"""统一异常类定义 - FastAPI 业务异常标准化。

所有业务异常继承自 BusinessException，提供统一的错误码和 HTTP 状态码映射。
在路由中直接抛出，由 main.py 中的全局异常处理器捕获并返回标准格式响应。

示例:
    from api.exceptions import DataNotFoundError, ValidationError
    
    @router.get("/api/v1/alerts/{alert_id}")
    def get_alert(alert_id: str):
        alert = repo.get_alert(alert_id)
        if not alert:
            raise DataNotFoundError("告警")
        return alert
"""
from __future__ import annotations

from fastapi import HTTPException, status


class BusinessException(HTTPException):
    """业务异常基类。
    
    所有自定义业务异常都应继承此类，提供标准化的错误响应格式。
    
    Attributes:
        code: 业务错误码（字符串，便于前端国际化）
        message: 错误描述（中文，便于调试）
        status_code: HTTP 状态码
    """
    
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message}
        )
        self.code = code
        self.message = message


class DataNotFoundError(BusinessException):
    """数据不存在异常。
    
    适用场景：
    - 查询单条记录时未找到
    - 资源ID不存在
    
    Args:
        resource: 资源名称（如"告警"、"队列"、"审核人"）
    """
    
    def __init__(self, resource: str = "数据"):
        super().__init__(
            code="DATA_NOT_FOUND",
            message=f"{resource}不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )


class ValidationError(BusinessException):
    """参数校验失败异常。
    
    适用场景：
    - 日期格式错误
    - 枚举值不在允许范围
    - 必填参数缺失
    
    Args:
        field: 参数名
        reason: 校验失败原因
    """
    
    def __init__(self, field: str, reason: str):
        super().__init__(
            code="VALIDATION_ERROR",
            message=f"参数 {field} 校验失败: {reason}",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class DatabaseError(BusinessException):
    """数据库操作失败异常。
    
    适用场景：
    - SQL 执行超时
    - 连接池耗尽
    - 主键冲突
    
    Args:
        message: 错误描述（应屏蔽敏感信息）
        original_error: 原始异常（用于日志记录，不返回给前端）
    """
    
    def __init__(self, message: str = "数据库操作失败", original_error: Exception | None = None):
        super().__init__(
            code="DATABASE_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        self.original_error = original_error


class PermissionDeniedError(BusinessException):
    """权限不足异常。
    
    适用场景：
    - 用户无权访问某个队列
    - 操作需要管理员权限
    
    Args:
        action: 操作名称（如"查看告警详情"、"修改告警状态"）
    """
    
    def __init__(self, action: str = "执行此操作"):
        super().__init__(
            code="PERMISSION_DENIED",
            message=f"无权限{action}",
            status_code=status.HTTP_403_FORBIDDEN
        )


class RateLimitExceededError(BusinessException):
    """请求频率超限异常。
    
    适用场景：
    - API 调用次数超过限制
    - 短时间内重复请求
    
    Args:
        limit: 限制次数
        window: 时间窗口（秒）
    """
    
    def __init__(self, limit: int, window: int):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"请求过于频繁，限制为 {limit} 次/{window}秒",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class ExternalServiceError(BusinessException):
    """外部服务调用失败异常。
    
    适用场景：
    - 第三方 API 超时
    - 依赖服务不可用
    
    Args:
        service: 服务名称（如"蓝鲸监控"、"企业微信"）
        message: 错误描述
    """
    
    def __init__(self, service: str, message: str = "服务暂时不可用"):
        super().__init__(
            code="EXTERNAL_SERVICE_ERROR",
            message=f"{service} {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class ConflictError(BusinessException):
    """资源冲突异常。
    
    适用场景：
    - 告警状态已被其他人修改
    - 并发更新冲突
    
    Args:
        resource: 资源名称
        reason: 冲突原因
    """
    
    def __init__(self, resource: str, reason: str = "资源已被修改"):
        super().__init__(
            code="CONFLICT",
            message=f"{resource} {reason}，请刷新后重试",
            status_code=status.HTTP_409_CONFLICT
        )
