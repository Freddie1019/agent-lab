from deep_research_agent.core.checkpoint import (
    RunCheckpoint,
)
from deep_research_agent.core.db.repositories import (
    checkpoint_repo
)
class CheckpointManager:
    """
    Agent运行过程中的checkpoint管理器
    """

    async def save_checkpoint(
        self,
        *,
        run_id,
        session_id,
        user_id,
        step_index,
        event_type,
        checkpoint_type,
        messages,
        accumulated_content,
        db,
    ):
        checkpoint = RunCheckpoint(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            step_index=step_index,
            checkpoint_type=checkpoint_type,
            messages_snapshot=messages,
            accumulated_content=accumulated_content,
            last_event_type=event_type,
        )

        await checkpoint_repo.add(
            db,
            checkpoint
        )


checkpoint_manager = CheckpointManager()
    
