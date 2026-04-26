"""自动化运维 - 数据清理 & 健康检查推送。

功能：
1. 自动删除超过 RETENTION_DAYS(45) 天的历史数据
2. 定期执行数据健康检查并推送异常到企微
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository
from utils.constants import RETENTION_DAYS


def _load_settings() -> dict:
    p = PROJECT_ROOT / "config" / "settings.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _week_begin(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_begin(d: date) -> date:
    return d.replace(day=1)


def _fetch_count(repo: DashboardRepository, table: str, where_sql: str, params: list) -> int:
    row = repo.fetch_one(f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where_sql}", params)
    return int(row["cnt"]) if row and row.get("cnt") is not None else 0


def prune_old_data(days_to_keep: int | None = None) -> dict:
    """直接删除超过指定天数的所有历史数据（不归档）。

    默认保留 RETENTION_DAYS(45) 天，按每天约 4 万行计算，
    45 天约 180 万行，足够满足看板展示需求且不会占用过多存储。
    """
    retention = days_to_keep or RETENTION_DAYS
    repo = DashboardRepository()

    cutoff_date = date.today() - timedelta(days=retention)
    cutoff_week = _week_begin(cutoff_date)
    cutoff_month = _month_begin(cutoff_date)

    # 统计待清理数量
    stats = {
        "retention_days": retention,
        "cutoff_date": str(cutoff_date),
        "deleted": {},
    }

    day_tables = [
        "fact_qa_event", "fact_appeal_event", "fact_newcomer_qa",
        "mart_day_group", "mart_day_queue", "mart_day_auditor", "mart_day_error_topic",
    ]
    week_tables = ["mart_week_group", "mart_week_queue", "mart_week_error_topic"]
    month_tables = ["mart_month_group", "mart_month_queue", "mart_month_error_topic"]
    other_tables = [
        ("fact_alert_event", "alert_date"),
        ("mart_training_action_recovery", "action_date"),
        ("fact_upload_log", "upload_time"),
        ("fact_file_dedup", "first_upload_time"),
    ]

    for tbl in day_tables:
        stats["deleted"][tbl] = _fetch_count(repo, tbl, "biz_date < %s", [cutoff_date])
    for tbl in week_tables:
        stats["deleted"][tbl] = _fetch_count(repo, tbl, "week_begin_date < %s", [cutoff_week])
    for tbl in month_tables:
        stats["deleted"][tbl] = _fetch_count(repo, tbl, "month_begin_date < %s", [cutoff_month])
    for tbl, col in other_tables:
        stats["deleted"][tbl] = _fetch_count(repo, tbl, f"{col} < %s", [cutoff_date])

    total = sum(stats["deleted"].values())
    if total == 0:
        stats["deleted_total"] = 0
        stats["message"] = "无需清理"
        return stats

    # 构建删除 SQL
    sql_list = []
    for tbl in day_tables:
        sql_list.append((f"DELETE FROM {tbl} WHERE biz_date < %s", [cutoff_date]))
    for tbl in week_tables:
        sql_list.append((f"DELETE FROM {tbl} WHERE week_begin_date < %s", [cutoff_week]))
    for tbl in month_tables:
        sql_list.append((f"DELETE FROM {tbl} WHERE month_begin_date < %s", [cutoff_month]))
    for tbl, col in other_tables:
        sql_list.append((f"DELETE FROM {tbl} WHERE {col} < %s", [cutoff_date]))

    # 清理孤儿告警状态记录
    sql_list.append((
        "DELETE s FROM fact_alert_status s LEFT JOIN fact_alert_event e "
        "ON s.alert_id = e.alert_id WHERE e.alert_id IS NULL", None
    ))
    sql_list.append((
        "DELETE h FROM fact_alert_status_history h LEFT JOIN fact_alert_event e "
        "ON h.alert_id = e.alert_id WHERE e.alert_id IS NULL", None
    ))

    repo.execute_in_transaction(sql_list)

    stats["deleted_total"] = int(total)
    stats["message"] = f"已清理 {total:,} 条 {cutoff_date} 之前的数据"
    return stats


def run_health_check() -> list[dict]:
    """执行数据健康检查，返回检查项列表。"""
    repo = DashboardRepository()
    checks = []

    # 1. 数据量
    total = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_qa_event")
    total_cnt = total["cnt"] if total else 0
    checks.append({
        "item": "质检事实表总量",
        "result": f"{total_cnt:,}",
        "status": "ok" if total_cnt > 0 else "warn",
    })

    # 2. 最新数据日期
    latest = repo.fetch_one("SELECT MAX(biz_date) AS d FROM fact_qa_event")
    latest_date = latest["d"] if latest else None
    if latest_date:
        gap = (date.today() - latest_date).days
        checks.append({
            "item": "最新数据日期",
            "result": f"{latest_date} (距今{gap}天)",
            "status": "ok" if gap <= 1 else ("warn" if gap <= 3 else "error"),
        })
    else:
        checks.append({"item": "最新数据日期", "result": "无数据", "status": "error"})

    # 3. mart 表新鲜度
    for tbl in ["mart_day_group", "mart_day_queue"]:
        try:
            r = repo.fetch_one(f"SELECT COUNT(*) AS cnt, MAX(biz_date) AS d FROM {tbl}")
            cnt = r["cnt"] if r else 0
            d = r["d"] if r else None
            if cnt > 0 and d:
                gap = (date.today() - d).days
                checks.append({
                    "item": f"{tbl} 新鲜度",
                    "result": f"{cnt:,}条, 最新{d}",
                    "status": "ok" if gap <= 1 else "warn",
                })
            else:
                checks.append({"item": f"{tbl}", "result": "空", "status": "warn"})
        except Exception:
            checks.append({"item": f"{tbl}", "result": "表不存在", "status": "error"})

    # 4. 告警积压
    try:
        open_alerts = repo.fetch_one(
            "SELECT COUNT(*) AS cnt FROM fact_alert_event WHERE alert_status = 'open'"
        )
        open_cnt = open_alerts["cnt"] if open_alerts else 0
        checks.append({
            "item": "未处理告警",
            "result": f"{open_cnt} 条",
            "status": "ok" if open_cnt < 5 else ("warn" if open_cnt < 20 else "error"),
        })
    except Exception:
        pass

    return checks


def push_health_report() -> None:
    """执行健康检查并推送结果到企微。"""
    from services.wecom_push import push_text

    checks = run_health_check()
    errors = [c for c in checks if c["status"] == "error"]
    warns = [c for c in checks if c["status"] == "warn"]

    if not errors and not warns:
        return  # 一切正常不推送

    lines = [f"🩺 **数据健康检查** | {date.today()}"]
    lines.append("---")

    if errors:
        lines.append("**❌ 异常项**")
        for c in errors:
            lines.append(f"- {c['item']}: {c['result']}")

    if warns:
        lines.append("**⚠️ 关注项**")
        for c in warns:
            lines.append(f"- {c['item']}: {c['result']}")

    lines.append("")
    lines.append(f"共检查 {len(checks)} 项，异常 {len(errors)} 项，关注 {len(warns)} 项")

    push_text("\n".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--prune", action="store_true", help="执行数据清理（删除超期数据）")
    parser.add_argument("--days", type=int, default=RETENTION_DAYS,
                        help=f"保留天数，默认 {RETENTION_DAYS}")
    parser.add_argument("--health", action="store_true", help="执行健康检查")
    parser.add_argument("--push", action="store_true", help="推送健康检查到企微")
    # 兼容旧参数
    parser.add_argument("--archive", action="store_true",
                        help="[已废弃] 等同于 --prune，保留向后兼容")
    args = parser.parse_args()

    if args.prune or args.archive:
        result = prune_old_data(args.days)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.health:
        checks = run_health_check()
        for c in checks:
            icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(c["status"], "?")
            print(f"{icon} {c['item']}: {c['result']}")

    if args.push:
        push_health_report()
