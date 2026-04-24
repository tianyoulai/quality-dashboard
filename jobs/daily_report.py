#!/usr/bin/env python3
"""质检日报 -- 基于统一报告引擎生成 & 推送。

用法:
    python jobs/daily_report.py                    # 推送 T-1 日报
    python jobs/daily_report.py --dry-run          # 只生成不推送
    python jobs/daily_report.py --date 2026-04-21  # 指定日期
    python jobs/daily_report.py --force            # 忽略去重
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

from reports import generate_daily_report
from reports.formatters.wecom_card import format_daily_wecom
from reports.formatters.markdown_file import format_daily_markdown
from services.wecom_push import send_wecom_webhook_with_split


# ── 去重 ──────────────────────────────────────────────────────
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
SENT_FILE = CACHE_DIR / "report_sent.txt"


def _load_sent() -> set[str]:
    if SENT_FILE.exists():
        return {l.strip() for l in SENT_FILE.read_text("utf-8").splitlines() if l.strip()}
    return set()


def _mark_sent(d: date) -> None:
    s = _load_sent()
    s.add(str(d))
    SENT_FILE.write_text("\n".join(sorted(s)), encoding="utf-8")


# ── 主流程 ────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="质检日报生成 & 企微群推送")
    parser.add_argument("--date", default=str(date.today() - timedelta(days=1)))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-ai", action="store_true", help="跳过 DeepSeek AI 洞察")
    parser.add_argument("--mention", nargs="*", default=[])
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date)
    print(f"📊 日报生成 | {report_date}")

    # 1. 生成数据
    result = generate_daily_report(report_date, skip_ai=args.skip_ai)

    # 2. 格式化
    wecom_md = format_daily_wecom(result)
    full_md = format_daily_markdown(result)

    # 3. 输出
    print(wecom_md)

    # 保存文件
    out_path = Path(args.output) if args.output else PROJECT_ROOT / "deliverables" / f"daily_report_{report_date}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_md, encoding="utf-8")
    print(f"\n📄 日报已保存: {out_path}")

    # 保存 JSON（供智能体读取）
    json_path = PROJECT_ROOT / "daily_data.json"
    json_data = {
        "report_date": str(result.report_date),
        "has_data": result.has_data,
        "target": result.target,
        "acc": result.acc,
        "total_qa": result.total_qa,
        "total_error": result.total_error,
        "groups": [
            {
                "name": g.name, "acc": g.acc, "qa_cnt": g.qa_cnt,
                "error_cnt": g.error_cnt, "flag": g.flag,
                "subs": [
                    {"name": s.name, "acc": s.acc, "qa_cnt": s.qa_cnt, "error_cnt": s.error_cnt, "flag": s.flag}
                    for s in g.subs
                ],
            }
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

    if not args.force and str(report_date) in _load_sent():
        print(f"⏭️ {report_date} 已推送过，跳过（--force 可强制）")
        return

    if not result.has_data:
        from services.wecom_push import send_wecom_webhook
        send_wecom_webhook(f"📊 质检日报 | {report_date}\n\n⚠️ **今日无质检数据**，请检查数据链路。")
        _mark_sent(report_date)
        print("⚠️ 无数据，已推送告警。")
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
