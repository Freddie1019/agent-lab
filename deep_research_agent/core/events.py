"""
Agent 流式事件类型定义
v2: 增强错误事件
"""
import json
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pydantic import BaseModel
from typing import Literal, Optional
from shared.agent_errors import (
    AgentError, ToolRateLimit, ToolTimeout,
    ToolUnavailable, ToolInvalidArgument,
    ToolPermissionDenied, ToolHumanRejected,
)

# 所有可能的事件类型
AgentEventType = Literal[
    "agent_start",      # Agent 开始执行
    "step_start",       # 一个新步骤开始
    "thought",          # Agent 的思考
    "tool_call",        # 调用工具
    "tool_result",      # 工具执行结果
    "answer_chunk",     # 最终答案的 token 增量（流式 LLM 输出）
    "answer_complete",  # 答案完整生成完毕
    "error",            # 错误
    "agent_complete",   # Agent 整体完成
    "queued",
    "started",
]

# 错误的严重程度
ErrorSeverity = Literal[
    "warning",  # 部分功能失败，但流可以继续
    "error",  # 流必须终止
    "fatal",  # 系统级错误，可能需要人工
]

class AgentErrorEvent(BaseModel):
    """ 流式中的错误事件 - RFC 7807 风格 """
    # 错误身份
    type: str      # 例如 "tool_rate_limit"
    title: str    # 人类可读的简短标题

    # 详细信息
    detail: str   # 详细错误信息（给开发者）
    user_message: str  # 用户友好的信息（给终端用户）

    # 流式特有字段
    step: int = 0   # 第几步出错
    severity: ErrorSeverity = "error"
    recoverable: bool = False  # 客户端能不能自动重试
    retry_after: Optional[float] = None  # 多少秒后建议重试

    # 上下文
    tool_name: Optional[str] = None  # 工具错误时填工具名
    accumulated_content: Optional[str] = None   # 已生成的部分内容

    def to_event_data(self) -> dict:
        return self.model_dump(exclude_none=True)


class AgentEvent(BaseModel):
    """统一的 Agent 事件结构"""
    type: AgentEventType
    step: int = 0
    data: dict = {}

    def to_sse(self) -> str:
        """序列化为 SSE 事件帧"""
        import json
        # event: type
        # data: {json}
        # \n\n
        return f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"

def make_error_event(
    type: str,
    title: str,
    detail: str,
    user_message: str,
    step: int = 0,
    severity: ErrorSeverity = "error",
    recoverable: bool = False,
    retry_after: Optional[float] = None,
    tool_name: Optional[str] = None,
    accumulated_content: Optional[str] = None,
) -> AgentEvent:
    """ 工厂函数：构造标准错误事件 """
    error = AgentErrorEvent(
        type=type, title=title, detail=detail, user_message=user_message,
        step=step, severity=severity, recoverable=recoverable,
        retry_after=retry_after, tool_name=tool_name,
        accumulated_content=accumulated_content,
    )
    return AgentEvent(type="error", step=step, data=error.to_event_data())

def agent_error_to_event(
    e: AgentError,
    step: int = 0,
    accumulated_content: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> AgentError:
    """把 AgentError 转换成 SSE 错误事件"""

    # 根据 AgentError 类型决定语义
    type_map = {
        ToolRateLimit: ("tool_rate_limit", True, 60.0),
        ToolTimeout: ("tool_timeout", True, 30.0),
        ToolUnavailable: ("tool_unavailable", True, 60.0),
        ToolInvalidArgument: ("tool_invalid_argument", False, None),
        ToolPermissionDenied: ("tool_permission_denied", False, None),
        ToolHumanRejected: ("user_rejected_action", False, None),
    }

    error_type, recoverable, retry_after = type_map.get(
        type(e),
        ("internal_error", False, None)
    )

    return make_error_event(
        type=error_type,
        title=e.__class__.__name__,
        detail=e.detail or str(e),
        user_message=e.user_message,
        step=step,
        severity="error",
        recoverable=recoverable,
        retry_after=retry_after,
        tool_name=tool_name,
        accumulated_content=accumulated_content,
    )