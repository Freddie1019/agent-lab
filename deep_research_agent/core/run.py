from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class AgentRunStatus(str, Enum):
    """
    Agent 一次执行过程的状态。

    queued:
        已创建，等待执行。后续接入后台任务队列时会用到。

    running:
        正在执行。

    waiting_tool:
        正在等待工具调用结果。

    waiting_user:
        正在等待用户确认，适用于 Human-in-the-loop。

    completed:
        正常完成。

    failed:
        系统错误或不可恢复错误。

    interrupted:
        被中断，例如客户端断开连接。

    cancelled:
        用户主动取消。
    """

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"

class AgentRun(BaseModel):
    """
    Agent 的一次运行记录。

    一个用户问题通常对应一次 AgentRun。
    """
    id: str = Field(default_factory=lambda: f"run_{uuid4().hex}")

    # 归属关系
    session_id: str
    user_id: str

    # 具体 message
    user_message_id: Optional[str] = None
    assistant_message_id: Optional[str] = None

    # 状态
    status: AgentRunStatus = AgentRunStatus.QUEUED
    current_step: int = 0

    # 当前正在执行的动作
    current_event: Optional[str] = None
    current_tool: Optional[str] = None

     # 错误信息
    error_type: Optional[str] = None
    error_detail: Optional[str] = None
    error_user_message: Optional[str] = None

    # 简单统计
    total_events: int = 0
    total_tool_calls: int = 0

    # 时间
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)

    # 扩展字段
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_started(self) -> None:
        now = datetime.now()
        self.status = AgentRunStatus.RUNNING
        self.started_at = now
        self.updated_at = now
    
    def mark_completed(self) -> None:
        now = datetime.now()
        self.status = AgentRunStatus.COMPLETED
        self.completed_at = now
        self.updated_at = now

    def mark_failed(
        self,
        error_type: str,
        error_detail: str,
        error_user_message: Optional[str] = None,
    ) -> None:
        now = datetime.now()
        self.status = AgentRunStatus.FAILED
        self.error_type = error_type
        self.error_detail = error_detail
        self.error_user_message = error_user_message
        self.completed_at = now
        self.updated_at = now
    
    def mark_interrupted(
        self,
        reason: str = "client_disconnected",
    ) -> None:
        now = datetime.now()
        self.status = AgentRunStatus.INTERRUPTED
        self.error_type = "interrupted"
        self.error_detail = reason
        self.completed_at = now
        self.updated_at = now
    
    def mark_cancelled(
        self,
        reason: str = "user_cancelled",
    ) -> None:
        now = datetime.now()
        self.status = AgentRunStatus.CANCELLED
        self.error_type = "cancelled"
        self.error_detail = reason
        self.completed_at = now
        self.updated_at = now
    
    def update_step(self, step: int) -> None:
        self.current_step = step
        self.updated_at = datetime.now()

    def update_event(self, event_type: str) -> None:
        self.current_event = event_type
        self.total_events += 1
        self.updated_at = datetime.now()

    def mark_waiting_tool(self, tool_name: Optional[str] = None) -> None:
        self.status = AgentRunStatus.WAITING_TOOL
        self.current_tool = tool_name
        self.total_tool_calls += 1
        self.updated_at = datetime.now()

    def mark_running(self) -> None:
        self.status = AgentRunStatus.RUNNING
        self.current_tool = None
        self.updated_at = datetime.now()