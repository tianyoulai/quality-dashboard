from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jobs.import_fact_data import extract_date_from_filename
from storage.repository import DashboardRepository


@dataclass
class CleanupResult:
    file_name: str
    removed_skipped_logs: int
    removed_success_logs: int
    removed_failed_logs: int
    removed_dedup_rows: int
    removed_fact_qa_rows: int
    removed_fact_newcomer_rows: int


@dataclass
class ImportResult:
    file_name: str
    file_path: str
    status: str
    inserted_rows: int
    message: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理错误判重状态，并按指定文件补导质检数据。")
    parser.add_argument("--file-name", dest="file_names", action="append", required=True, help="原始文件名，可重复传多个")
    parser.add_argument("--qa-file", dest="qa_files", action="append", default=[], help="本地 Excel 路径，顺序需与 --file-name 一致")
    parser.add_argument("--cleanup-only", action="store_true", help="只清理错误判重状态，不执行补导")
    parser.add_argument("--skip-refresh", action="store_true", help="补导后跳过数仓/告警刷新")
    return parser.parse_args()


def cleanup_retry_state(repo: DashboardRepository, file_name: str) -> CleanupResult:
    skipped_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_upload_log
        WHERE file_name = %s
          AND upload_status = 'skipped'
          AND error_message = '文件内容已存在，跳过重复导入'
        """,
        [file_name],
    )
    success_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_upload_log
        WHERE file_name = %s
          AND upload_status = 'success'
        """,
        [file_name],
    )
    failed_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_upload_log
        WHERE file_name = %s
          AND upload_status = 'failed'
        """,
        [file_name],
    )
    dedup_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_file_dedup
        WHERE file_name = %s
        """,
        [file_name],
    )
    fact_qa_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_qa_event
        WHERE source_file_name = %s
        """,
        [file_name],
    )
    fact_newcomer_rows = repo.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM fact_newcomer_qa
        WHERE source_file_name = %s
        """,
        [file_name],
    )

    # 用替换式重导：先删历史事实表数据和上传日志，再重新导入，避免重复累计。
    repo.execute(
        """
        DELETE FROM fact_qa_event
        WHERE source_file_name = %s
        """,
        [file_name],
    )
    repo.execute(
        """
        DELETE FROM fact_newcomer_qa
        WHERE source_file_name = %s
        """,
        [file_name],
    )
    repo.execute(
        """
        DELETE FROM fact_upload_log
        WHERE file_name = %s
        """,
        [file_name],
    )
    repo.execute(
        """
        DELETE FROM fact_file_dedup
        WHERE file_name = %s
        """,
        [file_name],
    )

    return CleanupResult(
        file_name=file_name,
        removed_skipped_logs=int((skipped_rows or {}).get("cnt") or 0),
        removed_success_logs=int((success_rows or {}).get("cnt") or 0),
        removed_failed_logs=int((failed_rows or {}).get("cnt") or 0),
        removed_dedup_rows=int((dedup_rows or {}).get("cnt") or 0),
        removed_fact_qa_rows=int((fact_qa_rows or {}).get("cnt") or 0),
        removed_fact_newcomer_rows=int((fact_newcomer_rows or {}).get("cnt") or 0),
    )


def run_import(file_name: str, file_path: Path) -> ImportResult:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "jobs/import_fact_data.py"),
        "--qa-file",
        str(file_path),
        "--source-name",
        file_name,
        "--skip-refresh",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"补导失败：{file_name}")

    try:
        payload = json.loads(result.stdout)
        qa_result = payload.get("qa_files", [{}])[0]
    except Exception as exc:
        raise RuntimeError(f"补导输出解析失败：{file_name} | {exc}") from exc

    return ImportResult(
        file_name=file_name,
        file_path=str(file_path),
        status=qa_result.get("status", "success"),
        inserted_rows=int(qa_result.get("inserted_rows") or 0),
        message=qa_result.get("message"),
    )


def run_refresh(start_date: date | None, end_date: date | None) -> bool:
    if not start_date or not end_date:
        return False
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "jobs/refresh_warehouse.py"),
            "--start-date",
            start_date.isoformat(),
            "--end-date",
            end_date.isoformat(),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "refresh_warehouse 执行失败")
    return True


def run_alert_refresh() -> bool:
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "jobs/refresh_alerts.py"),
            "--lookback-days",
            "45",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "refresh_alerts 执行失败")
    return True


def main() -> None:
    args = parse_args()
    file_names = args.file_names
    qa_files = [Path(path).expanduser().resolve() for path in args.qa_files]

    if qa_files and len(qa_files) != len(file_names):
        raise SystemExit("--qa-file 数量必须与 --file-name 一致")
    if any(not path.exists() for path in qa_files):
        missing = [str(path) for path in qa_files if not path.exists()]
        raise FileNotFoundError(f"以下补导文件不存在：{missing}")

    repo = DashboardRepository()
    repo.initialize_schema()

    cleanup_results = [asdict(cleanup_retry_state(repo, file_name)) for file_name in file_names]

    import_results: list[dict] = []
    refreshed = False
    alert_refreshed = False
    refresh_error = None
    alert_refresh_error = None

    if not args.cleanup_only and qa_files:
        biz_dates: list[date] = []
        for file_name, file_path in zip(file_names, qa_files, strict=True):
            result = run_import(file_name, file_path)
            import_results.append(asdict(result))
            file_date = extract_date_from_filename(file_name)
            if file_date:
                biz_dates.append(file_date)

        if import_results and not args.skip_refresh and biz_dates:
            try:
                refreshed = run_refresh(min(biz_dates), max(biz_dates))
            except Exception as exc:
                refresh_error = str(exc)
            try:
                alert_refreshed = run_alert_refresh()
            except Exception as exc:
                alert_refresh_error = str(exc)

    payload = {
        "cleaned": cleanup_results,
        "imports": import_results,
        "refreshed": refreshed,
        "alert_refreshed": alert_refreshed,
        "refresh_error": refresh_error,
        "alert_refresh_error": alert_refresh_error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
