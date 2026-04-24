#!/usr/bin/env python3
"""新人培训日报 -- 基于统一报告引擎生成 & 推送。

用法:
    python jobs/newcomer_daily_report.py                  # 推送今日新人日报
    python jobs/newcomer_daily_report.py --dry-run        # 只生成不推送
    python jobs/newcomer_daily_report.py --date 2026-04-21
    python jobs/newcomer_daily_report.py --force
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reports import generate_newcomer_report
from reports.formatters.wecom_card import format_newcomer_wecom
from reports.formatters.markdown_file import format_newcomer_markdown
from services.wecom_push import send_wecom_webhook_with_split
from jobs._report_common import load_sent, mark_sent, push_error_notification


def main() -> None:
    parser = argparse.ArgumentParser(description="新人培训日报生成 & 企微群推送")
    parser.add_argument("--date", default=str(date.today() - timedelta(days=1)))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    parser.add_argument("--mention", nargs="*", default=[])
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date)
    print(f"👶 新人培训日报 | {report_date}")

    try:
        _run_report(report_date, args)
    except Exception as e:
        print(f"❌ 新人日报生成失败: {e}")
        import traceback
        traceback.print_exc()
        if not args.dry_run:
            push_error_notification("新人培训日报", str(report_date), e)
        sys.exit(1)


def _run_report(report_date: date, args) -> None:
    """新人日报生成核心逻辑。"""

    # 1. 生成
    result = generate_newcomer_report(report_date, skip_ai=args.skip_ai)

    # 2. 格式化
    wecom_md = format_newcomer_wecom(result)
    full_md = format_newcomer_markdown(result)

    # 3. 输出
    print(wecom_md)

    out_path = PROJECT_ROOT / "deliverables" / f"newcomer_report_{report_date}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_md, encoding="utf-8")
    print(f"\n📄 新人日报已保存: {out_path}")

    # 4. 推送
    if args.dry_run:
        print("\n⏭️ dry-run 模式，未推送。")
        return

    if not args.force and str(report_date) in load_sent("newcomer"):
        print(f"⏭️ {report_date} 已推送过，跳过。")
        return

    if not result.has_data:
        from services.wecom_push import send_wecom_webhook
        send_wecom_webhook(f"👶 新人日报 | {report_date}\n\n⚠️ **今日无新人质检数据**")
        mark_sent("newcomer", report_date)
        return

    mentioned = args.mention if args.mention else None
    ok, msg = send_wecom_webhook_with_split(wecom_md, mentioned_list=mentioned)
    if ok:
        print(f"✅ {msg}")
        mark_sent("newcomer", report_date)
    else:
        print(f"❌ 推送失败: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
