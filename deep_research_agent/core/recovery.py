from enum import Enum
from typing import Optional
from pydantic import Field, BaseModel

class RecoveryMode(str, Enum):
    """
    AgentRun 的恢复方式
    """

    NONE = "none"

    # 从原始用户消息重新执行
    REGENERATE = "regenerate"

    # 从最近稳定检查点继续
    RESUME_FROM_CHECKPOINT = (
        "resume_from_checkpoint"
    )

    # 只重试失败工具，目前仅预留
    RETRY_TOOL = "retry_tool"


class RunRecoveryPlan(BaseModel):
    """
    服务端根据 run 状态生成的恢复建议
    """

    run_id: str
    recoverable: bool

    recommended_mode: RecoveryMode
    allowed_modes: list[RecoveryMode] = (
        Field(default_factory=list)
    )
        

    reason: str
    warning: list[str] = (
        Field(default_factory=list)
    )

    checkpoint_id: Optional[str] = None
    checkpoint_step: Optional[int] = None

    