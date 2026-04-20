"""dashboard 路由异常处理改造示例 - 演示如何使用统一异常类。

改造前后对比：

❌ 改造前（不统一）：
    if not data:
        raise HTTPException(status_code=404, detail="数据不存在")

✅ 改造后（统一）：
    from api.exceptions import DataNotFoundError
    if not data:
        raise DataNotFoundError("仪表盘数据")

好处：
1. 错误码统一（前端可以根据 code 做国际化）
2. 日志格式统一（便于监控和告警）
3. 减少重复代码
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.exceptions import DataNotFoundError, ValidationError  # 新增
from api.serializers import dataframe_to_records, normalize_payload
from services.dashboard_service import DashboardService
from utils.cache import get_cache
from utils.logger import get_logger

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
service = DashboardService()
cache = get_cache()
_log = get_logger("api.dashboard")


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
    """获取仪表盘概览数据。
    
    示例异常使用（未来扩展）：
        if selected_date > date.today():
            raise ValidationError("selected_date", "不能查询未来日期")
    """
    # ---- 缓存优先：同 grain + 同 date 直接返回（300s 内） ----
    cached = cache.get_overview(grain=grain, selected_date=selected_date.isoformat())
    if cached is not None:
        _log.debug("cache HIT overview grain=%s date=%s", grain, selected_date)
        return {"ok": True, "data": normalize_payload(cached), "cached": True}

    # ---- 缓存未命中：走 DB 查询 ----
    payload = service.load_dashboard_payload(grain, selected_date)
    
    # 示例：如果数据为空，抛出业务异常（根据实际需求决定是否需要）
    # if not payload:
    #     raise DataNotFoundError(f"{grain} 维度 {selected_date} 仪表盘数据")
    
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
    """获取组别详细数据。
    
    改造示例（未来可选）：
        if not group_name:
            raise ValidationError("group_name", "组别名称不能为空")
    """
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
    
    # 示例：如果关键数据缺失，抛出异常
    # if payload is None:
    #     raise DataNotFoundError(f"组别 {group_name} 的详细数据")
    
    return {
        "ok": True,
        "data": normalize_payload(payload),
    }


# 其他路由函数保持不变...
# 未来可以逐步在需要的地方替换 HTTPException 为统一异常类
