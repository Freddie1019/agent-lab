import asyncio
from uuid import uuid4

from sqlalchemy import select

from deep_research_agent.core.db.models import AgentRunORM, MessageORM, SessionORM
from deep_research_agent.core.db.session import AsyncSessionLocal
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.session import Message
from deep_research_agent.services.state_persistence_service import state_persistence_service

async def main() -> None:
    suffix = uuid4().hex[:8]
    user_id = f"day21_user_{suffix}"
    session_id = f"day21_session_{suffix}"

    # -------------------------
    # 准备 Session
    # -------------------------

    async with AsyncSessionLocal.begin() as db:
        db.add(
            SessionORM(
                id=session_id,
                user_id=user_id,
                title="Day21 Transaction Test",
            )
        )

    # -------------------------
    # 构造 User Message
    # -------------------------

    user_message = Message(
        role="user",
        content="Day21 transaction test",
        status="complete"
    )

    # -------------------------
    # 故意构造非法 Run：
    # session_id 指向不存在 Session
    #
    # Foreign Key 开启时应失败。
    # -------------------------

    invalid_run = AgentRun(
        session_id="missing_session",
        user_id=user_id,
        user_message_id=user_message.id,
        idempotency_key=f"tset-{suffix}",
    )

    try:
        await state_persistence_service.start_run(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            run=invalid_run,
        )
    except Exception as exc:
        print(
            "事务失败已捕获",
            type(exc).__name__,
        )

    # -------------------------
    # 验证 User Message
    # 也被 rollback
    # -------------------------

    async with AsyncSessionLocal() as db:
        message_result = await db.execute(
            select(MessageORM)
            .where(
                MessageORM.id
                == user_message.id
            )
        )

        stored_message = (
            message_result.scalar_one_or_none()
        )

        run_result = await db.execute(
            select(AgentRunORM)
            .where(
                AgentRunORM.id
                == invalid_run.id
            )
        )

        stored_run = (
            run_result.scalar_one_or_none()
        )

        assert stored_message is None
        assert stored_run is None

        print(
            "✅ Message 与 Run 均未写入"
        )
        print(
            "✅ Transaction Rollback 验证通过"
        )


if __name__ == "__main__":
    asyncio.run(main())