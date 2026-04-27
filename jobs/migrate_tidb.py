"""TiDB 跨区域迁移工具（新加坡 → 东京）
============================================
用途：
  1. 从源集群导出最近 45 天数据到本地 parquet 文件
  2. 将导出数据导入目标集群（并执行 schema.sql）
  3. 可选：迁移完成后清空源集群（需 --drop-source 确认）

使用流程：
  # 步骤 1: 导出源集群数据
  python jobs/migrate_tidb.py export --days 45 --output /tmp/tidb_backup

  # 步骤 2: 在目标集群初始化 schema（只做一次）
  python jobs/migrate_tidb.py init-schema --target-env .env.tokyo

  # 步骤 3: 导入到目标集群
  python jobs/migrate_tidb.py import --input /tmp/tidb_backup --target-env .env.tokyo

  # 步骤 4: 验证
  python jobs/migrate_tidb.py verify --target-env .env.tokyo

凭据读取规则：
  - export 阶段使用默认 .env / settings.json（即新加坡）
  - import/init-schema/verify 通过 --target-env 指定东京凭据文件
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import mysql.connector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ---- 需要迁移的表清单（按依赖顺序）----
TABLES_WITH_DATE = {
    # 表名: 日期字段（用于 45 天过滤）
    "fact_qa_event": "biz_date",
    "fact_appeal_event": "appeal_date",
    "fact_newcomer_qa": "biz_date",
    "fact_newcomer_milestone": "event_date",
    "fact_upload_log": "upload_time",
    "fact_file_dedup": "upload_time",
    "fact_alert_event": "event_date",
    "fact_alert_status_history": "changed_at",
    "etl_run_log": "run_time",
    "sys_audit_log": "log_time",
    # mart 表 —— 明细数据按 45 天过滤
    "mart_day_group": "biz_date",
    "mart_day_queue": "biz_date",
    "mart_day_auditor": "biz_date",
    "mart_day_error_topic": "biz_date",
    "mart_week_group": "week_start",
    "mart_week_queue": "week_start",
    "mart_week_error_topic": "week_start",
    "mart_month_group": "month_start",
    "mart_month_queue": "month_start",
    "mart_month_error_topic": "month_start",
    "mart_training_action_recovery": "recovery_date",
}

# 维度/配置表 —— 全量迁移
TABLES_FULL = [
    "dim_newcomer_batch",
    "dim_graduation_rule",
    "dim_alert_rule",
    "fact_alert_status",  # 当前告警状态，全量
]


# ================================================================
# 连接工具
# ================================================================
def _load_env_file(path: Path) -> dict:
    """解析 .env 格式文件为 dict。"""
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def get_conn(env_file: Optional[str] = None):
    """按 env_file 或默认配置建立连接。"""
    if env_file:
        cfg = _load_env_file(Path(env_file))
        conn = mysql.connector.connect(
            host=cfg["TIDB_HOST"],
            port=int(cfg.get("TIDB_PORT", "4000")),
            user=cfg["TIDB_USER"],
            password=cfg["TIDB_PASSWORD"],
            database=cfg["TIDB_DATABASE"],
            ssl_verify_cert=False,
            ssl_disabled=False,
            connection_timeout=30,
        )
        return conn, cfg["TIDB_HOST"]
    # 使用项目默认配置（新加坡）
    from storage.tidb_manager import TiDBManager
    mgr = TiDBManager.get_instance()
    return mgr.get_connection().__enter__(), mgr.config.host  # 直接拿原生连接


# ================================================================
# 导出
# ================================================================
def cmd_export(args):
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    
    from storage.tidb_manager import TiDBManager
    mgr = TiDBManager.get_instance()
    
    print(f"📤 开始导出源集群数据（host={mgr.config.host}）")
    print(f"   保留天数: {args.days}，截止日期: {cutoff}")
    print(f"   输出目录: {out_dir}")
    print("=" * 60)
    
    total_rows = 0
    summary = []
    
    # 1) 按日期过滤的表
    for table, date_col in TABLES_WITH_DATE.items():
        try:
            sql = f"SELECT * FROM {table} WHERE {date_col} >= %s"
            with mgr.get_connection() as conn:
                df = pd.read_sql(sql, conn, params=(cutoff,))
            out_file = out_dir / f"{table}.parquet"
            df.to_parquet(out_file, index=False)
            rows = len(df)
            total_rows += rows
            summary.append((table, rows, out_file.stat().st_size))
            print(f"  ✅ {table:40s} {rows:>8,} 行  →  {out_file.name}")
        except Exception as e:
            print(f"  ⚠️  {table:40s} 导出失败: {e}")
    
    # 2) 全量表
    for table in TABLES_FULL:
        try:
            with mgr.get_connection() as conn:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
            out_file = out_dir / f"{table}.parquet"
            df.to_parquet(out_file, index=False)
            rows = len(df)
            total_rows += rows
            summary.append((table, rows, out_file.stat().st_size))
            print(f"  ✅ {table:40s} {rows:>8,} 行  →  {out_file.name} (全量)")
        except Exception as e:
            print(f"  ⚠️  {table:40s} 导出失败: {e}")
    
    # 写入清单文件
    manifest_path = out_dir / "_manifest.txt"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"# 源集群: {mgr.config.host}\n")
        f.write(f"# 导出时间: {datetime.now().isoformat()}\n")
        f.write(f"# 保留天数: {args.days}\n")
        f.write(f"# 截止日期: {cutoff}\n")
        f.write(f"# 总行数: {total_rows}\n\n")
        for table, rows, size in summary:
            f.write(f"{table:40s}\t{rows:>10}\t{size:>10} bytes\n")
    
    total_size = sum(s for _, _, s in summary)
    print("=" * 60)
    print(f"✅ 导出完成，总计 {total_rows:,} 行，{total_size / 1024 / 1024:.2f} MB")
    print(f"   清单文件: {manifest_path}")


# ================================================================
# 初始化目标集群 schema
# ================================================================
def cmd_init_schema(args):
    conn, host = get_conn(args.target_env)
    print(f"🏗️  在目标集群初始化 schema（host={host}）")
    
    schema_sql = (PROJECT_ROOT / "storage" / "schema.sql").read_text(encoding="utf-8")
    
    # 按语句切分（简单处理：按分号+换行）
    statements = [s.strip() for s in schema_sql.split(";\n") if s.strip() and not s.strip().startswith("--")]
    
    cursor = conn.cursor()
    executed = 0
    failed = 0
    for stmt in statements:
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            executed += 1
        except mysql.connector.Error as e:
            # 视图依赖可能顺序问题，忽略已存在错误
            if "already exists" in str(e).lower() or e.errno == 1050:
                continue
            print(f"  ⚠️  语句失败: {stmt[:80]}... → {e}")
            failed += 1
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Schema 初始化完成：成功 {executed} 条，跳过/失败 {failed} 条")


# ================================================================
# 导入到目标集群
# ================================================================
def cmd_import(args):
    in_dir = Path(args.input)
    if not in_dir.exists():
        print(f"❌ 输入目录不存在: {in_dir}")
        return
    
    conn, host = get_conn(args.target_env)
    print(f"📥 开始导入数据到目标集群（host={host}）")
    print(f"   输入目录: {in_dir}")
    print("=" * 60)
    
    # 先关闭外键检查以加速
    cursor = conn.cursor()
    cursor.execute("SET @@foreign_key_checks = 0")
    cursor.execute("SET @@unique_checks = 0")
    
    all_tables = list(TABLES_WITH_DATE.keys()) + TABLES_FULL
    total_rows = 0
    
    for table in all_tables:
        parquet_file = in_dir / f"{table}.parquet"
        if not parquet_file.exists():
            print(f"  ⏭️  {table:40s} 跳过（文件不存在）")
            continue
        
        df = pd.read_parquet(parquet_file)
        if df.empty:
            print(f"  ⏭️  {table:40s} 跳过（空表）")
            continue
        
        # 转换 NaN → None
        df = df.where(pd.notna(df), None)
        
        cols = list(df.columns)
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(f"`{c}`" for c in cols)
        # 使用 REPLACE INTO 或 INSERT IGNORE 处理可能的主键冲突
        insert_sql = f"INSERT IGNORE INTO `{table}` ({col_names}) VALUES ({placeholders})"
        
        batch_size = 500
        rows = df.values.tolist()
        imported = 0
        t0 = time.time()
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            try:
                cursor.executemany(insert_sql, batch)
                conn.commit()
                imported += len(batch)
            except Exception as e:
                conn.rollback()
                print(f"     ⚠️ 批次 {i} 失败: {e}")
        
        elapsed = time.time() - t0
        total_rows += imported
        print(f"  ✅ {table:40s} {imported:>8,} 行  用时 {elapsed:.1f}s")
    
    cursor.execute("SET @@foreign_key_checks = 1")
    cursor.execute("SET @@unique_checks = 1")
    cursor.close()
    conn.close()
    print("=" * 60)
    print(f"✅ 导入完成，总计 {total_rows:,} 行")


# ================================================================
# 验证
# ================================================================
def cmd_verify(args):
    conn, host = get_conn(args.target_env)
    print(f"🔍 验证目标集群数据（host={host}）")
    print("=" * 60)
    
    cursor = conn.cursor()
    all_tables = list(TABLES_WITH_DATE.keys()) + TABLES_FULL
    
    for table in all_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            (cnt,) = cursor.fetchone()
            
            date_col = TABLES_WITH_DATE.get(table)
            date_range = ""
            if date_col:
                cursor.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM `{table}`")
                dmin, dmax = cursor.fetchone()
                if dmin and dmax:
                    date_range = f"   [{dmin} ~ {dmax}]"
            print(f"  {table:40s} {cnt:>10,} 行{date_range}")
        except Exception as e:
            print(f"  ⚠️  {table:40s} 验证失败: {e}")
    
    cursor.close()
    conn.close()
    print("=" * 60)
    print("✅ 验证完成")


# ================================================================
# 主入口
# ================================================================
def main():
    parser = argparse.ArgumentParser(description="TiDB 跨区域迁移工具")
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    p_exp = sub.add_parser("export", help="从源集群导出数据")
    p_exp.add_argument("--days", type=int, default=45, help="保留最近 N 天（默认 45）")
    p_exp.add_argument("--output", default="/tmp/tidb_backup", help="输出目录")
    p_exp.set_defaults(func=cmd_export)
    
    p_init = sub.add_parser("init-schema", help="在目标集群初始化 schema")
    p_init.add_argument("--target-env", required=True, help="目标集群 .env 文件路径")
    p_init.set_defaults(func=cmd_init_schema)
    
    p_imp = sub.add_parser("import", help="导入到目标集群")
    p_imp.add_argument("--input", default="/tmp/tidb_backup", help="输入目录")
    p_imp.add_argument("--target-env", required=True, help="目标集群 .env 文件路径")
    p_imp.set_defaults(func=cmd_import)
    
    p_ver = sub.add_parser("verify", help="验证目标集群数据")
    p_ver.add_argument("--target-env", required=True, help="目标集群 .env 文件路径")
    p_ver.set_defaults(func=cmd_verify)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
