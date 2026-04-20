from __future__ import annotations

import os
import time
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import dashboard, details, meta, monitor, analysis
# 内检路由 —— 6 个端点（summary/queues/trend/reviewers/error-types/qa-owners）
from api.routers import internal as _internal_mod  # noqa: F401
# 前端日志收集路由
from api.routers import frontend_logging
# 统一异常类
from api.exceptions import BusinessException

from utils.logger import get_logger

_log = get_logger("api.access")
_log_err = get_logger("api.error")

# newcomers 路由 —— 2026-04-19 方案A收口：
#   所有公有符号已在 api/routers/newcomers.py 的 __all__ 中声明，
#   main.py 只需 import router 即可注册路由。
#   不依赖 services/newcomer_aggregates（该模块尚未迁完），零风险。
from api.routers import newcomers as _newcomers_mod  # noqa: F401
_newcomers_router = _newcomers_mod.router
_newcomers_load_error: str | None = None

# 慢请求阈值（毫秒），可通过环境变量覆盖
_SLOW_MS = int(os.getenv("API_SLOW_THRESHOLD_MS", "800"))


def _parse_allow_origins() -> list[str]:
    raw_value = os.getenv("API_ALLOW_ORIGINS", "*")
    origins = [item.strip() for item in raw_value.split(",") if item.strip()]
    return origins or ["*"]


app = FastAPI(
    title="QC 统一看板 API",
    description="从 Streamlit 页面逻辑中抽离出的首批 FastAPI 接口，用于统一看板前后端解耦迁移。",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常统一处理器。
    
    捕获所有继承自 BusinessException 的异常，返回标准格式：
    {
        "error": {
            "code": "DATA_NOT_FOUND",
            "message": "告警不存在"
        },
        "request_id": "a1b2c3d4e5"
    }
    """
    rid = getattr(request.state, "request_id", "-")
    _log.warning(
        "rid=%s BusinessException: code=%s message=%s",
        rid, exc.code, exc.message
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": rid
        },
        headers={"X-Request-Id": rid}
    )


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    """统一 access log + 慢请求告警 + 异常兜底。

    日志落到 logs/dashboard.log（api.access / api.error）。
    每条请求分配 request_id（回写到响应头 X-Request-Id），便于关联前端日志。
    """
    # 跳过 preflight 与静态文档路径的噪声
    path = request.url.path
    if request.method == "OPTIONS" or path in ("/api/health",) or path.startswith("/api/docs") \
            or path.startswith("/api/redoc") or path == "/api/openapi.json":
        return await call_next(request)

    rid = uuid.uuid4().hex[:10]
    request.state.request_id = rid  # 保存到 request.state，供异常处理器使用
    start = time.perf_counter()
    qs = request.url.query
    client = request.client.host if request.client else "-"

    try:
        response = await call_next(request)
    except Exception as exc:  # pragma: no cover - 未处理异常兜底
        elapsed_ms = (time.perf_counter() - start) * 1000
        _log_err.error(
            "rid=%s %s %s?%s client=%s FAILED in %.0fms err=%s\n%s",
            rid, request.method, path, qs, client, elapsed_ms, exc,
            traceback.format_exc(limit=6),
        )
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "request_id": rid, "message": str(exc)[:200]},
            headers={"X-Request-Id": rid},
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    status = response.status_code
    # 慢请求 / 非 2xx 专门用 WARNING；其他 INFO
    if status >= 500:
        level = _log_err.error
    elif status >= 400 or elapsed_ms >= _SLOW_MS:
        level = _log.warning
    else:
        level = _log.info
    level(
        "rid=%s %s %s?%s client=%s status=%s in %.0fms",
        rid, request.method, path, qs, client, status, elapsed_ms,
    )
    response.headers["X-Request-Id"] = rid
    return response


app.include_router(meta.router)
app.include_router(dashboard.router)
app.include_router(details.router)
app.include_router(monitor.router)  # 实时监控路由
app.include_router(analysis.router)  # 错误分析路由
if _newcomers_router is not None:
    app.include_router(_newcomers_router)
app.include_router(_internal_mod.router)  # 内检看板路由
app.include_router(frontend_logging.router)  # 前端日志收集路由


@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, object]:
    return {
        "ok": True,
        "service": "qc-dashboard-api",
        "version": app.version,
        "routers": {
            "meta": True,
            "dashboard": True,
            "details": True,
            "monitor": True,
            "analysis": True,  # 新增
            "newcomers": _newcomers_router is not None,
            "internal": True,
        },
        "newcomers_load_error": _newcomers_load_error,
        "slow_threshold_ms": _SLOW_MS,
    }
