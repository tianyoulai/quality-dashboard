from __future__ import annotations

import argparse
import json
import sys
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jobs.import_fact_data import extract_date_from_filename, identify_newcomer_stage, normalize_name
from jobs.recover_failed_qa_uploads import cleanup_retry_state, run_alert_refresh, run_import, run_refresh
from storage.repository import DashboardRepository

WEWORK_CACHE_ROOT = Path.home() / "Library/Containers/com.tencent.WeWorkMac/Data/Documents/Profiles"
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}
EXCLUDE_PATTERNS = ["模板", "~$"]
DEFAULT_SCAN_DAYS = 45
PREVIEW_ROWS = 200

DIMENSION_COLUMN_ALIASES = {
    "content_type": ["内容类型", "内容体裁"],
    "risk_level": ["风险等级", "风险级别"],
    "training_topic": ["培训专题", "培训主题", "训练专题"],
}

# 派生源字段：原始文件没有目标列时，这些字段可以用来推断
DERIVABLE_SOURCE_COLUMNS = {
    "content_type": ["appName", "commentId", "评论ID", "评论id", "原始答案.commentContent", "评论文本"],  # appName/评论字段 → content_type
    "risk_level": ["reasonNumberLabel", "质检结果", "final_judgement", "错误类型"],  # 质检结果/错误类型 → risk_level
    "training_topic": [],  # 从文件名/队列名推断，不需要特定列
}


@dataclass
class CandidateFile:
    file_name: str
    file_path: str
    profile_id: str
    stage: str
    biz_date: date | None
    modified_at: datetime
    matched_by: str
    column_count: int
    content_type_column: str | None
    risk_level_column: str | None
    training_topic_column: str | None
    all_dimension_columns_ready: bool
    scan_error: str | None = None


def parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描企微缓存中的新人质检文件，并按需清理判重残留后回填导入。")
    parser.add_argument("--cache-root", default=str(WEWORK_CACHE_ROOT), help="企微缓存根目录，默认扫描 macOS 企业微信 Profiles 目录")
    parser.add_argument("--start-date", default=None, help="起始业务日期（YYYY-MM-DD），默认最近45天")
    parser.add_argument("--end-date", default=None, help="结束业务日期（YYYY-MM-DD），默认今天")
    parser.add_argument("--file-name", dest="file_names", action="append", default=[], help="指定原始文件名精确匹配，可重复传多个")
    parser.add_argument("--stage", choices=["internal", "external", "all"], default="all", help="只处理内检或外检文件，默认 all")
    parser.add_argument("--limit", type=int, default=0, help="限制返回/处理的候选文件数，0 表示不限")
    parser.add_argument("--dry-run", action="store_true", help="只扫描候选文件并检查三类维度字段，不执行导入")
    parser.add_argument("--cleanup-only", action="store_true", help="只清理历史 skipped/dedup 残留，不执行导入")
    parser.add_argument("--skip-refresh", action="store_true", help="导入后跳过数仓和告警刷新")
    parser.add_argument("--deep-scan", action="store_true", help="对文件名不明显的 Excel 也读取预览，尝试根据“新人评论测试”识别内检文件")
    return parser.parse_args()


def resolve_cache_dirs(cache_root: Path) -> list[tuple[str, Path]]:
    cache_root = cache_root.expanduser().resolve()
    candidates: list[tuple[str, Path]] = []

    if (cache_root / "Caches" / "Files").exists():
        return [(cache_root.name, cache_root / "Caches" / "Files")]

    if cache_root.name == "Files" and cache_root.exists():
        profile_id = cache_root.parent.parent.name if cache_root.parent.parent else "direct-files"
        return [(profile_id, cache_root)]

    if not cache_root.exists():
        return candidates

    for profile_dir in sorted(cache_root.iterdir()):
        if not profile_dir.is_dir():
            continue
        files_dir = profile_dir / "Caches" / "Files"
        if files_dir.exists():
            candidates.append((profile_dir.name, files_dir))
    return candidates


def month_range(month_dir_name: str) -> tuple[date, date] | None:
    try:
        month_start = datetime.strptime(month_dir_name, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None
    month_end = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
    return month_start, month_end


def month_overlaps(month_dir_name: str, start_date: date | None, end_date: date | None) -> bool:
    parsed = month_range(month_dir_name)
    if not parsed:
        return False
    month_start, month_end = parsed
    if start_date and month_end < start_date:
        return False
    if end_date and month_start > end_date:
        return False
    return True


def load_preview_frame(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        try:
            excel = pd.ExcelFile(file_path)
            sheet_name = "数据清洗" if "数据清洗" in excel.sheet_names else excel.sheet_names[0]
            return pd.read_excel(file_path, sheet_name=sheet_name, nrows=PREVIEW_ROWS, dtype=str)
        except Exception:
            return pd.read_excel(file_path, nrows=PREVIEW_ROWS, dtype=str)
    if suffix == ".csv":
        last_error: Exception | None = None
        for encoding in ["utf-8-sig", "utf-8", "gb18030"]:
            try:
                return pd.read_csv(file_path, nrows=PREVIEW_ROWS, dtype=str, encoding=encoding)
            except Exception as exc:  # noqa: PERF203
                last_error = exc
        raise RuntimeError(f"CSV 预览失败：{last_error}")
    raise ValueError(f"不支持的文件类型：{suffix}")


def match_dimension_columns(columns: list[Any]) -> dict[str, str | None]:
    normalized = {normalize_name(str(column)): str(column) for column in columns}
    matched: dict[str, str | None] = {}
    for field, aliases in DIMENSION_COLUMN_ALIASES.items():
        hit = None
        for candidate in [field, *aliases]:
            hit = normalized.get(normalize_name(candidate))
            if hit is not None:
                break
        matched[field] = hit
    return matched


def resolve_dimension_availability(columns: list[Any], stage: str) -> dict[str, str | None]:
    """返回三类维度在候选文件中的可用来源。

    直接列优先；没有直接列时，若存在可派生源字段，则返回“派生(列名)”标识。
    """
    normalized = {normalize_name(str(column)): str(column) for column in columns}
    direct_hits = match_dimension_columns(columns)
    resolved: dict[str, str | None] = {}

    for field, direct_hit in direct_hits.items():
        if direct_hit is not None:
            resolved[field] = direct_hit
            continue

        derived_hit = None
        for source_name in DERIVABLE_SOURCE_COLUMNS.get(field, []):
            normalized_hit = normalized.get(normalize_name(source_name))
            if normalized_hit is not None:
                derived_hit = f"派生({normalized_hit})"
                break

        if derived_hit is not None:
            resolved[field] = derived_hit
        elif field == "training_topic" and stage in {"internal", "external"}:
            resolved[field] = "派生(文件名/队列名)"
        else:
            resolved[field] = None

    return resolved


def detect_candidate(
    *,
    file_path: Path,
    file_name: str,
    profile_id: str,
    deep_scan: bool,
    force_preview: bool,
) -> CandidateFile | None:
    obvious_stage = identify_newcomer_stage(file_name)
    should_preview = force_preview or obvious_stage is not None or deep_scan
    if not should_preview:
        return None

    try:
        preview_df = load_preview_frame(file_path)
    except Exception as exc:
        if obvious_stage is None and not force_preview:
            return None
        return CandidateFile(
            file_name=file_name,
            file_path=str(file_path),
            profile_id=profile_id,
            stage=obvious_stage or "unknown",
            biz_date=extract_date_from_filename(file_name),
            modified_at=datetime.fromtimestamp(file_path.stat().st_mtime),
            matched_by="filename" if obvious_stage is not None else "content",
            column_count=0,
            content_type_column=None,
            risk_level_column=None,
            training_topic_column=None,
            all_dimension_columns_ready=False,
            scan_error=str(exc),
        )

    stage = identify_newcomer_stage(file_name, preview_df)
    if stage is None:
        return None

    dimension_availability = resolve_dimension_availability(preview_df.columns.tolist(), stage)
    matched_by = "filename" if obvious_stage is not None else "content"
    return CandidateFile(
        file_name=file_name,
        file_path=str(file_path),
        profile_id=profile_id,
        stage=stage,
        biz_date=extract_date_from_filename(file_name),
        modified_at=datetime.fromtimestamp(file_path.stat().st_mtime),
        matched_by=matched_by,
        column_count=len(preview_df.columns),
        content_type_column=dimension_availability["content_type"],
        risk_level_column=dimension_availability["risk_level"],
        training_topic_column=dimension_availability["training_topic"],
        all_dimension_columns_ready=all(dimension_availability.values()),
    )


def scan_candidates(
    *,
    cache_root: Path,
    start_date: date | None,
    end_date: date | None,
    exact_file_names: set[str],
    stage_filter: str,
    deep_scan: bool,
    limit: int,
) -> list[CandidateFile]:
    candidates: list[CandidateFile] = []

    for profile_id, files_root in resolve_cache_dirs(cache_root):
        if not files_root.exists():
            continue

        for month_dir in sorted(files_root.iterdir()):
            if not month_dir.is_dir() or not month_overlaps(month_dir.name, start_date, end_date):
                continue

            for file_path in sorted(month_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue

                file_name = file_path.name
                if any(pattern in file_name for pattern in EXCLUDE_PATTERNS):
                    continue

                exact_match = bool(exact_file_names) and file_name in exact_file_names
                if exact_file_names and not exact_match:
                    continue

                biz_date = extract_date_from_filename(file_name)
                if not exact_match and biz_date is not None:
                    if start_date and biz_date < start_date:
                        continue
                    if end_date and biz_date > end_date:
                        continue

                candidate = detect_candidate(
                    file_path=file_path,
                    file_name=file_name,
                    profile_id=profile_id,
                    deep_scan=deep_scan,
                    force_preview=exact_match,
                )
                if candidate is None:
                    continue
                if stage_filter != "all" and candidate.stage != stage_filter:
                    continue

                candidates.append(candidate)

    candidates.sort(key=lambda item: ((item.biz_date or date.min), item.file_name, item.profile_id), reverse=True)
    return candidates[:limit] if limit > 0 else candidates


def default_date_window(start_date: date | None, end_date: date | None) -> tuple[date | None, date | None]:
    safe_end = end_date or date.today()
    safe_start = start_date or (safe_end - timedelta(days=DEFAULT_SCAN_DAYS - 1))
    return safe_start, safe_end


def main() -> None:
    args = parse_args()
    exact_file_names = {name.strip() for name in args.file_names if name and name.strip()}
    start_date = parse_optional_date(args.start_date)
    end_date = parse_optional_date(args.end_date)
    start_date, end_date = default_date_window(start_date, end_date)
    cache_root = Path(args.cache_root)

    candidates = scan_candidates(
        cache_root=cache_root,
        start_date=start_date,
        end_date=end_date,
        exact_file_names=exact_file_names,
        stage_filter=args.stage,
        deep_scan=args.deep_scan,
        limit=max(args.limit, 0),
    )

    payload: dict[str, Any] = {
        "scan": {
            "cache_root": str(cache_root.expanduser()),
            "start_date": start_date,
            "end_date": end_date,
            "stage_filter": args.stage,
            "deep_scan": args.deep_scan,
            "exact_file_names": sorted(exact_file_names),
            "candidate_count": len(candidates),
        },
        "candidates": [asdict(item) for item in candidates],
        "cleaned": [],
        "imports": [],
        "refreshed": False,
        "alert_refreshed": False,
        "refresh_error": None,
        "alert_refresh_error": None,
    }

    if args.dry_run or not candidates:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    repo = DashboardRepository()
    repo.initialize_schema()

    cleanup_results = [asdict(cleanup_retry_state(repo, item.file_name)) for item in candidates]
    payload["cleaned"] = cleanup_results

    import_results: list[dict[str, Any]] = []
    imported_dates: list[date] = []
    if not args.cleanup_only:
        for item in candidates:
            result = run_import(item.file_name, Path(item.file_path))
            import_results.append(asdict(result))
            if result.status == "success" and result.inserted_rows > 0 and item.biz_date is not None:
                imported_dates.append(item.biz_date)
        payload["imports"] = import_results

        if import_results and not args.skip_refresh and imported_dates:
            try:
                payload["refreshed"] = run_refresh(min(imported_dates), max(imported_dates))
            except Exception as exc:
                payload["refresh_error"] = str(exc)
            try:
                payload["alert_refreshed"] = run_alert_refresh()
            except Exception as exc:
                payload["alert_refresh_error"] = str(exc)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
