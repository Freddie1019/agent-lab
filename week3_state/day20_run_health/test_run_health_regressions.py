import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from deep_research_agent.core.db.base import Base
from deep_research_agent.core.db.models import AgentRunORM, SessionORM
from deep_research_agent.core.db.repositories import run_repo
from deep_research_agent.core.run import AgentRun, AgentRunStatus
from deep_research_agent.services import run_health_service as health_module
from deep_research_agent.services.run_health_service import RunHealthService


@pytest_asyncio.fixture
async def db_factory(tmp_path):
    database_path = tmp_path / "run-health.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield factory
    await engine.dispose()


async def _add_session(db_factory, session_id: str, user_id: str) -> None:
    async with db_factory() as db:
        db.add(
            SessionORM(
                id=session_id,
                user_id=user_id,
                title="Run health regression test",
            )
        )
        await db.commit()


async def _get_run(db_factory, run_id: str, user_id: str) -> AgentRun:
    async with db_factory() as db:
        run = await run_repo.get_run_model(db, run_id, user_id)
    assert run is not None
    return run


@pytest.mark.asyncio
async def test_event_upsert_preserves_runtime_lease(db_factory):
    session_id = "session-preserve-lease"
    user_id = "user-preserve-lease"
    await _add_session(db_factory, session_id, user_id)

    run = AgentRun(
        id="run-preserve-lease",
        session_id=session_id,
        user_id=user_id,
        status=AgentRunStatus.RUNNING,
    )
    assert run.created_at.utcoffset() == timedelta(0)

    async with db_factory() as db:
        await run_repo.upsert_run(db, run)

    async with db_factory() as db:
        await run_repo.claim_runtime(
            db,
            run_id=run.id,
            user_id=user_id,
            runtime_id="runtime-alive",
        )

    # This is the stale in-memory object held by the streaming request. Its
    # lease fields are still None when the next agent event is persisted.
    run.update_event("step_start")
    async with db_factory() as db:
        await run_repo.upsert_run(db, run)

    persisted = await _get_run(db_factory, run.id, user_id)
    assert persisted.runtime_id == "runtime-alive"
    assert persisted.last_heartbeat_at is not None


@pytest.mark.asyncio
async def test_reconciliation_repairs_legacy_orphan_with_local_time(
    db_factory,
    monkeypatch,
):
    session_id = "session-legacy-orphan"
    user_id = "user-legacy-orphan"
    run_id = "run-legacy-orphan"
    await _add_session(db_factory, session_id, user_id)

    # Reproduce a pre-fix row: local wall-clock time was written without a
    # timezone and the runtime/heartbeat fields were overwritten with NULL.
    legacy_local_time = datetime.now() + timedelta(hours=8)
    async with db_factory() as db:
        db.add(
            AgentRunORM(
                id=run_id,
                session_id=session_id,
                user_id=user_id,
                status=AgentRunStatus.RUNNING.value,
                current_step=2,
                total_events=6,
                total_tool_calls=1,
                metadata_json={},
                runtime_id=None,
                last_heartbeat_at=None,
                created_at=legacy_local_time,
                started_at=legacy_local_time,
                updated_at=legacy_local_time,
            )
        )
        await db.commit()

    monkeypatch.setattr(health_module, "AsyncSessionLocal", db_factory)
    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: SimpleNamespace(
            RUN_STALE_AFTER_SECONDS=20,
            RUN_RECONCILE_INTERVAL_SECONDS=1,
            RUN_HEARTBEAT_INTERVAL_SECONDS=1,
        ),
    )

    report = await RunHealthService().reconcile_stale_runs()
    persisted = await _get_run(db_factory, run_id, user_id)

    assert report.repaired_count == 1
    assert persisted.status == AgentRunStatus.INTERRUPTED
    assert persisted.error_type == "stale_run_detected"


@pytest.mark.asyncio
async def test_periodic_reconciler_repairs_crashed_runtime(
    db_factory,
    monkeypatch,
):
    session_id = "session-periodic-repair"
    user_id = "user-periodic-repair"
    run_id = "run-periodic-repair"
    await _add_session(db_factory, session_id, user_id)

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=5)
    async with db_factory() as db:
        db.add(
            AgentRunORM(
                id=run_id,
                session_id=session_id,
                user_id=user_id,
                status=AgentRunStatus.RUNNING.value,
                current_step=1,
                total_events=2,
                total_tool_calls=0,
                metadata_json={},
                runtime_id="dead-runtime",
                last_heartbeat_at=stale_time,
                created_at=stale_time,
                started_at=stale_time,
                updated_at=stale_time,
            )
        )
        await db.commit()

    monkeypatch.setattr(health_module, "AsyncSessionLocal", db_factory)
    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: SimpleNamespace(
            RUN_STALE_AFTER_SECONDS=1,
            RUN_RECONCILE_INTERVAL_SECONDS=0.01,
            RUN_HEARTBEAT_INTERVAL_SECONDS=1,
        ),
    )

    service = RunHealthService()
    handle = service.start_reconciler()
    try:
        for _ in range(50):
            persisted = await _get_run(db_factory, run_id, user_id)
            if persisted.status == AgentRunStatus.INTERRUPTED:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("periodic reconciliation did not repair the stale Run")
    finally:
        await handle.stop()


@pytest.mark.asyncio
async def test_reconciliation_does_not_interrupt_renewed_lease(db_factory):
    session_id = "session-renewed-lease"
    user_id = "user-renewed-lease"
    run_id = "run-renewed-lease"
    await _add_session(db_factory, session_id, user_id)

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=30)
    async with db_factory() as db:
        db.add(
            AgentRunORM(
                id=run_id,
                session_id=session_id,
                user_id=user_id,
                status=AgentRunStatus.RUNNING.value,
                current_step=1,
                total_events=2,
                total_tool_calls=0,
                metadata_json={},
                runtime_id="live-runtime",
                last_heartbeat_at=stale_time,
                created_at=stale_time,
                started_at=stale_time,
                updated_at=stale_time,
            )
        )
        await db.commit()

    async with db_factory() as db:
        stale_snapshot = (
            await run_repo.find_stale_runs(
                db,
                stale_after_seconds=20,
            )
        )[0]

    async with db_factory() as db:
        assert await run_repo.touch_heartbeat(
            db,
            run_id=run_id,
            runtime_id="live-runtime",
        )

    async with db_factory() as db:
        repaired = await run_repo.mark_stale_interrupted(
            db,
            run=stale_snapshot,
        )

    persisted = await _get_run(db_factory, run_id, user_id)
    assert repaired is None
    assert persisted.status == AgentRunStatus.RUNNING
