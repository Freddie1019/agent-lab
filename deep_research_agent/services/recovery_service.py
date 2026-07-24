from deep_research_agent.core.recovery import (
    RecoveryMode,
    RunRecoveryPlan,
)

class RecoveryService:
    def build_plan(
        self,
        run,
        checkpoint=None,
        last_tool_call=None,
    ):
        # 1. 已完成
        if run.status.value == "completed":
            return RunRecoveryPlan(
                run_id=run.id,
                recoverable=False,
                recommended_mode=RecoveryMode.NONE,
                reason="Run已经完成，不需要恢复"
            )

        # 2. 没有checkpoint
        if checkpoint is None:
            return RunRecoveryPlan(
                run_id=run.id,
                recoverable=True,
                recommended_mode=RecoveryMode.REGENERATE,
                allowed_modes=[
                    RecoveryMode.REGENERATE
                ],
                reason="没有checkpoint，只能重新生成"
            )

        # 3. 有checkpoint
        warnings = []
        if last_tool_call:
            if last_tool_call.is_dangerous:
                warnings.append(
                    "存在危险工具调用，需要人工确认"
                )

        return RunRecoveryPlan(
            run_id=run.id,
            recoverable=True,
            recommended_mode=RecoveryMode.RESUME_FROM_CHECKPOINT,
            allowed_modes=[
                RecoveryMode.RESUME_FROM_CHECKPOINT,
                RecoveryMode.REGENERATE
            ],
            reason="存在稳定checkpoint，可以继续恢复",
            warning=warnings,
            checkpoint_id=checkpoint.id,
            checkpoint_step=checkpoint.step_index
        )

recovery_service = RecoveryService()
    
