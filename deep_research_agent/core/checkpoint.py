from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

class CheckpointType(str, Enum):
    INITIAL = "initial"
    AFTER_TOOL_RESULT = "after_tool_result"
    STABLE_STEP = "stable_step"
    MANUAL = "manual"

class RunCheckpoint(BaseModel):
    id: str = Field(
        default_factory=lambda: f"checkpoint_{uuid4().hex}"
    )

    run_id: str
    session_id: str
    user_id: str

    step_index: int = 0
    checkpoint_type: CheckpointType

    # 可恢复的完整消息上下文
    messages_snapshot: list[dict[str, Any]] = Field(default_factory=list)

    accumulated_content: Optional[str] = None
    last_event_type: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

    metadata: dict[str, Any] = Field(default_factory=dict)