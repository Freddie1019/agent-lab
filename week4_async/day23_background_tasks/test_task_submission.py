import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from deep_research_agent.core.db.base import Base
from deep_research_agent.core.db.models import (
    AgentRunORM,
    SessionORM,
    TaskRecordORM,
)
from deep_research_agent.core.db.repositories import (
    task_repo,
)
from deep_research_agent.services.task_service import (
    IdempotencyKeyReuseError,
    TaskSessionNotFoundError,
    TaskSubmissionService,
)


@pytest_asyncio.fixture
async def db_factory(tmp_path):
    database_path = tmp_path / "day23-service.db"

    engine = create_async_engine(
        "sqlite+aiosqlite:///"
        f"{database_path.as_posix()}"
    )

    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    yield factory

    await engine.dispose()


async def add_session(
    db_factory,
    *,
    session_id: str,
    user_id: str,
) -> None:
    async with db_factory() as db:
        db.add(
            SessionORM(
                id=session_id,
                user_id=user_id,
                title="Day23 test session",
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_submit_creates_queued_task_only(
    db_factory,
) -> None:
    await add_session(
        db_factory,
        session_id="session-alice",
        user_id="user-alice",
    )

    service = TaskSubmissionService(
        session_factory=db_factory
    )

    result = await service.submit(
        user_id="user-alice",
        session_id="session-alice",
        idempotency_key="submit-key-0001",
        request_payload={
            "question": "分析后台任务模型",
            "max_steps": 10,
            "max_tokens_budget": 50_000,
            "model": "gpt-4o-mini",
        },
    )

    assert result.created is True
    assert result.task.status.value == "queued"

    async with db_factory() as db:
        task_count = await db.scalar(
            select(func.count())
            .select_from(TaskRecordORM)
        )

        run_count = await db.scalar(
            select(func.count())
            .select_from(AgentRunORM)
        )

    assert task_count == 1
    assert run_count == 0


@pytest.mark.asyncio
async def test_same_request_returns_original_task(
    db_factory,
) -> None:
    await add_session(
        db_factory,
        session_id="session-alice",
        user_id="user-alice",
    )

    service = TaskSubmissionService(
        session_factory=db_factory
    )

    payload = {
        "question": "分析幂等任务提交",
        "max_steps": 10,
        "max_tokens_budget": 50_000,
        "model": "gpt-4o-mini",
    }

    first = await service.submit(
        user_id="user-alice",
        session_id="session-alice",
        idempotency_key="same-request-key",
        request_payload=payload,
    )

    second = await service.submit(
        user_id="user-alice",
        session_id="session-alice",
        idempotency_key="same-request-key",
        request_payload=payload,
    )

    assert first.created is True
    assert second.created is False
    assert second.task.id == first.task.id

    async with db_factory() as db:
        task_count = await db.scalar(
            select(func.count())
            .select_from(TaskRecordORM)
        )

    assert task_count == 1


@pytest.mark.asyncio
async def test_same_key_different_request_conflicts(
    db_factory,
) -> None:
    await add_session(
        db_factory,
        session_id="session-alice",
        user_id="user-alice",
    )

    service = TaskSubmissionService(
        session_factory=db_factory
    )

    await service.submit(
        user_id="user-alice",
        session_id="session-alice",
        idempotency_key="conflict-key-0001",
        request_payload={
            "question": "第一个研究问题",
            "max_steps": 10,
            "max_tokens_budget": 50_000,
            "model": "gpt-4o-mini",
        },
    )

    with pytest.raises(
        IdempotencyKeyReuseError
    ):
        await service.submit(
            user_id="user-alice",
            session_id="session-alice",
            idempotency_key="conflict-key-0001",
            request_payload={
                "question": "完全不同的研究问题",
                "max_steps": 10,
                "max_tokens_budget": 50_000,
                "model": "gpt-4o-mini",
            },
        )


@pytest.mark.asyncio
async def test_cannot_submit_to_another_users_session(
    db_factory,
) -> None:
    await add_session(
        db_factory,
        session_id="session-admin",
        user_id="user-admin",
    )

    service = TaskSubmissionService(
        session_factory=db_factory
    )

    with pytest.raises(
        TaskSessionNotFoundError
    ):
        await service.submit(
            user_id="user-alice",
            session_id="session-admin",
            idempotency_key="cross-user-key",
            request_payload={
                "question": "尝试越权提交任务",
                "max_steps": 10,
                "max_tokens_budget": 50_000,
                "model": "gpt-4o-mini",
            },
        )


@pytest.mark.asyncio
async def test_repository_filters_by_user(
    db_factory,
) -> None:
    await add_session(
        db_factory,
        session_id="session-alice",
        user_id="user-alice",
    )

    service = TaskSubmissionService(
        session_factory=db_factory
    )

    submitted = await service.submit(
        user_id="user-alice",
        session_id="session-alice",
        idempotency_key="isolation-key-0001",
        request_payload={
            "question": "验证任务用户隔离",
            "max_steps": 10,
            "max_tokens_budget": 50_000,
            "model": "gpt-4o-mini",
        },
    )

    async with db_factory() as db:
        alice_task = await task_repo.get(
            db=db,
            task_id=submitted.task.id,
            user_id="user-alice",
        )

        admin_task = await task_repo.get(
            db=db,
            task_id=submitted.task.id,
            user_id="user-admin",
        )

    assert alice_task is not None
    assert admin_task is None
    