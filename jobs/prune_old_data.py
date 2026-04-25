#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository
from utils.constants import RETENTION_DAYS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理 TiDB 中超过保留期的历史数据")
    parser.add_argument("--retention-days", type=int, default=RETENTION_DAYS,
                        help=f"保留最近多少天数据，默认 {RETENTION_DAYS}")
    return parser.parse_args()


def week_begin(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_begin(d: date) -> date:
    return d.replace(day=1)


def fetch_count(repo: DashboardRepository, table: str, where_sql: str, params: list) -> int:
    row = repo.fetch_one(f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where_sql}", params)
    return int(row["cnt"]) if row and row.get("cnt") is not None else 0


def main() -> None:
    args = parse_args()
    retention_days = max(int(args.retention_days), 1)
    cutoff_date = date.today() - timedelta(days=retention_days - 1)
    cutoff_week = week_begin(cutoff_date)
    cutoff_month = month_begin(cutoff_date)

    repo = DashboardRepository()
    repo.initialize_schema()

    stats = {
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
        "deleted": {},
    }

    # 先统计
    stats["deleted"]["fact_qa_event"] = fetch_count(repo, "fact_qa_event", "biz_date < %s", [cutoff_date])
    stats["deleted"]["fact_appeal_event"] = fetch_count(repo, "fact_appeal_event", "biz_date < %s", [cutoff_date])
    stats["deleted"]["fact_newcomer_qa"] = fetch_count(repo, "fact_newcomer_qa", "biz_date < %s", [cutoff_date])
    stats["deleted"]["mart_day_group"] = fetch_count(repo, "mart_day_group", "biz_date < %s", [cutoff_date])
    stats["deleted"]["mart_day_queue"] = fetch_count(repo, "mart_day_queue", "biz_date < %s", [cutoff_date])
    stats["deleted"]["mart_day_auditor"] = fetch_count(repo, "mart_day_auditor", "biz_date < %s", [cutoff_date])
    stats["deleted"]["mart_day_error_topic"] = fetch_count(repo, "mart_day_error_topic", "biz_date < %s", [cutoff_date])
    stats["deleted"]["mart_week_group"] = fetch_count(repo, "mart_week_group", "week_begin_date < %s", [cutoff_week])
    stats["deleted"]["mart_week_queue"] = fetch_count(repo, "mart_week_queue", "week_begin_date < %s", [cutoff_week])
    stats["deleted"]["mart_week_error_topic"] = fetch_count(repo, "mart_week_error_topic", "week_begin_date < %s", [cutoff_week])
    stats["deleted"]["mart_month_group"] = fetch_count(repo, "mart_month_group", "month_begin_date < %s", [cutoff_month])
    stats["deleted"]["mart_month_queue"] = fetch_count(repo, "mart_month_queue", "month_begin_date < %s", [cutoff_month])
    stats["deleted"]["mart_month_error_topic"] = fetch_count(repo, "mart_month_error_topic", "month_begin_date < %s", [cutoff_month])
    stats["deleted"]["fact_alert_event"] = fetch_count(repo, "fact_alert_event", "alert_date < %s", [cutoff_date])
    stats["deleted"]["mart_training_action_recovery"] = fetch_count(repo, "mart_training_action_recovery", "action_date < %s", [cutoff_date])
    stats["deleted"]["fact_upload_log"] = fetch_count(repo, "fact_upload_log", "upload_time < %s", [cutoff_date])
    stats["deleted"]["fact_file_dedup"] = fetch_count(repo, "fact_file_dedup", "first_upload_time < %s", [cutoff_date])

    sql_list = [
        ("DELETE FROM fact_qa_event WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM fact_appeal_event WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM fact_newcomer_qa WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM mart_day_group WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM mart_day_queue WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM mart_day_auditor WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM mart_day_error_topic WHERE biz_date < %s", [cutoff_date]),
        ("DELETE FROM mart_week_group WHERE week_begin_date < %s", [cutoff_week]),
        ("DELETE FROM mart_week_queue WHERE week_begin_date < %s", [cutoff_week]),
        ("DELETE FROM mart_week_error_topic WHERE week_begin_date < %s", [cutoff_week]),
        ("DELETE FROM mart_month_group WHERE month_begin_date < %s", [cutoff_month]),
        ("DELETE FROM mart_month_queue WHERE month_begin_date < %s", [cutoff_month]),
        ("DELETE FROM mart_month_error_topic WHERE month_begin_date < %s", [cutoff_month]),
        ("DELETE FROM fact_alert_event WHERE alert_date < %s", [cutoff_date]),
        ("DELETE FROM mart_training_action_recovery WHERE action_date < %s", [cutoff_date]),
        ("DELETE FROM fact_upload_log WHERE upload_time < %s", [cutoff_date]),
        ("DELETE FROM fact_file_dedup WHERE first_upload_time < %s", [cutoff_date]),
        ("DELETE s FROM fact_alert_status s LEFT JOIN fact_alert_event e ON s.alert_id = e.alert_id WHERE e.alert_id IS NULL", None),
        ("DELETE h FROM fact_alert_status_history h LEFT JOIN fact_alert_event e ON h.alert_id = e.alert_id WHERE e.alert_id IS NULL", None),
    ]

    repo.execute_in_transaction(sql_list)

    stats["deleted_total"] = int(sum(stats["deleted"].values()))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
