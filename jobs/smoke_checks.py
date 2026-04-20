#!/usr/bin/env python3
from __future__ import annotations

import argparse
import compileall
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.dashboard_service import DashboardService
from storage.repository import DashboardRepository


TIMEOUT_SECONDS = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="部署前/后的关键链路冒烟检查。")
    parser.add_argument("--mode", choices=["predeploy", "postdeploy", "full"], default="full")
    parser.add_argument("--selected-date", default=None, help="业务日期，格式 YYYY-MM-DD；默认自动取最新可用日期")
    parser.add_argument("--group-name", default=None, help="指定下钻组别；默认自动选第一个实际组别")
    parser.add_argument("--api-base", default=None, help="部署后 API 基础地址，例如 http://127.0.0.1:8000")
    parser.add_argument("--frontend-base", default=None, help="部署后前端基础地址，例如 http://127.0.0.1:3000")
    parser.add_argument("--streamlit-base", default=None, help="部署后 Streamlit 基础地址，例如 http://127.0.0.1:8501")
    parser.add_argument("--output", default=None, help="可选，把结果写到指定 JSON 文件")
    return parser.parse_args()


def parse_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    return datetime.strptime(raw_value, "%Y-%m-%d").date()


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_result(name: str, status: str, detail: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "extra": extra or {},
    }


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_payload(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): normalize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_payload(item) for item in value]
    return value


def request_response(method: str, url: str, body: dict[str, Any] | None = None) -> requests.Response:
    response = requests.request(method=method.upper(), url=url, timeout=TIMEOUT_SECONDS, json=body)
    response.raise_for_status()
    return response


def request_json(method: str, url: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    response = request_response(method, url, body=body)
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"接口未返回 JSON 对象: {url}")
    return response.status_code, payload


def fetch_json(url: str) -> tuple[int, dict[str, Any]]:
    return request_json("GET", url)


def fetch_text(url: str) -> tuple[int, str]:
    response = request_response("GET", url)
    return response.status_code, response.text


def build_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    base = f"{normalize_base_url(base_url)}{path}"
    if not params:
        return base
    query = urlencode(
        {
            key: value
            for key, value in params.items()
            if value is not None and value != "" and value != []
        },
        doseq=True,
    )
    return f"{base}?{query}" if query else base


def pick_selected_date(service: DashboardService, preferred: date | None) -> tuple[date, date, date]:
    min_date, max_date = service.get_data_date_range()
    selected_date = preferred or max_date
    if selected_date < min_date:
        selected_date = min_date
    if selected_date > max_date:
        selected_date = max_date
    return min_date, max_date, selected_date


def pick_group_name(group_df, preferred: str | None) -> str | None:
    if preferred:
        return preferred
    if group_df is None or group_df.empty or "group_name" not in group_df.columns:
        return None
    actual_df = group_df[group_df["group_name"].fillna("") != "B组"]
    if actual_df.empty:
        return None
    return str(actual_df.iloc[0]["group_name"])


def run_python_compile_check() -> dict[str, Any]:
    targets = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "api",
        PROJECT_ROOT / "jobs",
        PROJECT_ROOT / "pages",
        PROJECT_ROOT / "services",
        PROJECT_ROOT / "storage",
    ]
    ok = True
    checked_targets: list[str] = []
    for target in targets:
        checked_targets.append(str(target.relative_to(PROJECT_ROOT)))
        if target.is_file():
            ok = compileall.compile_file(str(target), quiet=1) and ok
        elif target.is_dir():
            ok = compileall.compile_dir(str(target), quiet=1) and ok
    status = "passed" if ok else "failed"
    detail = "Python 代码编译通过" if ok else "存在 Python 语法/编译错误"
    return build_result("python_compile", status, detail, {"targets": checked_targets})


def run_repository_smoke(selected_date: date | None, group_name: str | None) -> list[dict[str, Any]]:
    service = DashboardService()
    repo = DashboardRepository()
    min_date, max_date, picked_date = pick_selected_date(service, selected_date)

    payload = service.load_dashboard_payload("day", picked_date)
    group_df = payload.get("group_df")
    group_display_df = payload.get("group_display_df")
    alerts_df = payload.get("alerts_df")

    if group_df is None or group_df.empty:
        return [
            build_result(
                "repository_dashboard_payload",
                "failed",
                "首页主 payload 没拿到组别数据，无法继续做数据链路冒烟。",
                {"selected_date": picked_date.isoformat()},
            )
        ]

    chosen_group = pick_group_name(group_df, group_name)
    queue_start = max(min_date, picked_date - timedelta(days=6))
    queue_payload = service.load_queue_overview_payload("day", queue_start, picked_date, chosen_group)
    detail_payload = service.load_group_payload("day", picked_date, chosen_group, None, None) if chosen_group else None
    issue_df = repo.get_issue_samples("day", picked_date, chosen_group, limit=5) if chosen_group else None

    results = [
        build_result(
            "repository_dashboard_payload",
            "passed",
            "首页 payload 读取通过。",
            {
                "selected_date": picked_date.isoformat(),
                "group_rows": int(len(group_df)),
                "group_display_rows": int(len(group_display_df)) if group_display_df is not None else 0,
                "alert_rows": int(len(alerts_df)) if alerts_df is not None else 0,
            },
        ),
        build_result(
            "repository_queue_overview",
            "passed",
            "队列概览与趋势范围查询通过。",
            {
                "group_name": chosen_group,
                "start_date": queue_start.isoformat(),
                "end_date": picked_date.isoformat(),
                "queue_rows": int(len(queue_payload["queue_df"])),
                "trend_rows": int(len(queue_payload["trend_df"])),
            },
        ),
    ]

    if chosen_group and detail_payload is not None:
        results.append(
            build_result(
                "repository_group_detail",
                "passed",
                "组别下钻 payload 读取通过。",
                {
                    "group_name": chosen_group,
                    "queue_rows": int(len(detail_payload.get("queue_df", []))),
                    "auditor_rows": int(len(detail_payload.get("auditor_df", []))),
                    "sample_rows": int(len(detail_payload.get("sample_df", []))),
                    "training_recovery_rows": int(len(detail_payload.get("training_recovery_df", []))),
                },
            )
        )
        results.append(
            build_result(
                "repository_issue_samples",
                "passed",
                "问题样本查询通过。",
                {
                    "group_name": chosen_group,
                    "sample_rows": int(len(issue_df)) if issue_df is not None else 0,
                },
            )
        )

    return results


def run_predeploy_checks(selected_date: date | None, group_name: str | None) -> list[dict[str, Any]]:
    results = [run_python_compile_check()]
    try:
        results.extend(run_repository_smoke(selected_date, group_name))
    except Exception as exc:
        results.append(build_result("repository_smoke", "failed", f"数据链路冒烟失败：{exc}"))
    return results


def validate_details_query_payload(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    required_keys = [
        "row_count",
        "returned_count",
        "total_count",
        "is_truncated",
        "preview_row_cap",
        "export_row_cap",
        "export_expected_count",
        "export_will_truncate",
        "default_visible_keys",
        "columns",
        "rows",
    ]
    missing_keys = [key for key in required_keys if key not in data]

    rows = data.get("rows", []) if isinstance(data, dict) else []
    columns = data.get("columns", []) if isinstance(data, dict) else []
    default_visible_keys = data.get("default_visible_keys", []) if isinstance(data, dict) else []
    returned_count = to_int(data.get("returned_count")) if isinstance(data, dict) else 0
    total_count = to_int(data.get("total_count")) if isinstance(data, dict) else 0
    row_count = to_int(data.get("row_count")) if isinstance(data, dict) else 0
    preview_row_cap = to_int(data.get("preview_row_cap")) if isinstance(data, dict) else 0
    export_row_cap = to_int(data.get("export_row_cap")) if isinstance(data, dict) else 0
    export_expected_count = to_int(data.get("export_expected_count")) if isinstance(data, dict) else 0
    is_truncated = bool(data.get("is_truncated")) if isinstance(data, dict) else False
    export_will_truncate = bool(data.get("export_will_truncate")) if isinstance(data, dict) else False

    validation_errors: list[str] = []
    if row_count != returned_count:
        validation_errors.append("row_count 与 returned_count 不一致")
    if not isinstance(rows, list):
        validation_errors.append("rows 不是列表")
    elif len(rows) != returned_count:
        validation_errors.append("rows 行数与 returned_count 不一致")
    if total_count < returned_count:
        validation_errors.append("total_count 小于 returned_count")
    if is_truncated != (total_count > returned_count):
        validation_errors.append("is_truncated 与 total_count/returned_count 关系不一致")
    if preview_row_cap <= 0:
        validation_errors.append("preview_row_cap 必须大于 0")
    if export_row_cap < max(preview_row_cap, 1):
        validation_errors.append("export_row_cap 不应小于 preview_row_cap")
    if export_expected_count != min(total_count, export_row_cap):
        validation_errors.append("export_expected_count 与 total_count/export_row_cap 不一致")
    if export_will_truncate != (total_count > export_row_cap):
        validation_errors.append("export_will_truncate 与 total_count/export_row_cap 关系不一致")
    if not isinstance(columns, list) or not columns:
        validation_errors.append("columns 为空或不是列表")
    if not isinstance(default_visible_keys, list) or not default_visible_keys:
        validation_errors.append("default_visible_keys 为空或不是列表")

    return len(missing_keys) == 0 and len(validation_errors) == 0, {
        "row_count": row_count,
        "returned_count": returned_count,
        "total_count": total_count,
        "is_truncated": is_truncated,
        "preview_row_cap": preview_row_cap,
        "export_row_cap": export_row_cap,
        "export_expected_count": export_expected_count,
        "export_will_truncate": export_will_truncate,
        "default_visible_key_count": len(default_visible_keys) if isinstance(default_visible_keys, list) else 0,
        "column_count": len(columns) if isinstance(columns, list) else 0,
        "missing_keys": missing_keys,
        "validation_errors": validation_errors,
    }


def run_frontend_details_semantics_check(frontend_base: str, api_base: str, selected_date: date | None) -> dict[str, Any]:
    service = DashboardService()
    _, _, picked_date = pick_selected_date(service, selected_date)
    api_root = normalize_base_url(api_base)
    _, meta_payload = fetch_json(build_url(api_root, "/api/v1/meta/date-range"))
    meta_data = meta_payload.get("data", {}) if isinstance(meta_payload, dict) else {}
    effective_date = parse_date(str(meta_data.get("default_selected_date") or picked_date.isoformat())) or picked_date

    _, overview_payload = fetch_json(
        build_url(
            api_root,
            "/api/v1/dashboard/overview",
            {"grain": "day", "selected_date": effective_date.isoformat()},
        )
    )
    overview_data = overview_payload.get("data", {}) if isinstance(overview_payload, dict) else {}
    group_rows = overview_data.get("group_df") if isinstance(overview_data, dict) else []
    chosen_group = None
    if isinstance(group_rows, list):
        preferred_groups = [
            str(row.get("group_name", "")).strip()
            for row in group_rows
            if str(row.get("group_name", "")).strip() and str(row.get("group_name", "")).strip() != "B组"
        ]
        fallback_groups = [str(row.get("group_name", "")).strip() for row in group_rows if str(row.get("group_name", "")).strip()]
        chosen_group = (preferred_groups or fallback_groups or [None])[0]

    if not chosen_group:
        return build_result("frontend_details_semantics", "skipped", "首页未返回可下钻组别，跳过明细查询语义页面只读冒烟。")

    page_url = build_url(
        normalize_base_url(frontend_base),
        "/details",
        {
            "date_start": effective_date.isoformat(),
            "date_end": effective_date.isoformat(),
            "group_name": chosen_group,
        },
    )
    status_code, html = fetch_text(page_url)
    required_keywords = [
        "当前命中总数",
        "接口返回行数",
        "页面预览行数",
        "CSV 导出范围",
    ]
    missing_keywords = [kw for kw in required_keywords if kw not in html]
    detail = f"/details 明细语义页返回 {status_code}"
    if missing_keywords:
        detail += "，但四层结果口径文案不完整"
    return build_result(
        "frontend_details_semantics",
        "passed" if not missing_keywords else "failed",
        detail,
        {
            "group_name": chosen_group,
            "selected_date": effective_date.isoformat(),
            "page_url": page_url,
            "matched_keywords": [kw for kw in required_keywords if kw in html],
            "missing_keywords": missing_keywords,
        },
    )


def run_api_postdeploy_checks(api_base: str, selected_date: date | None) -> list[dict[str, Any]]:
    service = DashboardService()
    _, _, picked_date = pick_selected_date(service, selected_date)
    base_url = normalize_base_url(api_base)
    results: list[dict[str, Any]] = []

    status_code, health_payload = fetch_json(build_url(base_url, "/api/health"))
    health_ok = bool(health_payload.get("ok"))
    results.append(
        build_result(
            "api_health",
            "passed" if health_ok else "failed",
            f"/api/health 返回 {status_code}",
            {"payload": health_payload},
        )
    )

    _, meta_payload = fetch_json(build_url(base_url, "/api/v1/meta/date-range"))
    meta_data = meta_payload.get("data", {}) if isinstance(meta_payload, dict) else {}
    effective_date = parse_date(str(meta_data.get("default_selected_date") or picked_date.isoformat())) or picked_date

    _, overview_payload = fetch_json(
        build_url(
            base_url,
            "/api/v1/dashboard/overview",
            {"grain": "day", "selected_date": effective_date.isoformat()},
        )
    )
    overview_data = overview_payload.get("data", {}) if isinstance(overview_payload, dict) else {}
    group_rows = overview_data.get("group_df") if isinstance(overview_data, dict) else []
    chosen_group = None
    if isinstance(group_rows, list):
        preferred_groups = [
            str(row.get("group_name", "")).strip()
            for row in group_rows
            if str(row.get("group_name", "")).strip() and str(row.get("group_name", "")).strip() != "B组"
        ]
        fallback_groups = [str(row.get("group_name", "")).strip() for row in group_rows if str(row.get("group_name", "")).strip()]
        chosen_group = (preferred_groups or fallback_groups or [None])[0]

    results.append(
        build_result(
            "api_overview",
            "passed",
            "首页 overview 接口可用。",
            {
                "selected_date": effective_date.isoformat(),
                "group_rows": len(group_rows) if isinstance(group_rows, list) else 0,
                "chosen_group": chosen_group,
            },
        )
    )

    _, alerts_payload = fetch_json(
        build_url(
            base_url,
            "/api/v1/dashboard/alerts",
            {"grain": "day", "selected_date": effective_date.isoformat()},
        )
    )
    alert_items = alerts_payload.get("data", {}).get("items", []) if isinstance(alerts_payload, dict) else []
    chosen_alert_id = None
    if isinstance(alert_items, list):
        for item in alert_items:
            candidate_id = str(item.get("alert_id", "")).strip()
            if candidate_id:
                chosen_alert_id = candidate_id
                break
    results.append(
        build_result(
            "api_alerts",
            "passed",
            "告警列表接口可用。",
            {
                "alert_rows": len(alert_items) if isinstance(alert_items, list) else 0,
                "chosen_alert_id": chosen_alert_id,
            },
        )
    )

    _, bulk_update_payload = request_json(
        "PATCH",
        build_url(base_url, "/api/v1/dashboard/alerts/bulk-update"),
        {
            "alert_ids": [],
            "alert_status": "claimed",
            "owner_name": "smoke-check",
            "handle_note": "noop smoke check",
        },
    )
    bulk_update_data = bulk_update_payload.get("data", {}) if isinstance(bulk_update_payload, dict) else {}
    bulk_update_ok = int(bulk_update_data.get("updated_count") or 0) == 0
    results.append(
        build_result(
            "api_alerts_bulk_update",
            "passed" if bulk_update_ok else "failed",
            "告警批量流转接口可用（空列表 noop 校验）。",
            normalize_payload(bulk_update_data) if isinstance(bulk_update_data, dict) else {},
        )
    )

    if chosen_alert_id:
        _, alert_detail_payload = fetch_json(
            build_url(
                base_url,
                f"/api/v1/dashboard/alerts/{requests.utils.quote(chosen_alert_id, safe='')}",
                {"grain": "day", "selected_date": effective_date.isoformat()},
            )
        )
        alert_detail_data = alert_detail_payload.get("data", {}) if isinstance(alert_detail_payload, dict) else {}
        alert_history = alert_detail_data.get("history", []) if isinstance(alert_detail_data, dict) else []
        required_detail_keys = [
            "alert_status_label",
            "history",
            "suggestion",
            "alert_sample_df",
            "alert_sample_scope",
            "sla_label",
        ]
        missing_detail_keys = [key for key in required_detail_keys if key not in alert_detail_data]
        detail_ok = len(missing_detail_keys) == 0
        results.append(
            build_result(
                "api_alert_detail",
                "passed" if detail_ok else "failed",
                "告警详情接口可用，且首页详情闭环所需字段已齐。" if detail_ok else "告警详情接口可用，但首页详情闭环所需字段不完整。",
                {
                    "alert_id": chosen_alert_id,
                    "history_rows": len(alert_history) if isinstance(alert_history, list) else 0,
                    "alert_sample_rows": len(alert_detail_data.get("alert_sample_df", [])) if isinstance(alert_detail_data.get("alert_sample_df", []), list) else 0,
                    "sample_scope": alert_detail_data.get("alert_sample_scope"),
                    "missing_keys": missing_detail_keys,
                },
            )
        )
    else:
        results.append(build_result("api_alert_detail", "skipped", "当日无告警数据，跳过告警详情接口冒烟。"))

    _, filters_payload = fetch_json(build_url(base_url, "/api/v1/details/filters"))
    _, schema_payload = fetch_json(build_url(base_url, "/api/v1/details/schema"))
    results.append(
        build_result(
            "api_details_meta",
            "passed",
            "明细页 schema / filters 接口可用。",
            {
                "filter_keys": sorted(list(filters_payload.get("data", {}).keys())) if isinstance(filters_payload, dict) else [],
                "schema_columns": len(schema_payload.get("data", {}).get("columns", [])) if isinstance(schema_payload, dict) else 0,
            },
        )
    )

    if chosen_group:
        detail_params = {"grain": "day", "selected_date": effective_date.isoformat(), "group_name": chosen_group}
        _, detail_payload = fetch_json(build_url(base_url, "/api/v1/dashboard/group-detail", detail_params))
        detail_data = detail_payload.get("data", {}) if isinstance(detail_payload, dict) else {}
        results.append(
            build_result(
                "api_group_detail",
                "passed",
                "首页组别下钻接口可用。",
                {
                    "group_name": chosen_group,
                    "queue_rows": len(detail_data.get("queue_df", [])),
                    "auditor_rows": len(detail_data.get("auditor_df", [])),
                    "sample_rows": len(detail_data.get("sample_df", [])),
                },
            )
        )

        detail_query_params = {
            "date_start": effective_date.isoformat(),
            "date_end": effective_date.isoformat(),
            "group_name": chosen_group,
            "limit": 50,
        }
        _, query_payload = fetch_json(build_url(base_url, "/api/v1/details/query", detail_query_params))
        query_ok, query_extra = validate_details_query_payload(query_payload)
        results.append(
            build_result(
                "api_details_query",
                "passed" if query_ok else "failed",
                "明细查询接口可用，且返回/预览/导出口径一致。" if query_ok else "明细查询接口可用，但返回/预览/导出口径不一致。",
                {
                    "group_name": chosen_group,
                    **query_extra,
                },
            )
        )

        export_response = request_response("GET", build_url(base_url, "/api/v1/details/export", detail_query_params))
        export_text = export_response.content.decode("utf-8-sig", errors="ignore")
        export_first_line = export_text.splitlines()[0] if export_text.splitlines() else ""
        content_disposition = export_response.headers.get("Content-Disposition", "")
        export_ok = "attachment;" in content_disposition.lower() and "qa_detail_" in content_disposition and bool(export_first_line)
        results.append(
            build_result(
                "api_details_export",
                "passed" if export_ok else "failed",
                "明细导出接口可用。",
                {
                    "group_name": chosen_group,
                    "content_disposition": content_disposition,
                    "header_preview": export_first_line,
                },
            )
        )
    else:
        results.append(build_result("api_group_detail", "skipped", "首页未返回可下钻组别，跳过组别下钻接口冒烟。"))
        results.append(build_result("api_details_query", "skipped", "首页未返回可下钻组别，跳过明细查询接口冒烟。"))
        results.append(build_result("api_details_export", "skipped", "首页未返回可下钻组别，跳过明细导出接口冒烟。"))

    _, newcomers_summary_payload = fetch_json(build_url(base_url, "/api/v1/newcomers/summary"))
    newcomers_summary_data = newcomers_summary_payload.get("data", {}) if isinstance(newcomers_summary_payload, dict) else {}
    batch_items = newcomers_summary_data.get("batches", []) if isinstance(newcomers_summary_data, dict) else []
    unmatched_items = newcomers_summary_data.get("unmatched", []) if isinstance(newcomers_summary_data, dict) else []
    chosen_batch_name = None
    if isinstance(batch_items, list):
        for item in batch_items:
            candidate_batch = str(item.get("batch_name", "")).strip()
            if candidate_batch:
                chosen_batch_name = candidate_batch
                break
    results.append(
        build_result(
            "api_newcomers_summary",
            "passed",
            "新人总览接口可用。",
            {
                "batch_rows": len(batch_items) if isinstance(batch_items, list) else 0,
                "unmatched_rows": len(unmatched_items) if isinstance(unmatched_items, list) else 0,
                "chosen_batch_name": chosen_batch_name,
            },
        )
    )

    newcomer_members_params = {"batch_names": [chosen_batch_name]} if chosen_batch_name else None
    _, newcomer_members_payload = fetch_json(build_url(base_url, "/api/v1/newcomers/members", newcomer_members_params))
    newcomer_members_data = newcomer_members_payload.get("data", {}) if isinstance(newcomer_members_payload, dict) else {}
    newcomer_member_items = newcomer_members_data.get("items", []) if isinstance(newcomer_members_data, dict) else []
    chosen_reviewer_alias = None
    if isinstance(newcomer_member_items, list):
        for item in newcomer_member_items:
            candidate_alias = str(item.get("reviewer_alias", "")).strip()
            if candidate_alias:
                chosen_reviewer_alias = candidate_alias
                break
    results.append(
        build_result(
            "api_newcomers_members",
            "passed",
            "新人成员接口可用。",
            {
                "row_count": len(newcomer_member_items) if isinstance(newcomer_member_items, list) else 0,
                "chosen_reviewer_alias": chosen_reviewer_alias,
            },
        )
    )

    newcomer_query_params: dict[str, Any] = {}
    if chosen_batch_name:
        newcomer_query_params["batch_names"] = [chosen_batch_name]
    if chosen_reviewer_alias:
        newcomer_query_params["reviewer_aliases"] = [chosen_reviewer_alias]

    if newcomer_query_params:
        _, newcomer_daily_payload = fetch_json(build_url(base_url, "/api/v1/newcomers/qa-daily", newcomer_query_params))
        newcomer_daily_items = newcomer_daily_payload.get("data", {}).get("items", []) if isinstance(newcomer_daily_payload, dict) else []
        results.append(
            build_result(
                "api_newcomers_qa_daily",
                "passed",
                "新人日趋势接口可用。",
                {
                    "row_count": len(newcomer_daily_items) if isinstance(newcomer_daily_items, list) else 0,
                    "filters": newcomer_query_params,
                },
            )
        )

        _, newcomer_error_payload = fetch_json(build_url(base_url, "/api/v1/newcomers/error-summary", newcomer_query_params))
        newcomer_error_items = newcomer_error_payload.get("data", {}).get("items", []) if isinstance(newcomer_error_payload, dict) else []
        results.append(
            build_result(
                "api_newcomers_error_summary",
                "passed",
                "新人错误分布接口可用。",
                {
                    "row_count": len(newcomer_error_items) if isinstance(newcomer_error_items, list) else 0,
                    "filters": newcomer_query_params,
                },
            )
        )
    else:
        results.append(build_result("api_newcomers_qa_daily", "skipped", "未拿到可用批次或 reviewer_alias，跳过新人日趋势接口冒烟。"))
        results.append(build_result("api_newcomers_error_summary", "skipped", "未拿到可用批次或 reviewer_alias，跳过新人错误分布接口冒烟。"))

    if chosen_reviewer_alias:
        _, newcomer_formal_payload = fetch_json(
            build_url(base_url, "/api/v1/newcomers/formal-daily", {"reviewer_aliases": [chosen_reviewer_alias]})
        )
        newcomer_formal_items = newcomer_formal_payload.get("data", {}).get("items", []) if isinstance(newcomer_formal_payload, dict) else []
        results.append(
            build_result(
                "api_newcomers_formal_daily",
                "passed",
                "新人正式阶段趋势接口可用。",
                {
                    "row_count": len(newcomer_formal_items) if isinstance(newcomer_formal_items, list) else 0,
                    "reviewer_alias": chosen_reviewer_alias,
                },
            )
        )

        _, newcomer_person_payload = fetch_json(
            build_url(base_url, "/api/v1/newcomers/person-detail", {"reviewer_alias": chosen_reviewer_alias, "limit": 20})
        )
        newcomer_person_items = newcomer_person_payload.get("data", {}).get("items", []) if isinstance(newcomer_person_payload, dict) else []
        results.append(
            build_result(
                "api_newcomers_person_detail",
                "passed",
                "新人个人明细接口可用。",
                {
                    "row_count": len(newcomer_person_items) if isinstance(newcomer_person_items, list) else 0,
                    "reviewer_alias": chosen_reviewer_alias,
                },
            )
        )
    else:
        results.append(build_result("api_newcomers_formal_daily", "skipped", "未拿到可用 reviewer_alias，跳过新人正式阶段接口冒烟。"))
        results.append(build_result("api_newcomers_person_detail", "skipped", "未拿到可用 reviewer_alias，跳过新人个人明细接口冒烟。"))

    # ── Phase 5: 内检(internal)模块 6 个端点冒烟 ──
    _, internal_summary_payload = fetch_json(build_url(base_url, "/api/v1/internal/summary",
                                                         {"selected_date": effective_date.isoformat(), "with_prev": "true"}))
    internal_summary_data = internal_summary_payload.get("data", {}) if isinstance(internal_summary_payload, dict) else {}
    internal_metrics = internal_summary_data.get("metrics") if isinstance(internal_summary_data, dict) else None
    if internal_metrics and int(internal_metrics.get("qa_cnt", 0)) > 0:
        results.append(
            build_result(
                "api_internal_summary",
                "passed",
                "内检核心指标接口可用。",
                {
                    "qa_cnt": int(internal_metrics.get("qa_cnt", 0)),
                    "raw_accuracy_rate": float(internal_metrics.get("raw_accuracy_rate", 0)),
                    "final_accuracy_rate": float(internal_metrics.get("final_accuracy_rate", 0)),
                    "target_rate": str(internal_summary_data.get("target_rate")),
                },
            )
        )
        # 队列排名
        _, internal_queues_payload = fetch_json(build_url(base_url, "/api/v1/internal/queues",
                                                            {"selected_date": effective_date.isoformat()}))
        internal_queue_items = internal_queues_payload.get("data", {}).get("items", []) if isinstance(internal_queues_payload, dict) else []
        results.append(
            build_result(
                "api_internal_queues",
                "passed",
                "内检队列排名接口可用。",
                {"queue_count": len(internal_queue_items) if isinstance(internal_queue_items, list) else 0},
            )
        )

        # 趋势
        trend_start = (effective_date - timedelta(days=6)).isoformat()
        _, internal_trend_payload = fetch_json(build_url(base_url, "/api/v1/internal/trend",
                                                          {"start_date": trend_start, "end_date": effective_date.isoformat()}))
        internal_trend_series = internal_trend_payload.get("data", {}).get("series", []) if isinstance(internal_trend_payload, dict) else []
        results.append(
            build_result(
                "api_internal_trend",
                "passed",
                "内检趋势接口可用。",
                {
                    "trend_points": len(internal_trend_series) if isinstance(internal_trend_series, list) else 0,
                    "date_range": f"{trend_start} ~ {effective_date.isoformat()}",
                },
            )
        )

        # 审核人
        _, internal_reviewers_payload = fetch_json(build_url(base_url, "/api/v1/internal/reviewers",
                                                              {"selected_date": effective_date.isoformat(), "limit": "30"}))
        internal_reviewer_items = internal_reviewers_payload.get("data", {}).get("items", []) if isinstance(internal_reviewers_payload, dict) else []
        results.append(
            build_result(
                "api_internal_reviewers",
                "passed",
                "内检审核人明细接口可用。",
                {"reviewer_count": len(internal_reviewer_items) if isinstance(internal_reviewer_items, list) else 0},
            )
        )

        # 错误标签
        _, internal_error_types_payload = fetch_json(build_url(base_url, "/api/v1/internal/error-types",
                                                                 {"selected_date": effective_date.isoformat(), "top_n": "10"}))
        internal_error_items = internal_error_types_payload.get("data", {}).get("items", []) if isinstance(internal_error_types_payload, dict) else []
        total_errors = int(internal_error_types_payload.get("data", {}).get("total_errors", 0)) if isinstance(internal_error_types_payload, dict) else 0
        results.append(
            build_result(
                "api_internal_error_types",
                "passed",
                "内检错误标签接口可用。",
                {
                    "label_count": len(internal_error_items) if isinstance(internal_error_items, list) else 0,
                    "total_errors": total_errors,
                },
            )
        )

        # 质检员工作量
        _, internal_qa_owners_payload = fetch_json(build_url(base_url, "/api/v1/internal/qa-owners",
                                                               {"selected_date": effective_date.isoformat(), "limit": "20"}))
        internal_qa_owner_items = internal_qa_owners_payload.get("data", {}).get("items", []) if isinstance(internal_qa_owners_payload, dict) else []
        results.append(
            build_result(
                "api_internal_qa_owners",
                "passed",
                "内检质检员工作量接口可用。",
                {"owner_count": len(internal_qa_owner_items) if isinstance(internal_qa_owner_items, list) else 0},
            )
        )
    elif internal_metrics is not None and int(internal_metrics.get("qa_cnt", 0)) == 0:
        results.append(build_result("api_internal_summary", "warn", f"内检接口可用，但日期 {effective_date.isoformat()} 无内检数据（qa_cnt=0）。"))
        for name in ["api_internal_queues", "api_internal_trend", "api_internal_reviewers",
                     "api_internal_error_types", "api_internal_qa_owners"]:
            results.append(build_result(name, "skipped", "当日无内检数据，跳过该端点冒烟。"))
    else:
        results.append(build_result("api_internal_summary", "failed", "内检核心指标接口返回异常或 metrics 为空。", normalize_payload(internal_summary_data) if isinstance(internal_summary_data, dict) else {}))
        for name in ["api_internal_queues", "api_internal_trend", "api_internal_reviewers",
                     "api_internal_error_types", "api_internal_qa_owners"]:
            results.append(build_result(name, "skipped", "summary 接口异常，跳过其余内检端点冒烟。"))

    return results


def run_html_postdeploy_check(name: str, base_url: str, path: str, expected_keywords: list[str]) -> dict[str, Any]:
    status_code, html = fetch_text(f"{normalize_base_url(base_url)}{path}")
    passed = any(keyword in html for keyword in expected_keywords) if expected_keywords else True
    detail = f"{path or '/'} 返回 {status_code}"
    if expected_keywords and not passed:
        detail += "，但未命中预期关键词"
    return build_result(
        name,
        "passed" if passed else "failed",
        detail,
        {"path": path or "/", "matched_keywords": [kw for kw in expected_keywords if kw in html]},
    )


def run_html_postdeploy_check_all(name: str, base_url: str, path: str, expected_keywords: list[str]) -> dict[str, Any]:
    status_code, html = fetch_text(f"{normalize_base_url(base_url)}{path}")
    missing_keywords = [kw for kw in expected_keywords if kw not in html]
    detail = f"{path or '/'} 返回 {status_code}"
    if missing_keywords:
        detail += "，且缺少关键文案"
    return build_result(
        name,
        "passed" if not missing_keywords else "failed",
        detail,
        {
            "path": path or "/",
            "matched_keywords": [kw for kw in expected_keywords if kw in html],
            "missing_keywords": missing_keywords,
        },
    )


def run_frontend_dashboard_alert_detail_check(frontend_base: str, api_base: str, selected_date: date | None) -> dict[str, Any]:
    service = DashboardService()
    _, _, picked_date = pick_selected_date(service, selected_date)
    api_root = normalize_base_url(api_base)
    _, meta_payload = fetch_json(build_url(api_root, "/api/v1/meta/date-range"))
    meta_data = meta_payload.get("data", {}) if isinstance(meta_payload, dict) else {}
    effective_date = parse_date(str(meta_data.get("default_selected_date") or picked_date.isoformat())) or picked_date

    _, alerts_payload = fetch_json(
        build_url(
            api_root,
            "/api/v1/dashboard/alerts",
            {"grain": "day", "selected_date": effective_date.isoformat()},
        )
    )
    alert_items = alerts_payload.get("data", {}).get("items", []) if isinstance(alerts_payload, dict) else []
    chosen_alert: dict[str, Any] | None = None
    if isinstance(alert_items, list):
        for item in alert_items:
            if isinstance(item, dict) and str(item.get("alert_id", "")).strip():
                chosen_alert = item
                break

    if not chosen_alert:
        return build_result("frontend_home_alert_detail", "skipped", "当日无告警数据，跳过首页告警详情闭环页面冒烟。")

    chosen_alert_id = str(chosen_alert.get("alert_id", "")).strip()
    chosen_alert_group = str(chosen_alert.get("alert_group_name", "")).strip() or None
    page_url = build_url(
        normalize_base_url(frontend_base),
        "/",
        {
            "grain": "day",
            "selected_date": effective_date.isoformat(),
            "alert_id": chosen_alert_id,
            "group_name": chosen_alert_group,
        },
    )
    status_code, html = fetch_text(page_url)
    required_keywords = [
        "告警详情闭环",
        "快捷处置与建议",
        "处理历史",
        "这条告警现在可以直接在首页认领 / 解决 / 忽略 / 重新打开",
        "跳转到明细查询（保留返回链路）",
    ]
    missing_keywords = [kw for kw in required_keywords if kw not in html]
    detail = f"/ 首页告警详情页返回 {status_code}"
    if missing_keywords:
        detail += "，但首页详情闭环关键文案不完整"
    return build_result(
        "frontend_home_alert_detail",
        "passed" if not missing_keywords else "failed",
        detail,
        {
            "alert_id": chosen_alert_id,
            "group_name": chosen_alert_group,
            "selected_date": effective_date.isoformat(),
            "page_url": page_url,
            "matched_keywords": [kw for kw in required_keywords if kw in html],
            "missing_keywords": missing_keywords,
        },
    )


def run_frontend_smoke_page_check(frontend_base: str) -> dict[str, Any]:
    """抓 /smoke 页的 HTML，保证这个"前端自检页"本身不回归。

    两层断言：
      1. 页面自身可达：稳定 shell 文案（无论接口 ok/warn/error 都会渲染）。
      2. 页面结论：如果出现"❌ 有接口失败"字样，本次 postdeploy 视作 failed，
         因为 /smoke 页自己已经判定核心接口挂了。
         出现"⚠️"算 warn 不算 failed，避免数仓当天空库就把 CI 卡死。
    """
    path = "/smoke"
    status_code, html = fetch_text(f"{normalize_base_url(frontend_base)}{path}")
    shell_keywords = ["在线冒烟", "总检查数", "整体结论", "明细结果"]
    missing_shell = [kw for kw in shell_keywords if kw not in html]
    has_error_verdict = "❌ 有接口失败" in html
    has_warn_verdict = "⚠️ 部分接口有数据缺口" in html

    if missing_shell:
        return build_result(
            "frontend_smoke_page",
            "failed",
            f"/smoke 返回 {status_code}，但页面骨架关键文案不完整",
            {
                "path": path,
                "matched_keywords": [kw for kw in shell_keywords if kw in html],
                "missing_keywords": missing_shell,
            },
        )
    if has_error_verdict:
        return build_result(
            "frontend_smoke_page",
            "failed",
            f"/smoke 返回 {status_code}，页面自判定有核心接口失败",
            {
                "path": path,
                "verdict": "error",
                "matched_keywords": shell_keywords,
            },
        )
    return build_result(
        "frontend_smoke_page",
        "passed",
        f"/smoke 返回 {status_code}，页面结论 {'warn' if has_warn_verdict else 'ok'}",
        {
            "path": path,
            "verdict": "warn" if has_warn_verdict else "ok",
            "matched_keywords": shell_keywords,
        },
    )


def run_postdeploy_checks(
    selected_date: date | None,
    api_base: str | None,
    frontend_base: str | None,
    streamlit_base: str | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    if api_base:
        try:
            results.extend(run_api_postdeploy_checks(api_base, selected_date))
        except Exception as exc:
            results.append(build_result("api_postdeploy", "failed", f"API 部署后冒烟失败：{exc}"))
    else:
        results.append(build_result("api_postdeploy", "skipped", "未提供 --api-base，跳过 API 部署后冒烟。"))

    if frontend_base:
        try:
            results.append(
                run_html_postdeploy_check(
                    "frontend_home",
                    frontend_base,
                    "/",
                    ["首页首屏迁移版", "经营驾驶舱", "QC统一看板"],
                )
            )
            results.append(
                run_html_postdeploy_check_all(
                    "frontend_home_shell",
                    frontend_base,
                    "/",
                    ["首页总览", "告警批量流转"],
                )
            )
            if api_base:
                results.append(run_frontend_dashboard_alert_detail_check(frontend_base, api_base, selected_date))
            else:
                results.append(
                    build_result(
                        "frontend_home_alert_detail",
                        "skipped",
                        "未提供 --api-base，无法定位首页告警详情页面，跳过只读闭环冒烟。",
                    )
                )
            results.append(
                run_html_postdeploy_check(
                    "frontend_details",
                    frontend_base,
                    "/details",
                    ["明细查询", "导出", "筛选"],
                )
            )
            if api_base:
                results.append(run_frontend_details_semantics_check(frontend_base, api_base, selected_date))
            else:
                results.append(
                    build_result(
                        "frontend_details_semantics",
                        "skipped",
                        "未提供 --api-base，无法定位带真实筛选条件的明细语义页，跳过只读冒烟。",
                    )
                )
            results.append(
                run_html_postdeploy_check(
                    "frontend_newcomers",
                    frontend_base,
                    "/newcomers",
                    ["新人追踪", "批次", "培训期"],
                )
            )
            results.append(
                run_html_postdeploy_check(
                    "frontend_internal",
                    frontend_base,
                    "/internal",
                    ["内检看板", "队列正确率排名", "审核人分析"],
                )
            )
            results.append(run_frontend_smoke_page_check(frontend_base))
        except Exception as exc:
            results.append(build_result("frontend_postdeploy", "failed", f"前端部署后冒烟失败：{exc}"))
    else:
        results.append(build_result("frontend_postdeploy", "skipped", "未提供 --frontend-base，跳过前端部署后冒烟。"))

    if streamlit_base:
        try:
            results.append(
                run_html_postdeploy_check(
                    "streamlit_home",
                    streamlit_base,
                    "/",
                    ["streamlit", "质培运营看板"],
                )
            )
        except Exception as exc:
            results.append(build_result("streamlit_postdeploy", "failed", f"Streamlit 部署后冒烟失败：{exc}"))
    else:
        results.append(build_result("streamlit_postdeploy", "skipped", "未提供 --streamlit-base，跳过 Streamlit 部署后冒烟。"))

    return results


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for item in results:
        status = item.get("status", "failed")
        counts[status] = counts.get(status, 0) + 1
    return {
        "counts": counts,
        "success": counts.get("failed", 0) == 0,
    }


def print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 72)
    print("QC 看板部署冒烟结果")
    print("=" * 72)
    print(
        f"通过 {summary['counts'].get('passed', 0)} | 失败 {summary['counts'].get('failed', 0)} | 跳过 {summary['counts'].get('skipped', 0)}"
    )
    print("-" * 72)
    for item in report["results"]:
        print(f"[{item['status'].upper():7}] {item['name']}: {item['detail']}")
    print("-" * 72)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    args = parse_args()
    selected_date = parse_date(args.selected_date)
    results: list[dict[str, Any]] = []

    if args.mode in {"predeploy", "full"}:
        results.extend(run_predeploy_checks(selected_date, args.group_name))
    if args.mode in {"postdeploy", "full"}:
        results.extend(run_postdeploy_checks(selected_date, args.api_base, args.frontend_base, args.streamlit_base))

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "results": results,
        "summary": summarize(results),
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print_report(report)
    return 0 if report["summary"]["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
