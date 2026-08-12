from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research_agent.core.db.models import (
    AgentRunORM,
    MessageORM,
    RunStepORM,
    SessionORM,
    ToolCallRecordORM,
    RunCheckpointORM,
)

from deep_research_agent.core.checkpoint import (
    CheckpointType,
    RunCheckpoint,
)

from deep_research_agent.core.run import AgentRun, AgentRunStatus
from deep_research_agent.core.run_trace import RunStep, ToolCallRecord
from deep_research_agent.core.session import Message, Session

from deep_research_agent.core.db.converters import (
    orm_to_agent_run,
    orm_to_message,
    orm_to_run_step,
    orm_to_session,
    orm_to_tool_call_record,
)

async def _finish_write(
    db: AsyncSession,
    *,
    commit: bool,
) -> None:
    if commit:
        await db.commit()
    else:
        await db.flush()

class SessionRepository:
    async def upsert_session(
        self,
        db: AsyncSession,
        session: Session,
    ) -> None:
        existing = await db.get(SessionORM, session.id)

        if existing is None:
            db.add(
                SessionORM(
                    id=session.id,
                    user_id=session.user_id,
                    title=getattr(session, "title", None),
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )
            )
        else:
            existing.title = getattr(session, "title", None)
            existing.updated_at = session.updated_at
        
        await db.commit()
    
    async def add_message(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        message: Message,
        *,
        commit: bool = True,
    ) -> None:
        existing = await db.get(
            MessageORM,
            message.id,
        )

        if existing is not None:
            return

        db.add(
            MessageORM(
                id=message.id,
                session_id=session_id,
                user_id=user_id,
                role=message.role,
                content=message.content,
                status=getattr(
                    message,
                    "status",
                    "complete",
                ),
                error_detail=getattr(
                    message,
                    "error_detail",
                    None,
                ),
                created_at=message.created_at,
            )
        )

        await _finish_write(
            db,
            commit=commit,
        )
    
    async def list_messages(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
    ) -> list[MessageORM]:
        result = await db.execute(
            select(MessageORM)
            .where(MessageORM.session_id == session_id)
            .where(MessageORM.user_id == user_id)
            .order_by(MessageORM.created_at)
        )
        return list(result.scalars().all())
    
    async def get_session(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
    ) -> Session | None:
        result = await db.execute(
            select(SessionORM)
            .where(SessionORM.id == session_id)
            .where(SessionORM.user_id == user_id)
        )
        orm = result.scalar_one_or_none()

        if orm is None:
            return None
        
        messages = await self.list_messages(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )
        return orm_to_session(
            orm,
            messages=[orm_to_message(m) for m in messages],
        )

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> list[Session]:
        result = await db.execute(
            select(SessionORM)
            .where(SessionORM.user_id == user_id)
            .order_by(SessionORM.updated_at.desc())
        )

        sessions = []
        for orm in result.scalars().all():
            sessions.append(orm_to_session(orm, messages=[]))

        return sessions

    async def get_message(
        self,
        db: AsyncSession,
        message_id: str,
        user_id: str,
    ) -> Message | None:
        """
        按 message_id 和 user_id 查询一条消息
        
        同时使用 user_id, 防止 用户读取其他人的消息
        """
        result = await db.execute(
            select(MessageORM)
            .where(MessageORM.id == message_id)
            .where(MessageORM.user_id == user_id)
        )

        orm = result.scalar_one_or_none()

        if orm is None:
            return None

        return orm_to_message(orm)

    async def list_messages_until(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        target_message_id: str,
    ) -> list[Message]:
        """
        查询某个 Session 中， 从第一条消息到指定消息为止的历史

        用于 regenerate：
        保留原用户消息，但排除消息之后失败或中断的 assistant 消息。
        """
        target_result = await db.execute(
            select(MessageORM)
            .where(MessageORM.id == target_message_id)
            .where(MessageORM.session_id == session_id)
            .where(MessageORM.user_id == user_id)
        )

        target =target_result.scalar_one_or_none()

        if target is None:
            return []

        result = await db.execute(
            select(MessageORM)
            .where(MessageORM.session_id == session_id)
            .where(MessageORM.user_id == user_id)
            .where(MessageORM.created_at <= target.created_at)
            .order_by(
                MessageORM.created_at.asc(),
                MessageORM.id.asc(),
            )
        )

        return [
            orm_to_message(orm)
            for orm in result.scalars().all()
        ]

class RunRepository:
    ACTIVE_HEARTBEAT_STATUSES = {
        AgentRunStatus.RUNNING.value,
        AgentRunStatus.WAITING_TOOL.value,
    }
    async def upsert_run(
        self,
        db: AsyncSession,
        run: AgentRun,
        *,
        commit: bool = True,
    ) -> None:
        existing = await db.get(AgentRunORM, run.id)
        
        if existing is None:
            db.add(self._to_orm(run))
        else:
            self._update_orm(existing, run)
        
        await _finish_write(db, commit=commit)

    async def claim_runtime(
        self,
        db: AsyncSession,
        *,
        run_id: str,
        user_id: str,
        runtime_id: str,
    ) -> AgentRun:
        """
        声明当前 Run， 由指定服务实例负责执行。
        """
        now = datetime.now(timezone.utc)

        result = await db.execute(
            update(AgentRunORM)
            .where(AgentRunORM.id == run_id)
            .where(AgentRunORM.user_id == user_id)
            .values(
                runtime_id=runtime_id,
                last_heartbeat_at=now,
                stale_detected_at=None,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            await db.rollback()
            raise KeyError(f"Run not found: {run_id}")

        await db.commit()

        run = await self.get_run_model(
            db=db,
            run_id=run_id,
            user_id=user_id,
        )

        if run is None:
            raise KeyError(f"Run not found: {run_id}")

        return run

    async def touch_heartbeat(
        self,
        db: AsyncSession,
        *,
        run_id: str,
        runtime_id: str,
    ) -> bool:
        """
        更新运行中 Run 的 Heartbeat。

        只允许当前 runtime 更新自己负责的 Run
        """
        now = datetime.now(timezone.utc)

        result = await db.execute(
            update(AgentRunORM)
            .where(AgentRunORM.id == run_id)
            .where(AgentRunORM.runtime_id == runtime_id)
            .where(
                AgentRunORM.status.in_(
                    self.ACTIVE_HEARTBEAT_STATUSES
                )
            )
            .values(
                last_heartbeat_at=now,
                updated_at=now
            )
        )
        await db.commit()

        return result.rowcount == 1

    async def find_stale_runs(
        self,
        db: AsyncSession,
        *,
        stale_after_seconds: int,
    ) -> list[AgentRun]:
        """
        查询 Heartbeat 已经过期的活动 Run。
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(
            seconds=stale_after_seconds
        )

        stale_condition = or_(
            AgentRunORM.last_heartbeat_at < cutoff,
            # A correctly-started active Run is claimed before it becomes
            # running. Missing both fields therefore identifies an orphaned
            # or legacy Run affected by the old heartbeat overwrite bug.
            and_(
                AgentRunORM.runtime_id.is_(None),
                AgentRunORM.last_heartbeat_at.is_(None),
            ),
            and_(
                AgentRunORM.last_heartbeat_at.is_(None),
                AgentRunORM.updated_at < cutoff,
            ),
        )

        result = await db.execute(
            select(AgentRunORM)
            .where(
                AgentRunORM.status.in_(
                    self.ACTIVE_HEARTBEAT_STATUSES
                )
            )
            .where(stale_condition)
            .order_by(AgentRunORM.updated_at.asc())
        )

        return [
            orm_to_agent_run(orm)
            for orm in result.scalars().all()
        ]

    async def mark_stale_interrupted(
        self,
        db: AsyncSession,
        *,
        run: AgentRun,
    ) -> AgentRun | None:
        """
        将 Stale Run 修复为 interrupted
        """
        now = datetime.now(timezone.utc)

        waiting_tool = (
            run.status == AgentRunStatus.WAITING_TOOL
        )

        error_type = (
            "stale_waiting_tool"
            if waiting_tool
            else "stale_run_detected"
        )

        error_detail = (
            "Run 在等待工具结果时停止 Heartbeat。"
            "工具可能已产生副作用，恢复前需要检查。"
            if waiting_tool
            else
            "Run 长时间未更新 Heartbeat，"
            "推断原执行进程已经终止。"
        )

        statement = (
            update(AgentRunORM)
            .where(AgentRunORM.id == run.id)
            .where(AgentRunORM.user_id == run.user_id)
            .where(
                AgentRunORM.status.in_(
                    self.ACTIVE_HEARTBEAT_STATUSES
                )
            )
        )

        # Compare-and-set the lease snapshot. If a heartbeat renewed the Run
        # after the stale scan, do not interrupt the live worker.
        if run.runtime_id is None:
            statement = statement.where(
                AgentRunORM.runtime_id.is_(None)
            )
        else:
            statement = statement.where(
                AgentRunORM.runtime_id == run.runtime_id
            )

        if run.last_heartbeat_at is None:
            statement = statement.where(
                AgentRunORM.last_heartbeat_at.is_(None)
            )
        else:
            statement = statement.where(
                AgentRunORM.last_heartbeat_at
                == run.last_heartbeat_at
            )

        result = await db.execute(
            statement.values(
                status=AgentRunStatus.INTERRUPTED.value,
                error_type=error_type,
                error_detail=error_detail,
                error_user_message=(
                    "任务执行已异常中断，可以尝试恢复。"
                ),
                stale_detected_at=now,
                completed_at=now,
                updated_at=now,
            )
        )

        if result.rowcount != 1:
            await db.rollback()
            return None

        await db.commit()

        repaired_run = await self.get_run_model(
            db=db,
            run_id=run.id,
            user_id=run.user_id,
        )

        if repaired_run is None:
            raise RuntimeError(
                f"修复后无法读取 Run： {run.id}"
            )

        return repaired_run
    
    async def get_run(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> AgentRunORM | None:
        result = await db.execute(
            select(AgentRunORM)
            .where(AgentRunORM.id == run_id)
            .where(AgentRunORM.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def list_runs_by_session(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
    ) -> list[AgentRunORM]:
        result = await db.execute(
            select(AgentRunORM)
            .where(AgentRunORM.session_id == session_id)
            .where(AgentRunORM.user_id == user_id)
            .order_by(AgentRunORM.created_at.desc())
        )
        return list(result.scalars().all())

    def _to_orm(self, run: AgentRun) -> AgentRunORM:
        return AgentRunORM(
            id=run.id,
            session_id=run.session_id,
            user_id=run.user_id,
            idempotency_key=run.idempotency_key,
            user_message_id=run.user_message_id,
            assistant_message_id=run.assistant_message_id,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            current_step=run.current_step,
            current_event=run.current_event,
            current_tool=run.current_tool,
            runtime_id=run.runtime_id,
            last_heartbeat_at=run.last_heartbeat_at,
            stale_detected_at=run.stale_detected_at,
            error_type=run.error_type,
            error_detail=run.error_detail,
            error_user_message=run.error_user_message,
            total_events=run.total_events,
            total_tool_calls=run.total_tool_calls,
            metadata_json=run.metadata,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            updated_at=run.updated_at,
        )

    def _update_orm(
        self,
        orm: AgentRunORM,
        run: AgentRun,
    ) -> None:
        orm.user_message_id = run.user_message_id
        orm.assistant_message_id = run.assistant_message_id
        orm.idempotency_key = run.idempotency_key
        orm.status = run.status.value if hasattr(run.status, "value") else str(run.status)
        orm.current_step = run.current_step
        orm.current_event = run.current_event
        orm.current_tool = run.current_tool
        # Lease-management fields are updated through separate database
        # sessions by claim_runtime/touch_heartbeat/reconciliation. Copying
        # their stale in-memory values here would overwrite fresh heartbeats.
        orm.error_type = run.error_type
        orm.error_detail = run.error_detail
        orm.error_user_message = run.error_user_message
        orm.total_events = run.total_events
        orm.total_tool_calls = run.total_tool_calls
        orm.metadata_json = run.metadata
        orm.started_at = run.started_at
        orm.completed_at = run.completed_at
        orm.updated_at = run.updated_at
    
    async def get_run_model(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> AgentRun | None:
        orm = await self.get_run(
            db=db,
            run_id=run_id,
            user_id=user_id,
        )
        if orm is None:
            return None
        
        return orm_to_agent_run(orm)
    
    async def list_run_models_by_session(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: str,
    ) -> list[AgentRun]:
        orms = await self.list_runs_by_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )
        return [orm_to_agent_run(orm) for orm in orms]


class TraceRepository:
    async def add_step(
        self,
        db: AsyncSession,
        step: RunStep,
        *,
        commit: bool = True,
    ) -> None:

        existing = await db.get(RunStepORM, step.id)

        if existing is not None:
            return

        db.add(
            RunStepORM(
                id=step.id,
                run_id=step.run_id,
                session_id=step.session_id,
                user_id=step.user_id,
                step_index=step.step_index,
                event_type=step.event_type,
                step_type=step.step_type.value,
                status=step.status.value,
                content=step.content,
                summary=step.summary,
                raw_event_data=step.raw_event_data,
                error_type=step.error_type,
                error_detail=step.error_detail,
                metadata_json=step.metadata,
                created_at=step.created_at,
                completed_at=step.completed_at,
            )
        )
        await _finish_write(db, commit=commit)

    async def add_tool_call(
        self,
        db: AsyncSession,
        record: ToolCallRecord,
    ) -> None:
        db.add(
            ToolCallRecordORM(
                id=record.id,
                run_id=record.run_id,
                session_id=record.session_id,
                user_id=record.user_id,
                step_index=record.step_index,
                tool_name=record.tool_name,
                tool_args=record.tool_args,
                status=record.status.value,
                success=record.success,
                result_preview=record.result_preview,
                result_raw=record.result_raw,
                error_type=record.error_type,
                error_detail=record.error_detail,
                is_dangerous=record.is_dangerous,
                approval_required=record.approval_required,
                approved=record.approved,
                metadata_json=record.metadata,
                created_at=record.created_at,
                completed_at=record.completed_at,
                duration_ms=record.duration_ms,
            )
        )
        await db.commit()

    async def list_steps(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> list[RunStepORM]:
        result = await db.execute(
            select(RunStepORM)
            .where(RunStepORM.run_id == run_id)
            .where(RunStepORM.user_id == user_id)
            .order_by(RunStepORM.step_index, RunStepORM.created_at)
        )
        return list(result.scalars().all())

    async def list_tool_calls(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> list[ToolCallRecordORM]:
        result = await db.execute(
            select(ToolCallRecordORM)
            .where(ToolCallRecordORM.run_id == run_id)
            .where(ToolCallRecordORM.user_id == user_id)
            .order_by(ToolCallRecordORM.step_index, ToolCallRecordORM.created_at)
        )
        return list(result.scalars().all())

    async def list_step_models(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> list[RunStep]:
        orms = await self.list_steps(
            db=db,
            run_id=run_id,
            user_id=user_id,
        )
        return [orm_to_run_step(orm) for orm in orms]
    
    async def list_tool_call_models(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> list[ToolCallRecord]:
        orms = await self.list_tool_calls(
            db=db,
            run_id=run_id,
            user_id=user_id,
        )
        return [orm_to_tool_call_record(orm) for orm in orms]
    
    async def upsert_tool_call(
        self,
        db: AsyncSession,
        record: ToolCallRecord,
    ) -> None:
        existing = await db.get(ToolCallRecordORM, record.id)

        if existing is None:
            await self.add_tool_call(db, record)
            return
        
        existing.status = record.status.value
        existing.success = record.success
        existing.result_preview = record.result_preview
        existing.result_raw = record.result_raw
        existing.error_type = record.error_type
        existing.error_detail = record.error_detail
        existing.is_dangerous = record.is_dangerous
        existing.approval_required = record.approval_required
        existing.approved = record.approved
        existing.metadata_json = record.metadata
        existing.completed_at = record.completed_at
        existing.duration_ms = record.duration_ms

        await db.commit()

class CheckpointRepository:

    async def add(
        self,
        db: AsyncSession,
        checkpoint: RunCheckpoint,
        *,
        commit: bool = True,
    ) -> None:
        db.add(
            RunCheckpointORM(
                id=checkpoint.id,
                run_id=checkpoint.run_id,
                session_id=checkpoint.session_id,
                user_id=checkpoint.user_id,
                step_index=checkpoint.step_index,
                checkpoint_type=checkpoint.checkpoint_type.value,
                messages_snapshot=checkpoint.messages_snapshot,
                accumulated_content=checkpoint.accumulated_content,
                last_event_type=checkpoint.last_event_type,
                metadata_json=checkpoint.metadata,
                created_at=checkpoint.created_at,
            )
        )
        await _finish_write(db, commit=commit)

    async def get_latest(
        self,
        db: AsyncSession,
        run_id: str,
        user_id: str,
    ) -> RunCheckpoint | None:
        result = await db.execute(
            select(RunCheckpointORM)
            .where(RunCheckpointORM.run_id == run_id)
            .where(RunCheckpointORM.user_id == user_id)
            .order_by(
                RunCheckpointORM.step_index.desc(),
                RunCheckpointORM.created_at.desc(),
            )
            .limit(1)
        )

        orm = result.scalar_one_or_none()

        if orm is None:
            return None
        
        return RunCheckpoint(
            id=orm.id,
            run_id=orm.run_id,
            session_id=orm.session_id,
            user_id=orm.user_id,
            step_index=orm.step_index,
            checkpoint_type=CheckpointType(orm.checkpoint_type),
            messages_snapshot=orm.messages_snapshot or [],
            accumulated_content=orm.accumulated_content,
            last_event_type=orm.last_event_type,
            metadata=orm.metadata_json or {},
            created_at=orm.created_at,
        )

session_repo = SessionRepository()
run_repo = RunRepository()
trace_repo = TraceRepository()
checkpoint_repo = CheckpointRepository()
