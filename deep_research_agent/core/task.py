from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    """后台任务的调度状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TASK_TRANSITIONS: dict[
    TaskStatus,
    set[TaskStatus],
] = {
    TaskStatus.QUEUED: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class InvalidTaskTransitionError(ValueError):
    """TaskRecord 发生非法状态跳转。"""


class TaskRecord(BaseModel):
    """一个可持久化、可查询的后台任务。"""

    id: str = Field(
        default_factory=lambda: f"task_{uuid4().hex}"
    )

    # 归属关系
    user_id: str
    session_id: str

    # 任务类型与状态
    task_type: str = "research"
    status: TaskStatus = TaskStatus.QUEUED

    # 幂等提交
    idempotency_key: str
    request_hash: str

    # Worker 未来执行任务所需的完整输入
    request_payload: dict[str, Any]

    # 终态错误
    error_type: str | None = None
    error_detail: str | None = None

    # 生命周期时间
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def transition_to(
        self,
        new_status: TaskStatus,
    ) -> None:
        """验证并执行状态转移。"""

        allowed = ALLOWED_TASK_TRANSITIONS[self.status]

        if new_status not in allowed:
            raise InvalidTaskTransitionError(
                "Illegal task transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        now = utc_now()

        self.status = new_status
        self.updated_at = now

        if new_status == TaskStatus.RUNNING:
            self.started_at = now

        if new_status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            self.completed_at = now

    def mark_failed(
        self,
        *,
        error_type: str,
        error_detail: str,
    ) -> None:
        """将 running Task 标记为失败。"""

        self.transition_to(TaskStatus.FAILED)
        self.error_type = error_type
        self.error_detail = error_detail

    def mark_cancelled(
        self,
        *,
        reason: str = "user_cancelled",
    ) -> None:
        """取消 queued 或 running Task。"""

        self.transition_to(TaskStatus.CANCELLED)
        self.error_type = "cancelled"
        self.error_detail = reason