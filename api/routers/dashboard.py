from __future__ import annotations

import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.exceptions import DataNotFoundError, ValidationError
from api.serializers import dataframe_to_records, normalize_payload
from services.dashboard_service import DashboardService
from utils.cache import get_cache

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
service = DashboardService()
cache = get_cache()
_log = logging.getLogger("api.cache")


class AlertStatusUpdate(BaseModel):
    alert_status: Literal["open", "claimed", "ignored", "resolved"]
    owner_name: str | None = Field(default=None, description="处理人 / owner")
    handle_note: str | None = Field(default=None, description="处理备注")


class AlertBulkStatusUpdate(AlertStatusUpdate):
    alert_ids: list[str] = Field(default_factory=list, description="需要批量流转的 alert_id 列表")


@router.get("/overview")
def get_dashboard_overview(
    grain: Literal["day", "week", "month"] = Query(default="day"),
    selected_date: date = Query(..., description="锚点日期；week 传周一，month 传月初"),
) -> dict[str, object]:
    # ---- 缓存优先：同 grain + 同 date 直接返回（300s 内） ----
    cached = cache.get_overview(grain=grain, selected_date=selected_date.isoformat())
    if cached is not None:
        _log.debug("cache HIT overview grain=%s date=%s", grain, selected_date)
        return {"ok": True, "data": normalize_payload(cached), "cached": True}

    # ---- 缓存未命中：走 DB 查询 ----
    payload = service.load_dashboard_payload(grain, selected_date)
    cache.set_overview(payload, grain=grain, selected_date=selected_date.isoformat())
    _log.info("cache MISS overview grain=%s date=%s → computed & stored (ttl=300s)", grain, selected_date)
    return {
        "ok": True,
        "data": normalize_payload(payload),
        "cached": False,
    }


@router.get("/group-detail")
def get_group_detail(
    grain: Literal["day", "week", "month"] = Query(default="day"),
    selected_date: date = Query(...),
    group_name: str = Query(..., description="组别名称"),
    queue_name: str | None = Query(default=None),
    reviewer_name: str | None = Query(default=None),
    focus_rule_code: str | None = Query(default=None),
    focus_error_type: str | None = Query(default=None),
    demo_fixture: str | None = Query(default=None, description="dev-only fixture 名称"),
) -> dict[str, object]:
    payload = service.load_demo_group_payload(
        grain=grain,
        selected_date=selected_date,
        group_name=group_name,
        queue_name=queue_name,
        demo_fixture=demo_fixture,
    )
    if payload is None:
        payload = service.load_group_payload(
            grain=grain,
            selected_date=selected_date,
            group_name=group_name,
            queue_name=queue_name,
            reviewer_name=reviewer_name,
            focus_rule_code=focus_rule_code,
            focus_error_type=focus_error_type,
        )
    return {
        "ok": True,
        "data": normalize_payload(payload),
    }


@router.get("/alerts")
def get_alerts(
    grain: Literal["day", "week", "month"] = Query(default="day"),
    selected_date: date = Query(...),
    demo_fixture: str | None = Query(default=None, description="dev-only fixture 名称"),
) -> dict[str, object]:
    # ---- 缓存优先：同 grain + 同 date + 同 fixture 直接返回（180s 内） ----
    cached = cache.get_alerts(
        grain=grain, selected_date=selected_date.isoformat(), demo_fixture=demo_fixture,
    )
    if cached is not None:
        _log.debug("cache HIT alerts grain=%s date=%s", grain, selected_date)
        return {
            "ok": True,
            "data": cached,
            "cached": True,
        }

    # ---- 缓存未命中：走 DB 查询 ----
    anchor_date = service.normalize_anchor_date(grain, selected_date)
    alerts_df = service.load_demo_alerts_df(demo_fixture)
    if alerts_df is None:
        alerts_df = service.repo.get_alerts(grain, anchor_date)
    enriched_alerts = service.enrich_alerts(alerts_df)
    result = {
        "grain": grain,
        "selected_date": selected_date.isoformat(),
        "anchor_date": anchor_date.isoformat(),
        "summary": service.summarize_alerts(alerts_df),
        "status_summary": service.summarize_alert_status(alerts_df),
        "sla_summary": service.summarize_alert_sla(alerts_df),
        "actions": service.build_alert_actions(alerts_df),
        "items": dataframe_to_records(enriched_alerts),
    }
    cache.set_alerts(result, grain=grain, selected_date=selected_date.isoformat(), demo_fixture=demo_fixture)
    _log.info("cache MISS alerts grain=%s date=%s → computed & stored (ttl=180s)", grain, selected_date)
    return {"ok": True, "data": result, "cached": False}


@router.patch("/alerts/bulk-update")
def patch_bulk_alert_status(payload: AlertBulkStatusUpdate) -> dict[str, object]:
    updated_count = service.bulk_update_alert_status(
        alert_ids=payload.alert_ids,
        alert_status=payload.alert_status,
        owner_name=payload.owner_name,
        handle_note=payload.handle_note,
    )
    # 清除受影响的日期缓存（无法精确到 grain，用 broad invalidation）
    _log.info("cache INVALIDATE alerts after bulk-update (count=%d)", updated_count)
    # 由于 bulk-update 跨日期，简单清空整个 alerts 缓存
    cache._alerts.clear()
    return {
        "ok": True,
        "message": "批量告警状态更新成功",
        "data": {
            "updated_count": updated_count,
            "alert_ids": payload.alert_ids,
            "alert_status": payload.alert_status,
            "owner_name": payload.owner_name,
            "handle_note": payload.handle_note,
        },
    }


@router.get("/alerts/{alert_id}")
def get_alert_detail(
    alert_id: str,
    grain: Literal["day", "week", "month"] = Query(default="day"),
    selected_date: date = Query(...),
    demo_fixture: str | None = Query(default=None, description="dev-only fixture 名称"),
) -> dict[str, object]:
    anchor_date = service.normalize_anchor_date(grain, selected_date)
    alerts_df = service.load_demo_alerts_df(demo_fixture)
    if alerts_df is None:
        alerts_df = service.repo.get_alerts(grain, anchor_date)
    detail = next(
        (item for item in service.build_alert_focus_options(alerts_df) if item.get("alert_id") == alert_id),
        None,
    )
    if detail is None:
        raise DataNotFoundError(
            f"未找到告警 ID: {alert_id}",
            details={
                "alert_id": alert_id,
                "grain": grain,
                "selected_date": selected_date.isoformat(),
                "suggestion": "请确认日期粒度和 alert_id 是否匹配"
            }
        )

    history_df = service.load_alert_history(alert_id, limit=20)
    alert_sample_preview = service.load_demo_alert_sample_preview(demo_fixture, alert_id=alert_id)
    if alert_sample_preview is None:
        alert_sample_preview = service.load_alert_sample_preview(grain=grain, anchor_date=anchor_date, detail=detail)
    detail_payload = {
        **detail,
        "grain": grain,
        "selected_date": selected_date.isoformat(),
        "anchor_date": anchor_date.isoformat(),
        "target_level_label": service.get_alert_target_level_label(detail.get("target_level")),
        "sla_policy_text": service.get_sla_policy_text(),
        "history": dataframe_to_records(history_df),
        "alert_sample_df": dataframe_to_records(alert_sample_preview["alert_sample_df"]),
        "alert_sample_title": alert_sample_preview["alert_sample_title"],
        "alert_sample_hint": alert_sample_preview["alert_sample_hint"],
        "alert_sample_scope": alert_sample_preview["alert_sample_scope"],
    }
    return {
        "ok": True,
        "data": normalize_payload(detail_payload),
    }


@router.patch("/alerts/{alert_id}")
def patch_alert_status(alert_id: str, payload: AlertStatusUpdate) -> dict[str, object]:
    service.update_alert_status(
        alert_id=alert_id,
        alert_status=payload.alert_status,
        owner_name=payload.owner_name,
        handle_note=payload.handle_note,
    )
    # 清除单条告警详情缓存 + alerts 列表（状态变了列表也要刷新）
    cache.invalidate_alert_detail(alert_id)
    _log.info("cache INVALIDATE alert_detail after status update alert_id=%s", alert_id)
    history_df = service.load_alert_history(alert_id, limit=20)
    return {
        "ok": True,
        "message": "告警状态更新成功",
        "data": {
            "alert_id": alert_id,
            "alert_status": payload.alert_status,
            "owner_name": payload.owner_name,
            "handle_note": payload.handle_note,
            "history": dataframe_to_records(history_df),
        },
    }
