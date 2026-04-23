from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from api.serializers import dataframe_to_records, normalize_payload
from storage.repository import DashboardRepository
from utils.cache import ttl_cache

router = APIRouter(prefix="/api/v1/details", tags=["details"])
repo = DashboardRepository()

DETAIL_COLUMNS = [
    {
        "key": "业务日期",
        "label": "业务日期",
        "select": "biz_date AS 业务日期",
        "source": "fact_qa_event.biz_date",
        "description": "样本所属业务日期，用于按天筛选和导出定位。",
        "default_visible": True,
    },
    {
        "key": "组别",
        "label": "组别",
        "select": "COALESCE(sub_biz, '—') AS 组别",
        "source": "fact_qa_event.sub_biz",
        "description": "业务组别 / 子业务线，和首页分组口径保持一致。",
        "default_visible": True,
    },
    {
        "key": "队列",
        "label": "队列",
        "select": "COALESCE(queue_name, '—') AS 队列",
        "source": "fact_qa_event.queue_name",
        "description": "样本所属审核队列。",
        "default_visible": True,
    },
    {
        "key": "审核人",
        "label": "审核人",
        "select": "COALESCE(reviewer_name, '—') AS 审核人",
        "source": "fact_qa_event.reviewer_name",
        "description": "执行审核的人员名称。",
        "default_visible": True,
    },
    {
        "key": "内容类型",
        "label": "内容类型",
        "select": "COALESCE(content_type, '—') AS 内容类型",
        "source": "fact_qa_event.content_type",
        "description": "内容体裁 / 内容类型，用于识别结构性问题。",
        "default_visible": True,
    },
    {
        "key": "一审结果",
        "label": "一审结果",
        "select": "raw_judgement AS 一审结果",
        "source": "fact_qa_event.raw_judgement",
        "description": "原始审核结论。",
        "default_visible": False,
    },
    {
        "key": "最终结果",
        "label": "最终结果",
        "select": "final_judgement AS 最终结果",
        "source": "fact_qa_event.final_judgement",
        "description": "质检后的最终结论。",
        "default_visible": False,
    },
    {
        "key": "申诉状态",
        "label": "申诉状态",
        "select": "appeal_status AS 申诉状态",
        "source": "fact_qa_event.appeal_status",
        "description": "样本在申诉链路中的当前状态。",
        "default_visible": False,
    },
    {
        "key": "申诉原因",
        "label": "申诉原因",
        "select": "appeal_reason AS 申诉原因",
        "source": "fact_qa_event.appeal_reason",
        "description": "申诉原因原文。",
        "default_visible": False,
    },
    {
        "key": "原始判断",
        "label": "原始判断",
        "select": "CASE WHEN is_raw_correct = 1 THEN '正确' ELSE '错误' END AS 原始判断",
        "source": "fact_qa_event.is_raw_correct",
        "description": "一审结果是否正确。",
        "default_visible": True,
    },
    {
        "key": "最终判断",
        "label": "最终判断",
        "select": "CASE WHEN is_final_correct = 1 THEN '正确' ELSE '错误' END AS 最终判断",
        "source": "fact_qa_event.is_final_correct",
        "description": "质检后的最终结果是否正确。",
        "default_visible": True,
    },
    {
        "key": "错判",
        "label": "错判",
        "select": "CASE WHEN is_misjudge = 1 THEN '是' ELSE '否' END AS 错判",
        "source": "fact_qa_event.is_misjudge",
        "description": "是否属于错判样本。",
        "default_visible": True,
    },
    {
        "key": "漏判",
        "label": "漏判",
        "select": "CASE WHEN is_missjudge = 1 THEN '是' ELSE '否' END AS 漏判",
        "source": "fact_qa_event.is_missjudge",
        "description": "是否属于漏判样本。",
        "default_visible": True,
    },
    {
        "key": "申诉改判",
        "label": "申诉改判",
        "select": "CASE WHEN is_appeal_reversed = 1 THEN '是' ELSE '否' END AS 申诉改判",
        "source": "fact_qa_event.is_appeal_reversed",
        "description": "是否因申诉产生改判。",
        "default_visible": True,
    },
    {
        "key": "错误类型",
        "label": "错误类型",
        "select": "COALESCE(error_type, '—') AS 错误类型",
        "source": "fact_qa_event.error_type",
        "description": "问题样本的错误类型标签。",
        "default_visible": True,
    },
    {
        "key": "错误归因",
        "label": "错误归因",
        "select": "COALESCE(error_reason, '—') AS 错误归因",
        "source": "fact_qa_event.error_reason",
        "description": "错误归因 / 问题原因补充。",
        "default_visible": False,
    },
    {
        "key": "评论文本",
        "label": "评论文本",
        "select": "comment_text AS 评论文本",
        "source": "fact_qa_event.comment_text",
        "description": "原始评论文本或内容摘要。",
        "default_visible": False,
    },
    {
        "key": "备注",
        "label": "备注",
        "select": "COALESCE(qa_note, '—') AS 备注",
        "source": "fact_qa_event.qa_note",
        "description": "质检备注 / 补充说明。",
        "default_visible": True,
    },
    {
        "key": "关联主键",
        "label": "关联主键",
        "select": "join_key AS 关联主键",
        "source": "fact_qa_event.join_key",
        "description": "用于和申诉、联表质量等链路关联的主键。",
        "default_visible": False,
    },
    {
        "key": "质检时间",
        "label": "质检时间",
        "select": "qa_time AS 质检时间",
        "source": "fact_qa_event.qa_time",
        "description": "质检动作发生时间。",
        "default_visible": True,
    },
]

DEFAULT_VISIBLE_DETAIL_KEYS = [item["key"] for item in DETAIL_COLUMNS if item["default_visible"]]
MAX_QUERY_LIMIT = 20000
EXPORT_ROW_CAP = 50000
PREVIEW_ROW_CAP = 50


def _normalize_issue_filter(only_issues: bool, issue_filter: str | None) -> str | None:
    if not only_issues:
        return None

    mapping = {
        "全部问题": "__all_issues__",
        "all": "__all_issues__",
        "all_issues": "__all_issues__",
        "__all_issues__": "__all_issues__",
        "原始错误": "原始错误",
        "raw": "原始错误",
        "raw_incorrect": "原始错误",
        "最终错误": "最终错误",
        "final": "最终错误",
        "final_incorrect": "最终错误",
        "错判": "错判",
        "misjudge": "错判",
        "漏判": "漏判",
        "missjudge": "漏判",
        "申诉改判": "申诉改判",
        "appeal_reversed": "申诉改判",
    }
    normalized = (issue_filter or "全部问题").strip()
    return mapping.get(normalized, normalized)


def _build_detail_select_sql() -> str:
    return ",\n        ".join(item["select"] for item in DETAIL_COLUMNS)


def _build_detail_schema() -> list[dict[str, object]]:
    return [
        {
            "key": item["key"],
            "label": item["label"],
            "source": item["source"],
            "description": item["description"],
            "default_visible": item["default_visible"],
        }
        for item in DETAIL_COLUMNS
    ]


def _build_detail_filters(
    date_start: date,
    date_end: date,
    group_name: str | None,
    queue_name: str | None,
    reviewer_name: str | None,
    error_type: str | None,
    only_issues: bool,
    issue_filter: str | None,
) -> tuple[list[str], list[object]]:
    conditions = ["biz_date >= %s", "biz_date <= %s"]
    params: list[object] = [date_start, date_end]

    if group_name:
        conditions.append("sub_biz = %s")
        params.append(group_name)
    if queue_name:
        conditions.append("queue_name = %s")
        params.append(queue_name)
    if reviewer_name:
        conditions.append("reviewer_name = %s")
        params.append(reviewer_name)
    if error_type:
        conditions.append("error_type = %s")
        params.append(error_type)

    normalized_issue_filter = _normalize_issue_filter(only_issues, issue_filter)
    if only_issues:
        if normalized_issue_filter == "__all_issues__":
            conditions.append("(NOT is_raw_correct OR NOT is_final_correct OR is_misjudge = 1 OR is_missjudge = 1 OR is_appeal_reversed = 1)")
        elif normalized_issue_filter == "原始错误":
            conditions.append("NOT is_raw_correct")
        elif normalized_issue_filter == "最终错误":
            conditions.append("NOT is_final_correct")
        elif normalized_issue_filter == "错判":
            conditions.append("is_misjudge = 1")
        elif normalized_issue_filter == "漏判":
            conditions.append("is_missjudge = 1")
        elif normalized_issue_filter == "申诉改判":
            conditions.append("is_appeal_reversed = 1")

    return conditions, params


def _query_detail_rows(
    date_start: date,
    date_end: date,
    group_name: str | None,
    queue_name: str | None,
    reviewer_name: str | None,
    error_type: str | None,
    only_issues: bool,
    issue_filter: str | None,
    limit: int | None,
) -> pd.DataFrame:
    conditions, params = _build_detail_filters(
        date_start=date_start,
        date_end=date_end,
        group_name=group_name,
        queue_name=queue_name,
        reviewer_name=reviewer_name,
        error_type=error_type,
        only_issues=only_issues,
        issue_filter=issue_filter,
    )

    sql = f"""
    SELECT
        {_build_detail_select_sql()}
    FROM fact_qa_event
    WHERE {' AND '.join(conditions)}
    ORDER BY qa_time IS NULL, qa_time DESC, biz_date DESC
    """
    if limit is not None:
        sql += "\n    LIMIT %s"
        params.append(int(limit))
    return repo.fetch_df(sql, params)


def _count_detail_rows(
    date_start: date,
    date_end: date,
    group_name: str | None,
    queue_name: str | None,
    reviewer_name: str | None,
    error_type: str | None,
    only_issues: bool,
    issue_filter: str | None,
) -> int:
    conditions, params = _build_detail_filters(
        date_start=date_start,
        date_end=date_end,
        group_name=group_name,
        queue_name=queue_name,
        reviewer_name=reviewer_name,
        error_type=error_type,
        only_issues=only_issues,
        issue_filter=issue_filter,
    )
    row = repo.fetch_one(
        f"SELECT COUNT(*) AS total_count FROM fact_qa_event WHERE {' AND '.join(conditions)}",
        params,
    )
    return int((row or {}).get("total_count") or 0)


def _to_csv_response(df: pd.DataFrame, file_name: str) -> StreamingResponse:
    export_df = df.copy()
    for column in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column]):
            export_df[column] = export_df[column].astype(str)
    payload = export_df.to_csv(index=False).encode("utf-8-sig")
    response = StreamingResponse(iter([payload]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@ttl_cache(ttl_seconds=300, key_prefix="details_filters")
def _get_filter_options_payload() -> dict[str, object]:
    groups = repo.fetch_df("SELECT DISTINCT sub_biz AS group_name FROM fact_qa_event WHERE sub_biz IS NOT NULL AND sub_biz <> '' ORDER BY 1")
    queues = repo.fetch_df("SELECT DISTINCT sub_biz AS group_name, queue_name FROM fact_qa_event WHERE sub_biz IS NOT NULL AND sub_biz <> '' AND queue_name IS NOT NULL AND queue_name <> '' ORDER BY 1, 2")
    reviewers_df = repo.fetch_df(
        "SELECT DISTINCT sub_biz AS group_name, reviewer_name FROM fact_qa_event WHERE sub_biz IS NOT NULL AND sub_biz <> '' AND reviewer_name IS NOT NULL AND reviewer_name <> '' ORDER BY 1, 2"
    )
    error_types = repo.fetch_df("SELECT DISTINCT error_type FROM fact_qa_event WHERE error_type IS NOT NULL AND error_type <> '' ORDER BY 1")
    date_range = repo.fetch_one("SELECT MIN(biz_date) AS min_date, MAX(biz_date) AS max_date FROM fact_qa_event")

    return {
        "groups": groups["group_name"].tolist() if not groups.empty else [],
        "queues": dataframe_to_records(queues),
        "reviewers": reviewers_df["reviewer_name"].tolist() if not reviewers_df.empty else [],
        "reviewer_by_group": dataframe_to_records(reviewers_df),
        "error_types": error_types["error_type"].tolist() if not error_types.empty else [],
        "min_date": date_range.get("min_date") if date_range else None,
        "max_date": date_range.get("max_date") if date_range else None,
        "limit_options": [2000, 5000, 10000, MAX_QUERY_LIMIT],
        "issue_filter_options": ["全部问题", "原始错误", "最终错误", "错判", "漏判", "申诉改判"],
    }


@router.get("/filters")
def get_filter_options() -> dict[str, object]:
    payload = _get_filter_options_payload()
    return {
        "ok": True,
        "data": normalize_payload(payload),
    }


@router.get("/schema")
def get_detail_schema() -> dict[str, object]:
    return {
        "ok": True,
        "data": normalize_payload(
            {
                "columns": _build_detail_schema(),
                "default_visible_keys": DEFAULT_VISIBLE_DETAIL_KEYS,
            }
        ),
    }


@router.get("/query")
def query_details(
    date_start: date = Query(...),
    date_end: date = Query(...),
    group_name: str | None = Query(default=None),
    queue_name: str | None = Query(default=None),
    reviewer_name: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    only_issues: bool = Query(default=False),
    issue_filter: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=MAX_QUERY_LIMIT),
) -> dict[str, object]:
    df = _query_detail_rows(
        date_start=date_start,
        date_end=date_end,
        group_name=group_name,
        queue_name=queue_name,
        reviewer_name=reviewer_name,
        error_type=error_type,
        only_issues=only_issues,
        issue_filter=issue_filter,
        limit=limit,
    )
    total_count = _count_detail_rows(
        date_start=date_start,
        date_end=date_end,
        group_name=group_name,
        queue_name=queue_name,
        reviewer_name=reviewer_name,
        error_type=error_type,
        only_issues=only_issues,
        issue_filter=issue_filter,
    )
    returned_count = int(len(df))
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload(
                {
                    "date_start": date_start,
                    "date_end": date_end,
                    "group_name": group_name,
                    "queue_name": queue_name,
                    "reviewer_name": reviewer_name,
                    "error_type": error_type,
                    "only_issues": only_issues,
                    "issue_filter": _normalize_issue_filter(only_issues, issue_filter),
                    "limit": limit,
                }
            ),
            "row_count": returned_count,
            "returned_count": returned_count,
            "total_count": total_count,
            "is_truncated": total_count > returned_count,
            "preview_row_cap": PREVIEW_ROW_CAP,
            "export_row_cap": EXPORT_ROW_CAP,
            "export_expected_count": min(total_count, EXPORT_ROW_CAP),
            "export_will_truncate": total_count > EXPORT_ROW_CAP,
            "default_visible_keys": DEFAULT_VISIBLE_DETAIL_KEYS,
            "columns": normalize_payload(_build_detail_schema()),
            "rows": dataframe_to_records(df),
        },
    }


@router.get("/export")
def export_details(
    date_start: date = Query(...),
    date_end: date = Query(...),
    group_name: str | None = Query(default=None),
    queue_name: str | None = Query(default=None),
    reviewer_name: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    only_issues: bool = Query(default=False),
    issue_filter: str | None = Query(default=None),
    export_limit: int = Query(default=EXPORT_ROW_CAP, ge=1, le=EXPORT_ROW_CAP),
) -> StreamingResponse:
    df = _query_detail_rows(
        date_start=date_start,
        date_end=date_end,
        group_name=group_name,
        queue_name=queue_name,
        reviewer_name=reviewer_name,
        error_type=error_type,
        only_issues=only_issues,
        issue_filter=issue_filter,
        limit=export_limit,
    )
    file_name = f"qa_detail_{date_start.isoformat()}_{date_end.isoformat()}.csv"
    return _to_csv_response(df, file_name)
