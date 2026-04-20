#!/usr/bin/env python3
"""
🚀 一键应用高性能索引

功能：
1. 连接 TiDB 数据库
2. 读取 performance_indexes.sql
3. 逐条执行 CREATE INDEX 语句
4. 实时显示进度和耗时
5. 验证索引创建成功
6. 输出性能对比报告

使用方法：
    python3 jobs/apply_performance_indexes.py
    python3 jobs/apply_performance_indexes.py --dry-run  # 仅预览，不执行
"""

import argparse
import re
import time
from pathlib import Path

from storage.tidb_manager import TiDBManager


def extract_create_index_statements(sql_file: Path) -> list[str]:
    """从 SQL 文件中提取所有 CREATE INDEX 语句"""
    content = sql_file.read_text(encoding="utf-8")
    
    # 匹配 CREATE INDEX 语句（支持多行）
    pattern = r'CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+\w+\s+ON\s+\w+\([^)]+\);'
    statements = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    # 清理空白字符
    statements = [re.sub(r'\s+', ' ', stmt).strip() for stmt in statements]
    
    return statements


def get_existing_indexes(db: TiDBManager, table_name: str) -> set[str]:
    """获取表的现有索引"""
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name != 'PRIMARY'")
        indexes = cursor.fetchall()
        return {idx['Key_name'] for idx in indexes}
    finally:
        cursor.close()
        conn.close()


def apply_index(db: TiDBManager, statement: str, dry_run: bool = False) -> tuple[bool, float, str]:
    """
    应用单个索引
    
    Returns:
        (success: bool, elapsed_ms: float, message: str)
    """
    # 提取索引名和表名
    match = re.search(r'CREATE INDEX IF NOT EXISTS (\w+) ON (\w+)', statement, re.IGNORECASE)
    if not match:
        return False, 0, "无法解析语句"
    
    index_name = match.group(1)
    table_name = match.group(2)
    
    if dry_run:
        return True, 0, f"[DRY-RUN] 将创建索引 {index_name} 在表 {table_name}"
    
    # 检查索引是否已存在
    existing = get_existing_indexes(db, table_name)
    if index_name in existing:
        return True, 0, f"索引 {index_name} 已存在，跳过"
    
    # 执行创建
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        start = time.time()
        cursor.execute(statement)
        conn.commit()
        elapsed = (time.time() - start) * 1000
        return True, elapsed, f"✅ 成功创建 {index_name} ({elapsed:.0f}ms)"
    except Exception as e:
        conn.rollback()
        return False, 0, f"❌ 失败: {index_name} - {str(e)}"
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="应用高性能索引到 TiDB")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行")
    parser.add_argument("--sql-file", type=str, default="storage/performance_indexes.sql", help="SQL 文件路径")
    args = parser.parse_args()
    
    sql_file = Path(args.sql_file)
    if not sql_file.exists():
        print(f"❌ SQL 文件不存在: {sql_file}")
        return 1
    
    print("🚀 高性能索引应用工具")
    print("=" * 60)
    print(f"📄 SQL 文件: {sql_file}")
    print(f"🔧 模式: {'DRY-RUN（预览）' if args.dry_run else '实际执行'}")
    print("=" * 60)
    print()
    
    # 提取语句
    statements = extract_create_index_statements(sql_file)
    print(f"📊 找到 {len(statements)} 个 CREATE INDEX 语句\n")
    
    if not statements:
        print("❌ 没有找到有效的 CREATE INDEX 语句")
        return 1
    
    # 连接数据库
    try:
        db = TiDBManager()
        print("✅ 数据库连接成功\n")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return 1
    
    # 执行索引创建
    total_time = 0
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, stmt in enumerate(statements, 1):
        print(f"[{i}/{len(statements)}] ", end="")
        
        success, elapsed, message = apply_index(db, stmt, args.dry_run)
        print(message)
        
        if success:
            if "已存在" in message or "跳过" in message:
                skip_count += 1
            else:
                success_count += 1
                total_time += elapsed
        else:
            fail_count += 1
    
    # 总结报告
    print()
    print("=" * 60)
    print("📊 执行总结")
    print("=" * 60)
    print(f"✅ 成功创建: {success_count} 个")
    print(f"⏭️  已存在跳过: {skip_count} 个")
    print(f"❌ 失败: {fail_count} 个")
    print(f"⏱️  总耗时: {total_time / 1000:.2f}s")
    
    if not args.dry_run and success_count > 0:
        print()
        print("🎉 索引创建完成！")
        print()
        print("📝 建议执行以下步骤：")
        print("  1. 运行性能测试: /tmp/perf_test.sh")
        print("  2. 验证索引使用: EXPLAIN SELECT ... 查看执行计划")
        print("  3. 监控慢查询日志")
        print("  4. 对比优化前后性能")
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit(main())
