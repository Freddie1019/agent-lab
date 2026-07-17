from fastapi import APIRouter, Depends, HTTPException, status

from deep_research_agent.api.auth import CurrentUser, get_current_user
from deep_research_agent.core.run import AgentRun
from deep_research_agent.core.run_store import run_store

from deep_research_agent.core.run_trace import RunStep, ToolCallRecord
from deep_research_agent.core.run_trace_store import run_trace_store

router = APIRouter(prefix="/v1",tags=["runs"])

@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user), 
) -> AgentRun:
    try:
        return await run_store.get(
            run_id=run_id,
            user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
@router.get("/sessions/{session_id}/runs", response_model=list[AgentRun])
async def list_session_runs(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AgentRun]:
    return await run_store.list_by_session(
        session_id=session_id,
        user_id=current_user.user_id,
    )

@router.get("/runs/{run_id}/steps", response_model=list[RunStep])
async def list_run_steps(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RunStep]:
    # 先确认 run 存在且属于当前用户
    try:
        await run_store.get(
            run_id=run_id,
            user_id=current_user.user_id
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    return await run_trace_store.list_steps(
        run_id=run_id,
        user_id=current_user.user_id,
    )

@router.get("/runs/{run_id}/tool-calls", response_model=list[ToolCallRecord])
async def list_run_tool_calls(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ToolCallRecord]:
    # 先确认 run 存在且属于当前用户
    try:
        await run_store.get(
            run_id=run_id,
            user_id=current_user.user_id
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return await run_trace_store.list_tool_calls(
        run_id=run_id,
        user_id=current_user.user_id,
    )