import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
from uuid import uuid4

from deep_research_agent.core.db.models import (
    SessionORM,
)
from deep_research_agent.core.db.session import (
    AsyncSessionLocal,
)
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.session import Message
from deep_research_agent.services.state_persistence_service import (
    DuplicateAgentRequestError,
    state_persistence_service,
)
async def main() -> None:
    suffix = uuid4().hex[:8]

    user_id = f"user_{suffix}"
    session_id = f"session_{suffix}"

    idempotency_key = (
        f"request-{uuid4()}"
    )

    async with AsyncSessionLocal.begin() as db:
        db.add(
            SessionORM(
                id=session_id,
                user_id=user_id,
                title="Day21 Idempotency Test",
            )
        )

    # ==============================
    # 第一次请求
    # ==============================

    msg1 = Message(
        role="user",
        content="相同逻辑请求",
        status="complete",
    )

    run1 = AgentRun(
        session_id=session_id,
        user_id=user_id,
        user_message_id=msg1.id,
        idempotency_key=idempotency_key,
    )

    await state_persistence_service.start_run(
        session_id=session_id,
        user_id=user_id,
        user_message=msg1,
        run=run1,
    )

    print(
        "✅ 第一次请求成功:",
        run1.id,
    )

    # ==============================
    # 第二次请求
    # ==============================

    msg2 = Message(
        role="user",
        content="相同逻辑请求",
        status="complete",
    )

    run2 = AgentRun(
        session_id=session_id,
        user_id=user_id,
        user_message_id=msg2.id,

        # 完全相同
        idempotency_key=idempotency_key,
    )

    try:
        await state_persistence_service.start_run(
            session_id=session_id,
            user_id=user_id,
            user_message=msg2,
            run=run2,
        )

        raise AssertionError(
            "第二次请求不应该成功"
        )

    except DuplicateAgentRequestError:
        print(
            "✅ Duplicate Request 被阻止"
        )

    print(
        "✅ Idempotency 验证完成"
    )


if __name__ == "__main__":
    asyncio.run(main())