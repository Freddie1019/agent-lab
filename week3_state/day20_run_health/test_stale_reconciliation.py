import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import delete, select

from deep_research_agent.core.db.models import AgentRunORM, SessionORM
from deep_research_agent.core.db.session import AsyncSessionLocal
from deep_research_agent.core.run import AgentRunStatus
from deep_research_agent.services.run_health_service import run_health_service

async def main() -> None:
    suffix = uuid4().hex[:8]

    user_id = f"day20_user_{suffix}"
    session_id = f"day20_session_{suffix}"
    run_id = f"day20_run_{suffix}"

    stale_time = (
        datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    async with AsyncSessionLocal() as db:
        db.add(
            SessionORM(
                id=session_id,
                user_id=user_id,
                title="Day20 Stale Run Test",
                created_at=stale_time,
                updated_at=stale_time,
            )
        )
        db.add(
            AgentRunORM(
                id=run_id,
                session_id=session_id,
                user_id=user_id,
                status=AgentRunStatus.RUNNING.value,
                current_step=2,
                current_event="step_start",
                current_tool=None,
                total_events=3,
                total_tool_calls=0,
                metadata_json={
                    "test": "day20_stale_reconciliation"
                },
                runtime_id="dead-runtime-instance",
                last_heartbeat_at=stale_time,
                created_at=stale_time,
                started_at=stale_time,
                updated_at=stale_time,
            )
        )
        await db.commit()

    report = (
        await run_health_service.reconcile_stale_runs()
    )

    repaired_items = [
        item for item in report.items if item.run_id == run_id
    ]

    assert repaired_items, ("没有在协调报告中发现测试 Run")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentRunORM).where(
                AgentRunORM.id == run_id
            )
        )

        repaired_run = result.scalar_one()

        assert repaired_run.status == (
            AgentRunStatus.INTERRUPTED.value
        )

        assert repaired_run.error_type == (
            "stale_run_detected"
        )

        assert repaired_run.stale_detected_at is not None

        print("✅ Stale Run 已被修复")
        print("run_id =", repaired_run.id)
        print("status =", repaired_run.status)
        print("error_type =", repaired_run.error_type)

        # 清理测试数据
        await db.execute(
            delete(AgentRunORM)
            .where(AgentRunORM.id == run_id)
        )
        await db.execute(
            delete(SessionORM)
            .where(SessionORM.id == session_id)
        )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
