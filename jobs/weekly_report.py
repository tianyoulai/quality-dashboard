#!/usr/bin/env python3
"""质检周报 -- 基于统一报告引擎生成 & 推送。

用法:
    python jobs/weekly_report.py                     # 推送本周周报（截至今天）
    python jobs/weekly_report.py --dry-run           # 只生成不推送
    python jobs/weekly_report.py --date 2026-04-18   # 指定周结束日期
    python jobs/weekly_report.py --force             # 忽略去重
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reports import generate_weekly_report
from reports.formatters.wecom_card import format_weekly_wecom
from reports.formatters.markdown_file import format_weekly_markdown
from services.wecom_push import send_wecom_webhook_with_split
from jobs._report_common import load_sent, mark_sent, push_error_notification


def main() -> None:
    parser = argparse.ArgumentParser(description="质检周报生成 & 企微群推送")
    parser.add_argument("--date", default=str(date.today()), help="周结束日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--mention", nargs="*", default=[])
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    week_end = date.fromisoformat(args.date)
    week_start = week_end - timedelta(days=week_end.weekday())
    week_label = f"{week_start}~{week_end}"
    print(f"📈 周报生成 | {week_label}")

    try:
        _run_report(week_end, week_start, week_label, args)
    except Exception as e:
        print(f"❌ 周报生成失败: {e}")
        import traceback
        traceback.print_exc()
        if not args.dry_run:
            push_error_notification("质检周报", week_label, e)
        sys.exit(1)


def _run_report(week_end: date, week_start: date, week_label: str, args) -> None:
    """周报生成核心逻辑。"""

    # 1. 生成
    result = generate_weekly_report(week_end, skip_ai=args.skip_ai)

    # 2. 格式化
    wecom_md = format_weekly_wecom(result)
    full_md = format_weekly_markdown(result)

    # 3. 输出
    print(wecom_md)

    out_path = Path(args.output) if args.output else PROJECT_ROOT / "deliverables" / f"weekly_report_{week_start}_{week_end}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_md, encoding="utf-8")
    print(f"\n📄 周报已保存: {out_path}")

    # JSON
    json_path = PROJECT_ROOT / "deliverables" / f"weekly_data_{week_start}_{week_end}.json"
    json_data = {
        "week_start": str(result.week_start),
        "week_end": str(result.week_end),
        "has_data": result.has_data,
        "acc": result.acc,
        "total_qa": result.total_qa,
        "total_error": result.total_error,
        "week_over_week_acc_pp": result.week_over_week_acc_pp,
        "daily_trend": result.daily_trend,
        "groups": [
            {"name": g.name, "acc": g.acc, "qa_cnt": g.qa_cnt, "error_cnt": g.error_cnt}
            for g in result.groups
        ],
        "alerts": {"P0": result.alerts.p0, "P1": result.alerts.p1, "P2": result.alerts.p2},
        "ai_insight": result.ai_insight,
    }
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📊 数据已保存: {json_path}")

    # 4. 推送
    if args.dry_run:
        print("\n⏭️ dry-run 模式，未推送。")
        return

    if not args.force and week_label in load_sent("weekly"):
        print(f"⏭️ {week_label} 已推送过，跳过。")
        return

    if not result.has_data:
        from services.wecom_push import send_wecom_webhook
        send_wecom_webhook(f"📈 质检周报 | {week_label}\n\n⚠️ **本周无质检数据**")
        mark_sent("weekly", week_label)
        return

    mentioned = args.mention if args.mention else None
    ok, msg = send_wecom_webhook_with_split(wecom_md, mentioned_list=mentioned)
    if ok:
        print(f"✅ {msg}")
        mark_sent("weekly", week_label)
    else:
        print(f"❌ 推送失败: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
