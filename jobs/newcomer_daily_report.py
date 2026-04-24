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


# ── 去重 ──────────────────────────────────────────────────────
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
SENT_FILE = CACHE_DIR / "newcomer_report_sent.txt"


def _load_sent() -> set[str]:
    if SENT_FILE.exists():
        return {l.strip() for l in SENT_FILE.read_text("utf-8").splitlines() if l.strip()}
    return set()


def _mark_sent(d: date) -> None:
    s = _load_sent()
    s.add(str(d))
    SENT_FILE.write_text("\n".join(sorted(s)), encoding="utf-8")


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

    if not args.force and str(report_date) in _load_sent():
        print(f"⏭️ {report_date} 已推送过，跳过。")
        return

    if not result.has_data:
        from services.wecom_push import send_wecom_webhook
        send_wecom_webhook(f"👶 新人日报 | {report_date}\n\n⚠️ **今日无新人质检数据**")
        _mark_sent(report_date)
        return

    mentioned = args.mention if args.mention else None
    ok, msg = send_wecom_webhook_with_split(wecom_md, mentioned_list=mentioned)
    if ok:
        print(f"✅ {msg}")
        _mark_sent(report_date)
    else:
        print(f"❌ 推送失败: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
