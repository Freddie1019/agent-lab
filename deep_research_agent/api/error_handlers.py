"""
统一错误响应：参照 RFC 7807 Problem Details
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.agent_errors import AgentError

class ErrorResponse(BaseModel):
    """统一错误响应格式（RFC 7807 风格）"""
    type: str
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
    timestamp: str
    errors: list = []

def _make_error_response(
    status_code: int,
    error_type: str,
    title: str,
    detail: str,
    instance: str,
    errors: Optional[list] = None,
) -> JSONResponse:
    response = ErrorResponse(
        type=f"https://your-api.com/errors/{error_type}",
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        request_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        errors=errors or [],
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(),
    )

def register_error_handlers(app: FastAPI):
    """注册所有错误处理器"""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return _make_error_response(
            status_code=422,
            error_type="validation-error",
            title="Request Validation Failed",
            detail="One or more request fields failed validation",
            instance=str(request.url.path),
            errors=[
                {
                    "field": ".".join(str(x) for x in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
                for err in exc.errors()
            ],
        )
    
    @app.exception_handler(AgentError)
    async def agent_error_handler(request: Request, exc: AgentError):
        # 根据 AgentError 类型映射到 HTTP 状态码
        from shared.agent_errors import (
            ToolRateLimit, ToolPermissionDenied, ToolInvalidArgument,
            ToolUnavailable, ToolTimeout,
        )

        if isinstance(exc, ToolRateLimit):
            status = 429
        elif isinstance(exc, ToolPermissionDenied):
            status = 403
        elif isinstance(exc, ToolInvalidArgument):
            status = 400
        elif isinstance(exc, (ToolUnavailable, ToolTimeout)):
            status = 503
        else:
            status = 500
        
        return _make_error_response(
            status_code=status,
            error_type=exc.__class__.__name__.lower().replace("tool", "tool-"),
            title=exc.user_message,
            detail=exc.detail or str(exc),
            instance=str(request.url.path),
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """兜底：所有未捕获的异常"""
        # 生产环境应该上报到 Sentry
        return _make_error_response(
            status_code=500,
            error_type="internal-error",
            title="Internal Server Error",
            detail="An unexpected error occurred. Please try again later.",
            instance=str(request.url.path),
        )
