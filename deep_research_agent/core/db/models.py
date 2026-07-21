from datetime import datetime
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from deep_research_agent.core.db.base import Base

class SessionORM(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] =mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
    updated_at: Mapped[datetime] =mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )

    messages: Mapped[list["MessageORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    runs: Mapped[list["AgentRunORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan"
    )

class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    session_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sessions.id"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        default="complete",
        nullable=False,
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )

    session: Mapped["SessionORM"] = relationship(back_populates="messages")

class AgentRunORM(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    session_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sessions.id"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    user_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assistant_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    current_event: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_tool: Mapped[str | None] = mapped_column(String(128), nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_user_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    session: Mapped["SessionORM"] = relationship(back_populates="runs")

    steps: Mapped[list["RunStepORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )

    tool_calls: Mapped[list["ToolCallRecordORM"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )

class RunStepORM(Base):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("agent_runs.id"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_event_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped["AgentRunORM"] = relationship(back_populates="steps")

class ToolCallRecordORM(Base):
    __tablename__ = "tool_call_records"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("agent_runs.id"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    tool_args: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    result_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_dangerous: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped["AgentRunORM"] = relationship(
        back_populates="tool_calls"
    )

class RunCheckpointORM(Base):
    __tablename__ = "run_checkpoints"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("agent_runs.id"),
        index=True,
        nullable=False
    )

    session_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
    )

    step_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    checkpoint_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    messages_snapshot: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )

    accumulated_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_event_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )