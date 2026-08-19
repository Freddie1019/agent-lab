from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from deep_research_agent.api.auth import CurrentUser,get_current_user
from deep_research_agent.api.schemas.tasks import (
    TaskAcceptedResponse,
    TaskDetailResponse,
    TaskResultResponse,
    TaskSubmitRequest,
)
from deep_research_agent.core.db.repositories import run_repo, session_repo, task_repo
from deep_research_agent.core.db.session import get_db_session

from deep_research_agent.core.task import TaskRecord, TaskStatus
from deep_research_agent.services.task_service import (
    IdempotencyKeyReuseError,
    TaskSessionNotFoundError,
    TaskSubmissionService,
    task_submission_service,
)
router = APIRouter(prefix="/v1/tasks", tags=["tasks"])

def get_task_submission_service() -> (
    TaskSubmissionService
):
    return task_submission_service

def to_task_detail(
    task: TaskRecord,
) -> TaskDetailResponse:
    return TaskDetailResponse(
        id=task.id,
        user_id=task.user_id,
        session_id=task.session_id,
        task_type=task.task_type,
        status=task.status,
        request_payload=task.request_payload,
        error_type=task.error_type,
        error_detail=task.error_detail,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
        started_at=(
            task.started_at.isoformat()
            if task.started_at is not None
            else None
        ),
        completed_at=(
            task.completed_at.isoformat()
            if task.completed_at is not None
            else None
        ),
    )

@router.post("", response_model=TaskAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_task(
    request: TaskSubmitRequest,
    response:Response,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-key",
            min_length=8,
            max_length=128,
        ),
    ],
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    service: TaskSubmissionService = Depends(
        get_task_submission_service
    ),
) -> TaskAcceptedResponse:
    request_payload = {
        "question": request.question,
        "max_steps": request.max_steps,
        "max_tokens_budget": (
            request.max_tokens_budget
        ),
        "model": request.model,
    }

    try:
        result = await service.submit(
            user_id=current_user.user_id,
            session_id=request.session_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )

    except TaskSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "session_not_found",
                "message": "Session not found",
            },
        )

    except IdempotencyKeyReuseError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "idempotency_key_reuse",
                "message": (
                    "Idempotency-Key was already used "
                    "with different request content"
                ),
            },
        )

    task = result.task
    status_url = f"/v1/tasks/{task.id}"
    result_url = f"/v1/tasks/{task.id}/result"

    response.headers["Location"] = status_url

    return TaskAcceptedResponse(
        task_id=task.id,
        status=task.status,
        created=result.created,
        status_url=status_url,
        result_url=result_url,
    )

@router.get("", response_model=list[TaskDetailResponse])
async def list_tasks(
    task_status: Annotated[
        TaskStatus | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[TaskDetailResponse]:
    tasks = await task_repo.list_by_user(
        db=db,
        user_id=current_user.user_id,
        status=task_status,
        limit=limit,
    )

    return [
        to_task_detail(task)
        for task in tasks
    ]

@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TaskDetailResponse:
    task = await task_repo.get(
        db=db,
        task_id=task_id,
        user_id=current_user.user_id,
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return to_task_detail(task)

@router.get("/{task_id}/result",response_model=TaskResultResponse)
async def get_task_result(
    task_id: str,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TaskResultResponse:
    task = await task_repo.get(
        db=db,
        task_id=task_id,
        user_id=current_user.user_id,
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status in {
        TaskStatus.QUEUED,
        TaskStatus.RUNNING,
    }:
        response.status_code = (
            status.HTTP_202_ACCEPTED
        )

        return TaskResultResponse(
            task_id=task.id,
            status=task.status,
            ready=False,
        )
    latest_run = await run_repo.get_latest_run_by_task(
        db=db,
        task_id=task.id,
        user_id=current_user.user_id,
    )

    if task.status == TaskStatus.COMPLETED:
        if (
            latest_run is None or latest_run.assistant_message_id is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "task_result_inconsistent",
                    "message": (
                        "Completed task has no "
                        "assistant result"
                    ),
                }
            )
        assistant_message = await session_repo.get_message(
            db=db,
            message_id=(
                latest_run.assistant_message_id
            ),
            user_id=current_user.user_id,
        )
        if assistant_message is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "task_result_missing",
                    "message": (
                        "Assistant result message "
                        "was not found"
                    ),
                },
            )
        return TaskResultResponse(
            task_id=task_id,
            status=task.status,
            ready=True,
            run_id=latest_run.id,
            answer=assistant_message.content,
        )
    return TaskResultResponse(
        task_id=task.id,
        status=task.status,
        ready=True,
        run_id=(
            latest_run.id
            if latest_run is not None
            else None
        ),
        error_type=(
            task.error_type
            or (
                latest_run.error_type
                if latest_run is not None
                else None
            )
        ),
        error_detail=(
            task.error_detail
            or (
                latest_run.error_detail
                if latest_run is not None
                else None
            )
        ),
    )
