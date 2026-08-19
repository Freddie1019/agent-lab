import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from deep_research_agent.api.auth import (
    create_access_token,
)
from deep_research_agent.api.server import app
from deep_research_agent.api.v1.task_routers import (
    get_task_submission_service,
)
from deep_research_agent.core.db.base import Base
from deep_research_agent.core.db.models import (
    AgentRunORM,
    SessionORM,
)
from deep_research_agent.core.db.session import (
    get_db_session,
)
from deep_research_agent.services.task_service import (
    TaskSubmissionService,
)


def auth_headers(
    *,
    user_id: str,
    username: str,
) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id,
        username=username,
        role="user",
    )

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest_asyncio.fixture
async def api_context(tmp_path):
    database_path = tmp_path / "day23-api.db"

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

    async with factory() as db:
        db.add_all(
            [
                SessionORM(
                    id="session-alice",
                    user_id="user-alice",
                    title="Alice session",
                ),
                SessionORM(
                    id="session-admin",
                    user_id="user-admin",
                    title="Admin session",
                ),
            ]
        )
        await db.commit()

    service = TaskSubmissionService(
        session_factory=factory
    )

    async def override_db_session():
        async with factory() as db:
            yield db

    def override_task_service():
        return service

    app.dependency_overrides[
        get_db_session
    ] = override_db_session

    app.dependency_overrides[
        get_task_submission_service
    ] = override_task_service

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client, factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_task_api_flow(
    api_context,
) -> None:
    client, factory = api_context

    alice_headers = auth_headers(
        user_id="user-alice",
        username="alice",
    )
    alice_headers[
        "Idempotency-Key"
    ] = "api-task-key-0001"

    payload = {
        "session_id": "session-alice",
        "question": "分析后台任务领域模型",
        "max_steps": 10,
        "max_tokens_budget": 50_000,
        "model": "gpt-4o-mini",
    }

    first = await client.post(
        "/v1/tasks",
        headers=alice_headers,
        json=payload,
    )

    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    assert first.json()["created"] is True
    assert first.headers["location"].startswith(
        "/v1/tasks/task_"
    )

    task_id = first.json()["task_id"]

    replay = await client.post(
        "/v1/tasks",
        headers=alice_headers,
        json=payload,
    )

    assert replay.status_code == 202
    assert replay.json()["created"] is False
    assert replay.json()["task_id"] == task_id

    detail = await client.get(
        f"/v1/tasks/{task_id}",
        headers=alice_headers,
    )

    assert detail.status_code == 200
    assert detail.json()["id"] == task_id
    assert detail.json()["status"] == "queued"

    listing = await client.get(
        "/v1/tasks",
        headers=alice_headers,
    )

    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == task_id

    result = await client.get(
        f"/v1/tasks/{task_id}/result",
        headers=alice_headers,
    )

    assert result.status_code == 202
    assert result.json()["ready"] is False
    assert result.json()["run_id"] is None

    admin_headers = auth_headers(
        user_id="user-admin",
        username="admin",
    )

    forbidden_detail = await client.get(
        f"/v1/tasks/{task_id}",
        headers=admin_headers,
    )

    assert forbidden_detail.status_code == 404

    async with factory() as db:
        run_count = await db.scalar(
            select(func.count())
            .select_from(AgentRunORM)
        )

    assert run_count == 0


@pytest.mark.asyncio
async def test_idempotency_key_reuse_returns_409(
    api_context,
) -> None:
    client, factory = api_context
    del factory

    headers = auth_headers(
        user_id="user-alice",
        username="alice",
    )
    headers[
        "Idempotency-Key"
    ] = "api-conflict-key"

    first_payload = {
        "session_id": "session-alice",
        "question": "第一个后台研究任务",
        "max_steps": 10,
        "max_tokens_budget": 50_000,
        "model": "gpt-4o-mini",
    }

    second_payload = {
        "session_id": "session-alice",
        "question": "完全不同的后台研究任务",
        "max_steps": 10,
        "max_tokens_budget": 50_000,
        "model": "gpt-4o-mini",
    }

    first = await client.post(
        "/v1/tasks",
        headers=headers,
        json=first_payload,
    )

    conflict = await client.post(
        "/v1/tasks",
        headers=headers,
        json=second_payload,
    )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert (
        conflict.json()["detail"]["type"]
        == "idempotency_key_reuse"
    )