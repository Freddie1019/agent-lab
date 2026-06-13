"""
统一的 Agent 错误类型系统
所有工具/服务的异常最终都归一到这几种业务语义化错误
"""
from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    """错误大类，决定处理策略"""
    TRANSIENT = "transient"      # 瞬时错误，可重试
    PERMANENT = "permanent"      # 永久错误，不可重试
    RATE_LIMIT = "rate_limit"    # 限流，需要等待
    SAFETY = "safety"            # 安全问题，需要人工
    UNKNOWN = "unknown"          # 未分类，谨慎处理


class AgentError(Exception):
    """所有 Agent 错误的基类"""
    category: ErrorCategory = ErrorCategory.UNKNOWN
    user_message: str = "操作失败"  # 给 LLM 看的业务话术
    retryable: bool = False
    retry_after: Optional[float] = None  # 多少秒后可重试

    def __init__(self, detail: str = "", **kwargs):
        super().__init__(detail)
        self.detail = detail
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_llm_message(self) -> str:
        """生成喂给 LLM 的错误描述（绝不暴露 Traceback）"""
        msg = self.user_message
        if self.retry_after:
            msg += f"（建议 {self.retry_after} 秒后重试）"
        return msg


# ===== 具体错误类型 =====

class ToolTimeout(AgentError):
    category = ErrorCategory.TRANSIENT
    user_message = "工具执行超时，请重试或换个方式查询"
    retryable = True


class ToolRateLimit(AgentError):
    category = ErrorCategory.RATE_LIMIT
    user_message = "工具调用次数已达上限，请稍后再试"
    retryable = True
    retry_after = 30.0


class ToolInvalidArgument(AgentError):
    category = ErrorCategory.PERMANENT
    user_message = "工具参数不合法，请检查参数后重试"
    retryable = False


class ToolPermissionDenied(AgentError):
    category = ErrorCategory.SAFETY
    user_message = "此操作需要更高权限，已被安全策略拒绝"
    retryable = False


class ToolUnavailable(AgentError):
    category = ErrorCategory.TRANSIENT
    user_message = "工具服务暂时不可用（已熔断），请稍后重试或使用其他方式"
    retryable = True
    retry_after = 30.0


class ToolHumanRejected(AgentError):
    category = ErrorCategory.SAFETY
    user_message = "此操作被用户拒绝，请询问用户是否需要其他方案"
    retryable = False


def classify_exception(e: Exception) -> AgentError:
    """把任意异常转化为 AgentError（兜底翻译器）"""
    import httpx
    
    if isinstance(e, AgentError):
        return e
    
    if isinstance(e, (httpx.TimeoutException, TimeoutError)):
        return ToolTimeout(str(e))
    
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 429:
            return ToolRateLimit(f"HTTP 429: {e}")
        if code in (400, 422):
            return ToolInvalidArgument(f"HTTP {code}: {e}")
        if code in (401, 403):
            return ToolPermissionDenied(f"HTTP {code}: {e}")
        if 500 <= code < 600:
            return ToolUnavailable(f"HTTP {code}: {e}")
    
    if isinstance(e, (ConnectionError, httpx.ConnectError)):
        return ToolUnavailable(f"网络连接失败: {e}")
    
    # 未知错误兜底
    err = AgentError(detail=str(e))
    err.user_message = f"工具执行遇到未预期错误: {type(e).__name__}"
    return err