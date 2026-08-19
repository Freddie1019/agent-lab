import pytest

from deep_research_agent.core.task import (
    InvalidTaskTransitionError,
    TaskRecord,
    TaskStatus,
)

def make_task() -> TaskRecord:
    return TaskRecord(
        user_id="user_alice",
        session_id="session_alice",
        idempotency_key="task-model-key",
        request_hash="a" * 64,
        request_payload={
            "question": "分析 Agent 架构",
        },
    )

def test_task_starts_queued() -> None:
    task = make_task()

    assert task.status == TaskStatus.QUEUED
    assert task.started_at is None
    assert task.completed_at is None

def test_queued_task_can_start() -> None:
    task = make_task()

    task.transition_to(TaskStatus.RUNNING)

    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None
    assert task.completed_at is None


def test_running_task_can_complete() -> None:
    task = make_task()

    task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.COMPLETED)

    assert task.status == TaskStatus.COMPLETED
    assert task.started_at is not None
    assert task.completed_at is not None


def test_queued_task_can_cancel() -> None:
    task = make_task()

    task.mark_cancelled(
        reason="cancelled before worker claim"
    )

    assert task.status == TaskStatus.CANCELLED
    assert task.error_type == "cancelled"
    assert task.completed_at is not None


def test_completed_task_cannot_restart() -> None:
    task = make_task()

    task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.COMPLETED)

    with pytest.raises(
        InvalidTaskTransitionError
    ):
        task.transition_to(TaskStatus.RUNNING)


def test_queued_task_cannot_complete_directly() -> None:
    task = make_task()

    with pytest.raises(
        InvalidTaskTransitionError
    ):
        task.transition_to(TaskStatus.COMPLETED)