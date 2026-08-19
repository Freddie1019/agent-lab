import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from deep_research_agent.core.db.models import SessionORM
from deep_research_agent.core.db.repositories import task_repo
from deep_research_agent.core.db.session import AsyncSessionLocal
from deep_research_agent.core.task import TaskRecord

def make_request_hash(
    *,
    session_id: str,
    task_type: str,
    request_payload: dict[str, Any],
) -> str:
    """生成稳定的业务请求指纹"""

    fingerprint_payload = {
        "session_id": session_id,
        "task_type": task_type,
        "request_payload": request_payload,
    }

    canonical = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

def is_task_idempotency_conflict(
    exc: IndentationError,
) -> bool:
    """兼容 PostgreSQL 和 SQLite 的唯一约束判断"""

    constraint_name = getattr(
        getattr(exc.orig, "diag", None),
        "constraint_name",
        None,
    )

    if constraint_name == "uq_task_user_idempotency_key":
        return True

    detail = str(exc.orig).lower()

    return (
        "task_records.user_id" in detail
        and "task_records.idempotency_key" in detail
        and "unique" in detail
    )

class TaskSessionNotFoundError(Exception):
    def __init__(
        self,
        session_id: str,
    ) -> None:
        self.session_id = session_id

        super().__init__(
            f"Session not found: {session_id}"
        )

class IdempotencyKeyReuseError(Exception):
    def __init__(
        self,
        idempotency_key: str,
    ) -> None:
        self.idempotency_key = idempotency_key

        super().__init__(
            "Idempotency key was reused with "
            f"different request content: {idempotency_key}"
        )


@dataclass
class SubmitTaskResult:
    task: TaskRecord
    created: bool

class TaskSubmissionService:
    def __init__(
        self,
        session_factory=AsyncSessionLocal,
    ) -> None:
        self.session_factory = session_factory

    async def submit(
        self,
        *,
        user_id: str,
        session_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
        task_type: str = "research",
    ) -> SubmitTaskResult:
        request_hash = make_request_hash(
            session_id=session_id,
            task_type=task_type,
            request_payload=request_payload,
        )

        task = TaskRecord(
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_payload=request_payload,
        )

        try:
            async with self.session_factory.begin() as db:
                owned_session_id = await db.scalar(
                    select(SessionORM.id)
                    .where(SessionORM.id == session_id)
                    .where(SessionORM.user_id == user_id)
                )

                if owned_session_id is None:
                    raise TaskSessionNotFoundError(
                        session_id
                    )

                await task_repo.add(
                    db=db,
                    task=task,
                    commit=False,
                )

        except IntegrityError as exc:
            if not is_task_idempotency_conflict(exc):
                raise

            async with self.session_factory() as db:
                existing = (
                    await task_repo.get_by_idempotency_key(
                        db=db,
                        user_id=user_id,
                        idempotency_key=idempotency_key,
                    )
                )

            if existing is None:
                raise

            if existing.request_hash != request_hash:
                raise IdempotencyKeyReuseError(
                    idempotency_key
                ) from exc

            return SubmitTaskResult(
                task=existing,
                created=False,
            )
        return SubmitTaskResult(
            task=task,
            created=True,
        )

task_submission_service = TaskSubmissionService()
