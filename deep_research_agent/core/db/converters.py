from deep_research_agent.core.db.models import (
    AgentRunORM,
    MessageORM,
    RunStepORM,
    SessionORM,
    ToolCallRecordORM,
    TaskRecordORM,
)
from deep_research_agent.core.run import AgentRun, AgentRunStatus
from deep_research_agent.core.run_trace import (
    RunStep,
    RunStepStatus,
    RunStepType,
    ToolCallRecord,
    ToolCallStatus,
)
from deep_research_agent.core.session import Message, Session

from deep_research_agent.core.task import TaskRecord, TaskStatus

def orm_to_message(orm: MessageORM) -> Message:
    return Message(
        id=orm.id,
        role=orm.role,
        content=orm.content,
        status=orm.status,
        error_detail=orm.error_detail,
        created_at=orm.created_at,
    )

def orm_to_session(
    orm: SessionORM,
    messages: list[Message] | None = None,
) -> Session:
    return Session(
        id=orm.id,
        user_id=orm.user_id,
        title=orm.title,
        messages=messages or [],
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )

def orm_to_agent_run(orm: AgentRunORM) -> AgentRun:
    return AgentRun(
        id=orm.id,
        session_id=orm.session_id,
        user_id=orm.user_id,
        task_id=orm.task_id,
        idempotency_key=orm.idempotency_key,
        user_message_id=orm.user_message_id,
        assistant_message_id=orm.assistant_message_id,
        status=AgentRunStatus(orm.status),
        current_step=orm.current_step,
        current_event=orm.current_event,
        current_tool=orm.current_tool,
        runtime_id=orm.runtime_id,
        last_heartbeat_at=orm.last_heartbeat_at,
        stale_detected_at=orm.stale_detected_at,
        error_type=orm.error_type,
        error_detail=orm.error_detail,
        error_user_message=orm.error_user_message,
        total_events=orm.total_events,
        total_tool_calls=orm.total_tool_calls,
        metadata=orm.metadata_json or {},
        created_at=orm.created_at,
        started_at=orm.started_at,
        completed_at=orm.completed_at,
        updated_at=orm.updated_at,
    )

def orm_to_run_step(orm: RunStepORM) -> RunStep:
    return RunStep(
        id=orm.id,
        run_id=orm.run_id,
        session_id=orm.session_id,
        user_id=orm.user_id,
        step_index=orm.step_index,
        event_type=orm.event_type,
        step_type=RunStepType(orm.step_type),
        status=RunStepStatus(orm.status),
        content=orm.content,
        summary=orm.summary,
        raw_event_data=orm.raw_event_data or {},
        error_type=orm.error_type,
        error_detail=orm.error_detail,
        metadata=orm.metadata_json or {},
        created_at=orm.created_at,
        completed_at=orm.completed_at,
    )

def orm_to_task_record(orm: TaskRecordORM) -> TaskRecord:
    return TaskRecord(
        id=orm.id,
        user_id=orm.user_id,
        session_id=orm.session_id,
        task_type=orm.task_type,
        status=TaskStatus(orm.status),
        idempotency_key=orm.idempotency_key,
        request_hash=orm.request_hash,
        request_payload=orm.request_payload or {},
        error_type=orm.error_type,
        error_detail=orm.error_detail,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        started_at=orm.started_at,
        completed_at=orm.completed_at,
    )

def orm_to_tool_call_record(orm: ToolCallRecordORM) -> ToolCallRecord:
    return ToolCallRecord(
        id=orm.id,
        run_id=orm.run_id,
        session_id=orm.session_id,
        user_id=orm.user_id,
        step_index=orm.step_index,
        tool_name=orm.tool_name,
        tool_args=orm.tool_args or {},
        status=ToolCallStatus(orm.status),
        success=orm.success,
        result_preview=orm.result_preview,
        result_raw=orm.result_raw,
        error_type=orm.error_type,
        error_detail=orm.error_detail,
        is_dangerous=orm.is_dangerous,
        approval_required=orm.approval_required,
        approved=orm.approved,
        metadata=orm.metadata_json or {},
        created_at=orm.created_at,
        completed_at=orm.completed_at,
        duration_ms=orm.duration_ms,
    )

