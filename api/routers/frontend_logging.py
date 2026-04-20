"""前端错误日志收集路由 - 接收前端上报的错误信息。

提供接口：
- POST /api/v1/log-error: 接收前端错误日志

日志会写入到 logs/frontend.log，便于后续排查问题。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from utils.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["logging"])
_log = get_logger("frontend.error")


class FrontendErrorLog(BaseModel):
    """前端错误日志模型"""
    error_type: str = Field(default="frontend_error", description="错误类型")
    error_message: str = Field(..., description="错误消息")
    error_stack: str | None = Field(default=None, description="错误堆栈")
    component_stack: str | None = Field(default=None, description="组件堆栈")
    user_agent: str | None = Field(default=None, description="用户代理")
    url: str | None = Field(default=None, description="出错页面 URL")
    timestamp: str | None = Field(default=None, description="错误时间戳")


@router.post("/log-error")
async def log_frontend_error(error: FrontendErrorLog, request: Request) -> dict[str, str]:
    """接收前端错误日志。
    
    Args:
        error: 前端错误信息
        request: FastAPI 请求对象
        
    Returns:
        确认响应
    """
    client_ip = request.client.host if request.client else "-"
    request_id = getattr(request.state, "request_id", "-")
    
    # 记录到日志文件
    _log.error(
        "Frontend error | rid=%s | client=%s | url=%s | message=%s | stack=%s",
        request_id,
        client_ip,
        error.url,
        error.error_message,
        error.error_stack[:500] if error.error_stack else "-"  # 截断过长的堆栈
    )
    
    # 可选：存储到数据库（未来扩展）
    # await store_error_to_db(error, client_ip, request_id)
    
    return {
        "status": "ok",
        "message": "错误已记录",
        "request_id": request_id
    }


@router.get("/health-frontend-logging")
async def health_check_frontend_logging() -> dict[str, str]:
    """前端日志模块健康检查。"""
    return {
        "status": "ok",
        "module": "frontend-logging",
        "timestamp": datetime.now().isoformat()
    }
