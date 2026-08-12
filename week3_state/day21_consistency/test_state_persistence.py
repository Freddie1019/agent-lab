import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from deep_research_agent.core.db.base import Base
from deep_research_agent.core.db.models import AgentRunORM, MessageORM, SessionORM
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.session import Message
from deep_research_agent.services import state_persistence_service as service_module


@pytest.mark.asyncio
async def test_start_and_finalize_are_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(
        service_module,
        "AsyncSessionLocal",
        session_factory,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory.begin() as db:
        db.add(SessionORM(id="session-1", user_id="user-1"))

    user_message = Message(role="user", content="question")
    run = AgentRun(
        session_id="session-1",
        user_id="user-1",
        user_message_id=user_message.id,
        idempotency_key="request-0001",
    )
    await service_module.state_persistence_service.start_run(
        session_id="session-1",
        user_id="user-1",
        user_message=user_message,
        run=run,
    )

    run.mark_completed()
    assistant_message = Message(role="assistant", content="answer")
    await service_module.state_persistence_service.finalize_run(
        session_id="session-1",
        user_id="user-1",
        assistant_message=assistant_message,
        run=run,
    )

    async with session_factory() as db:
        persisted_run = await db.get(AgentRunORM, run.id)
        persisted_message = await db.get(MessageORM, assistant_message.id)

    assert persisted_run is not None
    assert persisted_message is not None
    assert persisted_run.assistant_message_id == assistant_message.id

    duplicate_message = Message(role="user", content="duplicate")
    duplicate_run = AgentRun(
        session_id="session-1",
        user_id="user-1",
        user_message_id=duplicate_message.id,
        idempotency_key="request-0001",
    )
    with pytest.raises(service_module.DuplicateAgentRequestError):
        await service_module.state_persistence_service.start_run(
            session_id="session-1",
            user_id="user-1",
            user_message=duplicate_message,
            run=duplicate_run,
        )

    async with session_factory() as db:
        duplicate_message_persisted = await db.get(
            MessageORM,
            duplicate_message.id,
        )

    assert duplicate_message_persisted is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_finalize_rolls_back_message_when_run_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(
        service_module,
        "AsyncSessionLocal",
        session_factory,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory.begin() as db:
        db.add(SessionORM(id="session-1", user_id="user-1"))
        db.add(
            AgentRunORM(
                id="existing-run",
                session_id="session-1",
                user_id="user-1",
                idempotency_key="request-0001",
                status="completed",
            )
        )

    conflicting_run = AgentRun(
        session_id="session-1",
        user_id="user-1",
        idempotency_key="request-0001",
    )
    assistant_message = Message(role="assistant", content="must roll back")

    with pytest.raises(IntegrityError):
        await service_module.state_persistence_service.finalize_run(
            session_id="session-1",
            user_id="user-1",
            assistant_message=assistant_message,
            run=conflicting_run,
        )

    async with session_factory() as db:
        message_count = await db.scalar(
            select(func.count())
            .select_from(MessageORM)
            .where(MessageORM.id == assistant_message.id)
        )
        conflicting_persisted_run = await db.get(
            AgentRunORM,
            conflicting_run.id,
        )

    assert message_count == 0
    assert conflicting_persisted_run is None
    assert conflicting_run.assistant_message_id is None

    await engine.dispose()
