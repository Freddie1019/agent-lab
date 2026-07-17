from datetime import datetime
from enum import Enum
from pydantic import BaseModel,Field
from typing import Optional,Any
from uuid import uuid4

class RunStepType(str, Enum):
    """
    AgentRun 中的步骤类型。
    """
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"
    SYSTEM = "system"

class RunStepStatus(str, Enum):
    """
    单个步骤的状态。
    """
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ToolCallStatus(str, Enum):
    """
    工具调用状态。
    """
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class RunStep(BaseModel):
    """
    AgentRun 中的一条步骤记录。
    """
    id: str = Field(default_factory=lambda: f"step_{uuid4().hex}")

    run_id: str
    session_id: str
    user_id: str

    step_index: int = 0
    event_type: str
    step_type: RunStepType
    status: RunStepStatus = RunStepStatus.COMPLETED

    # 内容
    content: Optional[str] = None
    summary: Optional[str] = None

    # 原始事件数据，方便调试
    raw_event_data: dict[str, Any] = Field(default_factory=dict)

    # 错误
    error_type: Optional[str] = None
    error_detail: Optional[str] = None

    # 时间
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # 扩展字段
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_failed(
        self,
        error_type: str,
        error_detail: str,
    ) -> None:
        self.status = RunStepStatus.FAILED
        self.error_type = error_type
        self.error_detail = error_detail
        self.completed_at = datetime.now()

    def mark_completed(self) -> None:
        self.status = RunStepStatus.COMPLETED
        self.completed_at = datetime.now()

class ToolCallRecord(BaseModel):
    """
    AgentRun 中的一次工具调用记录。
    """
    id: str =  Field(default_factory=lambda: f"step_{uuid4().hex}")

    run_id: str
    session_id: str
    user_id: str

    step_index: int = 0
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)

    status: ToolCallStatus = ToolCallStatus.RUNNING
    success: Optional[bool] = None

    result_preview: Optional[str] = None
    result_raw: Optional[str] = None

    error_type: Optional[str] = None
    error_detail: Optional[str] = None

    # 安全与审批
    is_dangerous: bool = False
    approval_required: bool = False
    approved: Optional[bool] = None

    # 时间
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # 扩展
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_completed(
        self,
        result_preview: Optional[str] = None,
        result_raw: Optional[str] = None,
    ) -> None:
        now = datetime.now()
        self.status = ToolCallStatus.COMPLETED
        self.success = True
        self.result_preview = result_preview
        self.result_raw = result_raw
        self.completed_at = now
        self.duration_ms = (now - self.created_at).total_seconds() * 1000

    def mark_failed(
        self,
        error_type: str,
        error_detail: str,
    ) -> None:
        now = datetime.now()
        self.status = ToolCallStatus.FAILED
        self.success = False
        self.error_type = error_type
        self.error_detail = error_detail
        self.completed_at = now
        self.duration_ms = (now - self.created_at).total_seconds() * 1000
