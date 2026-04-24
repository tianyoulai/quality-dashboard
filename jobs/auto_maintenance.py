"""自动化运维 - 数据归档 & 健康检查推送。

功能：
1. 自动归档超过 N 天的 fact_qa_event 数据到归档表
2. 定期执行数据健康检查并推送异常到企微
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository


def _load_settings() -> dict:
    p = PROJECT_ROOT / "config" / "settings.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def archive_old_data(days_to_keep: int = 90) -> dict:
    """归档超过指定天数的质检数据。

    不会物理删除，只是将超期数据从 fact_qa_event 移到 fact_qa_event_archive。
    """
    repo = DashboardRepository()
    cutoff = date.today() - timedelta(days=days_to_keep)

    # 确保归档表存在
    repo.execute("""
        CREATE TABLE IF NOT EXISTS fact_qa_event_archive LIKE fact_qa_event
    """)

    # 统计待归档数量
    row = repo.fetch_one(
        "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE biz_date < %s",
        [cutoff],
    )
    archive_cnt = row["cnt"] if row else 0

    if archive_cnt == 0:
        return {"archived": 0, "cutoff": str(cutoff), "message": "无需归档"}

    # 复制到归档表
    repo.execute("""
        INSERT IGNORE INTO fact_qa_event_archive
        SELECT * FROM fact_qa_event WHERE biz_date < %s
    """, [cutoff])

    # 从主表删除
    repo.execute("DELETE FROM fact_qa_event WHERE biz_date < %s", [cutoff])

    return {
        "archived": archive_cnt,
        "cutoff": str(cutoff),
        "message": f"已归档 {archive_cnt} 条 {cutoff} 之前的数据",
    }


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
    parser.add_argument("--archive", action="store_true", help="执行数据归档")
    parser.add_argument("--days", type=int, default=90, help="保留天数")
    parser.add_argument("--health", action="store_true", help="执行健康检查")
    parser.add_argument("--push", action="store_true", help="推送健康检查到企微")
    args = parser.parse_args()

    if args.archive:
        result = archive_old_data(args.days)
        print(json.dumps(result, ensure_ascii=False))

    if args.health:
        checks = run_health_check()
        for c in checks:
            icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(c["status"], "?")
            print(f"{icon} {c['item']}: {c['result']}")

    if args.push:
        push_health_report()
