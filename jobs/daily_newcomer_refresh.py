#!/usr/bin/env python3
"""新人专项日常刷新入口：按最近 N 天窗口回填新人文件，并复用现有回填/刷新链路。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
PYTHON_BIN = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="新人专项日常刷新：包装 recover_newcomer_uploads.py 的常用参数")
    parser.add_argument("--scan-days", type=int, default=3, help="向前扫描最近多少个业务日，默认 3 天")
    parser.add_argument("--end-date", default=None, help="结束业务日期（YYYY-MM-DD），默认今天")
    parser.add_argument("--stage", choices=["internal", "external", "all"], default="all", help="只处理内检或外检，默认 all")
    parser.add_argument("--limit", type=int, default=0, help="限制处理候选文件数，0 表示不限")
    parser.add_argument("--cache-root", default=None, help="自定义企微缓存根目录")
    parser.add_argument("--file-name", dest="file_names", action="append", default=[], help="指定原始文件名精确匹配，可重复传多个")
    parser.add_argument("--deep-scan", action="store_true", help="对文件名不明显的文件也做预览识别")
    parser.add_argument("--dry-run", action="store_true", help="只扫描候选文件，不执行导入")
    parser.add_argument("--cleanup-only", action="store_true", help="只清理 skipped/dedup 残留，不执行导入")
    parser.add_argument("--skip-refresh", action="store_true", help="导入后跳过数仓与告警刷新")
    return parser.parse_args()


def parse_end_date(raw_value: str | None) -> date:
    if not raw_value:
        return date.today()
    return datetime.strptime(raw_value, "%Y-%m-%d").date()


def build_command(args: argparse.Namespace) -> list[str]:
    end_date = parse_end_date(args.end_date)
    safe_scan_days = max(args.scan_days, 1)
    start_date = end_date - timedelta(days=safe_scan_days - 1)

    cmd = [
        PYTHON_BIN,
        str(PROJECT_ROOT / "jobs" / "recover_newcomer_uploads.py"),
        "--start-date",
        start_date.isoformat(),
        "--end-date",
        end_date.isoformat(),
        "--stage",
        args.stage,
    ]

    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.cache_root:
        cmd.extend(["--cache-root", args.cache_root])
    if args.deep_scan:
        cmd.append("--deep-scan")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.cleanup_only:
        cmd.append("--cleanup-only")
    if args.skip_refresh:
        cmd.append("--skip-refresh")
    for file_name in args.file_names:
        if file_name:
            cmd.extend(["--file-name", file_name])
    return cmd


def main() -> None:
    args = parse_args()
    cmd = build_command(args)

    print("=" * 72)
    print("新人专项日常刷新")
    print(f"执行目录: {PROJECT_ROOT}")
    print(f"执行命令: {' '.join(cmd)}")
    print("=" * 72)

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
