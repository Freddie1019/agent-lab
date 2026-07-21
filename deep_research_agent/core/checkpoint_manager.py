from typing import Optional, Any
from deep_research_agent.core.checkpoint import (
    RunCheckpoint,
    CheckpointType,
)
from deep_research_agent.core.db.repositories import (
    checkpoint_repo,
)
class CheckpointManager:
    """
    Agent运行过程中的checkpoint管理器

    职责：
    1. 判断稳定节点
    2. 创建checkpoint
    3. 持久化checkpoint
    """

    def should_checkpoint(
        self,
        event_type:str,
    ) -> bool:
        """
        判断当前事件是否值得保存checkpoint
        """

        stable_events = {
            # 工具完成后
            "tool_result",
            # Agent完成一个推理阶段
            "step_completed",
            # 初始化完成
            "agent_started",
        }
        return event_type in stable_events
    
    async def create_checkpoint(
        self,
        *,
        run_id: str,
        session_id: str,
        user_id: str,
        step_index: int,
        event_type: str,
        messages: list[dict],
        accumulated_content: Optional[str],
        db,
    ) -> RunCheckpoint:


        checkpoint = RunCheckpoint(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            step_index=step_index,
            checkpoint_type=self.get_checkpoint_type(
                event_type
            ),
            messages_snapshot=messages,
            accumulated_content=(
                accumulated_content
            ),
            last_event_type=event_type,
        )

        await checkpoint_repo.add(
            db,
            checkpoint
        )

        return checkpoint



    def get_checkpoint_type(
        self,
        event_type:str
    ) -> CheckpointType:


        mapping = {
            "agent_started":
                CheckpointType.INITIAL,
            "tool_result":
                CheckpointType.AFTER_TOOL_RESULT,
            "step_completed":
                CheckpointType.STABLE_STEP,
        }

        return mapping.get(
            event_type,
            CheckpointType.MANUAL
        )

checkpoint_manager = CheckpointManager()
    
