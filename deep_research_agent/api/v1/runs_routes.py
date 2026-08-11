from fastapi import APIRouter, Depends, HTTPException, status

from deep_research_agent.api.auth import CurrentUser, get_current_user
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.run_store import run_store

from deep_research_agent.core.run_trace import RunStep, ToolCallRecord
from deep_research_agent.core.run_trace_store import run_trace_store

# 添加 从 DB 读取 runs
from sqlalchemy.ext.asyncio import AsyncSession
from deep_research_agent.core.db.session import get_db_session
from deep_research_agent.core.db.repositories import run_repo, trace_repo, checkpoint_repo

# 添加检查点恢复接口
from deep_research_agent.core.recovery import RunRecoveryPlan
from deep_research_agent.services.recovery_service import recovery_service

# 添加 heartbeat 相关
from deep_research_agent.core.run_health import RunHealthResponse
from deep_research_agent.services.run_health_service import run_health_service

router = APIRouter(prefix="/v1",tags=["runs"])

@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db_session)
) -> AgentRun:
    run = await run_repo.get_run_model(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    return run

@router.get("/runs/{run_id}/health", response_model=RunHealthResponse)
async def get_run_health(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RunHealthResponse:
    run = await run_repo.get_run_model(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    
    return run_health_service.build_health_response(
        run
    )

@router.get("/sessions/{session_id}/runs", response_model=list[AgentRun])
async def list_session_runs(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[AgentRun]:
    return await run_repo.list_run_models_by_session(
        db=db,
        session_id=session_id,
        user_id=current_user.user_id,
    )

@router.get("/runs/{run_id}/steps", response_model=list[RunStep])
async def list_run_steps(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> list[RunStep]:
    # 先确认 run 存在且属于当前用户
    
    run = await run_repo.get_run_model(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    return await trace_repo.list_step_models(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )

@router.get("/runs/{run_id}/tool-calls", response_model=list[ToolCallRecord])
async def list_run_tool_calls(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ToolCallRecord]:
    # 先确认 run 存在且属于当前用户
    
    run = await run_repo.get_run_model(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return await trace_repo.list_tool_call_models(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )

@router.get("/runs/{run_id}/recovery-plan", response_model=RunRecoveryPlan,)
async def get_run_recovery_plan(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RunRecoveryPlan:
    """
    查询指定 Run 的恢复方案

    本接口只做决策，不执行恢复
    """

    # 1. 从数据库读取原 Run
    run = await run_repo.get_run_model(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found",
        )

    # 2. 读取最近的稳定 Checkpoint
    checkpoint = await checkpoint_repo.get_latest(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )

    # 3. 调用 Task6 已完成的 RecoveryService
    return recovery_service.build_plan(
        run=run,
        checkpoint=checkpoint
    )