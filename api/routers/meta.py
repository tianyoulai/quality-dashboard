from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from api.serializers import normalize_payload
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])
service = DashboardService()


@router.get("/navigation")
def get_navigation() -> dict[str, object]:
    return {
        "ok": True,
        "data": {
            "app_name": "QC统一看板",
            "subtitle": "Streamlit 与 Next.js 双轨迁移中",
            "items": [
                {"key": "dashboard", "label": "首页总览", "href": "/", "description": "经营总览、告警、组别概览"},
                {"key": "details", "label": "明细查询", "href": "/details", "description": "多维筛选、问题样本、导出前查询"},
                {"key": "newcomers", "label": "新人追踪", "href": "/newcomers", "description": "批次概览、成员、阶段走势"},
                {"key": "internal", "label": "内检看板", "href": "/internal", "description": "内部质检·队列分析·审核人画像"},
            ],
        },
    }


@router.get("/date-range")
def get_date_range() -> dict[str, object]:
    min_date, max_date = service.get_data_date_range()

    today = date.today().isoformat()
    payload = {
        "min_date": min_date or today,
        "max_date": max_date or today,
        "default_grain": "day",
        "default_selected_date": max_date or today,
    }
    return {
        "ok": True,
        "data": normalize_payload(payload),
    }
