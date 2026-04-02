from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="重跑 schema.sql，刷新 TiDB 中的 mart 与规则维表。")
    parser.add_argument("--db-path", default=None, help="已废弃，保留兼容性")
    parser.add_argument("--schema-path", default=None, help="可选，自定义 schema.sql 路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = DashboardRepository()
    repo.initialize_schema(args.schema_path)

    stats = {
        "db_type": "tidb",
        "fact_qa_event_rows": 0,
        "fact_appeal_event_rows": 0,
        "mart_day_group_rows": 0,
        "mart_week_group_rows": 0,
        "mart_month_group_rows": 0,
        "mart_training_action_recovery_rows": 0,
    }

    for table_name, key in [
        ("fact_qa_event", "fact_qa_event_rows"),
        ("fact_appeal_event", "fact_appeal_event_rows"),
        ("mart_day_group", "mart_day_group_rows"),
        ("mart_week_group", "mart_week_group_rows"),
        ("mart_month_group", "mart_month_group_rows"),
        ("mart_training_action_recovery", "mart_training_action_recovery_rows"),
    ]:
        result = repo.fetch_one(f"SELECT COUNT(*) AS cnt FROM {table_name}")
        stats[key] = int(list(result.values())[0]) if result else 0

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
