from dataclasses import dataclass
from sqlalchemy.exc import IntegrityError

from deep_research_agent.core.db.repositories import run_repo, session_repo
from deep_research_agent.core.db.session import AsyncSessionLocal
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.session import Message


def _is_idempotency_conflict(exc: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(exc.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name == "uq_agent_run_user_idempotency_key":
        return True

    detail = str(exc.orig).lower()
    return (
        "agent_runs.user_id" in detail
        and "agent_runs.idempotency_key" in detail
        and "unique" in detail
    )


class DuplicateAgentRequestError(Exception):
    def __init__(
        self,
        *,
        idempotency_key: str,
    ) -> None:
        self.idempotency_key = idempotency_key

        super().__init__(
            f"Duplicate agent request: "
            f"{idempotency_key}"
        )

@dataclass
class StartRunResult:
    user_message: Message
    run: AgentRun

class StatePersistenceService:
    """
    状态写入事务边界

    负责：
    1. 原子创建 User Message + AgentRun
    2. 原子保存 Assistant Message + Run 关联
    """ 
    async def start_run(
        self,
        *,
        session_id: str,
        user_id: str,
        user_message: Message,
        run: AgentRun,
    ) -> StartRunResult:
        """
        User Message + AgentRun 必须一起成功
        """

        try:
            async with AsyncSessionLocal.begin() as db:
                await session_repo.add_message(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    message=user_message,
                    commit=False,
                )

                await run_repo.upsert_run(
                    db=db,
                    run=run,
                    commit=False,
                )

        except IntegrityError as exc:
            # begin() context 会回滚事务
            if not _is_idempotency_conflict(exc):
                raise

            raise DuplicateAgentRequestError(
                idempotency_key=(run.idempotency_key or "")
            ) from exc

        return StartRunResult(
            user_message=user_message,
            run=run,
        )

    async def finalize_run(
        self,
        *,
        session_id: str,
        user_id: str,
        assistant_message: Message,
        run: AgentRun,
    ) -> None:
        """
        Assistant Message 和 Agent 结束状态必须一起提交
        """

        previous_assistant_message_id = run.assistant_message_id
        run.assistant_message_id = assistant_message.id

        try:
            async with AsyncSessionLocal.begin() as db:
                await session_repo.add_message(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    message=assistant_message,
                    commit=False,
                )

                await run_repo.upsert_run(
                    db=db,
                    run=run,
                    commit=False,
                )
        except Exception:
            # 数据库已回滚时，内存对象也不能保留未提交的关联。
            run.assistant_message_id = previous_assistant_message_id
            raise

state_persistence_service = StatePersistenceService()
