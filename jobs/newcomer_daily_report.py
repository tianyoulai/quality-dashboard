#!/usr/bin/env python3
"""新人培训日报：生成 Markdown 并通过企微机器人推送。

基于 services/newcomer_aggregates.py 的 build_training_daily_payload + format_training_daily_markdown。
支持命令行独立运行，可由 launchd 定时调用。

用法:
    python jobs/newcomer_daily_report.py                 # 推送今日新人日报
    python jobs/newcomer_daily_report.py --dry-run       # 只生成不推送
    python jobs/newcomer_daily_report.py --force         # 强制推送（忽略去重）
    python jobs/newcomer_daily_report.py --date 2026-04-14  # 指定日期
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.newcomer_aggregates import (
    build_training_daily_payload,
    format_training_daily_markdown,
    send_training_daily_report,
)
# wecom 推送由 send_training_daily_report 内部处理，无需额外导入

# ── 去重文件 ──
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
SENT_FILE = CACHE_DIR / "newcomer_report_sent.txt"


def _load_sent_dates() -> set[str]:
    if not SENT_FILE.exists():
        return set()
    return {line.strip() for line in SENT_FILE.read_text().splitlines() if line.strip()}


def _mark_date_sent(report_date: date) -> None:
    sent = _load_sent_dates()
    sent.add(str(report_date))
    SENT_FILE.write_text("\n".join(sorted(sent)) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="新人培训日报生成 & 企微群推送")
    parser.add_argument("--date", default=str(date.today() - timedelta(days=1)),
                        help="报告日期 YYYY-MM-DD（默认 T-1）")
    parser.add_argument("--dry-run", action="store_true", help="只生成不推送")
    parser.add_argument("--force", action="store_true", help="强制推送（忽略去重检查）")
    parser.add_argument("--mention", nargs="*", default=[], help="@指定成员 userId 列表")
    args = parser.parse_args()

    report_date = args.date
    print(f"👶 新人培训日报 | 日期: {report_date}")

    # 生成日报内容
    payload = build_training_daily_payload()
    markdown = format_training_daily_markdown(payload)

    if args.dry_run:
        print("\n" + "=" * 60)
        print(markdown)
        print("=" * 60)
        print("\n⏭️ dry-run 模式，未推送。")
        return

    # 去重检查
    if not args.force:
        sent_dates = _load_sent_dates()
        if str(report_date) in sent_dates:
            print(f"⏭️ 报告日期 {report_date} 已推送过，跳过（可用 --force 强制推送）")
            return

    # 推送
    result = send_training_daily_report(
        mentioned_list=args.mention if args.mention else None,
    )

    if result.get("ok"):
        print(f"✅ 新人日报推送成功")
        _mark_date_sent(date.fromisoformat(report_date))
    else:
        print(f"❌ 推送失败: {result.get('message', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
