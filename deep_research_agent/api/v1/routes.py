"""
API v1 路由
"""
import json
import asyncio
from itertools import accumulate
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from shared.rate_limiter import tracker
from fastapi.responses import StreamingResponse
from deep_research_agent.core.events import AgentEvent
from deep_research_agent.core.agent import ResearchAgent
from deep_research_agent.core.domain import ResearchTask
from deep_research_agent.api.schemas.v1 import ResearchRequest, ResearchResponse

from deep_research_agent.core.session_store import session_store
from deep_research_agent.core.session import Message
from deep_research_agent.core.events import AgentEvent, make_error_event

from deep_research_agent.api.auth import CurrentUser, get_current_user

# 添加 run 存储
from deep_research_agent.core.run_store import run_store

# 添加 run 追溯
from deep_research_agent.core.run_trace_store import run_trace_store

# 落库
from sqlalchemy.ext.asyncio import AsyncSession
from deep_research_agent.core.db.session import get_db_session
from deep_research_agent.core.db.repositories import run_repo, trace_repo, session_repo

# checkpoint检查点恢复
from deep_research_agent.core.recovery import RunRecoveryPlan
from deep_research_agent.services.recovery_service import recovery_service
from deep_research_agent.core.db.repositories import checkpoint_repo

async def _get_session_for_runtime(
    session_id: str,
    user_id: str,
    db: AsyncSession,
):
    """
    运行时获取 session

    优先用内存 session_store
    如果内存没有，则从数据库恢复
    """
    try:
        return await session_store.get(session_id, user_id)
    except Exception:
        db_session_model = await session_repo.get_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )

        if db_session_model is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )
         # 恢复到内存，保证后续 to_llm_messages / lock 逻辑可用
        # 这里根据你的 session_store 是否有 put/set 方法调整
        if hasattr(session_store, "put"):
            await session_store.put(db_session_model)
        elif hasattr(session_store, "set"):
            await session_store.set(db_session_model)
        else:
            # 如果没有 put/set，短期可以直接返回 db_session_model
            # 但 lock 仍然使用 session_store.get_lock(session_id)
            pass

        return db_session_model


# tracker.set_limit("web_search", 0)
class ChatInSessionRequest(BaseModel):
    """ 在某个会话中追加一条消息 """
    question: str = Field(..., min_length=1, max_length=2000)
    max_steps: int = Field(default=10, ge=1, le=30)

router = APIRouter(prefix="/v1", tags=["v1"])

@router.post("/research", response_model=ResearchResponse)
def create_research(request: ResearchRequest):
    # ★ 防腐层：API 模型 → 领域模型
    task = ResearchTask.from_api_request(request)

    agent = ResearchAgent(
        model=task.model,
        max_steps=task.max_steps,
        max_tokens_budget=task.max_tokens_budget,
        verbose=False,
    )
    
    report = agent.run(task.question)
    
    return ResearchResponse(
        status=report.status,
        answer=report.final_answer,
        steps=report.steps,
        tool_calls=report.tool_calls,
        duration_seconds=report.duration_seconds,
        total_tokens=report.total_tokens,
        estimated_cost_usd=report.estimated_cost_usd,
        errors=report.errors,
    )

@router.post("/research/stream")
async def stream_research(
        request: ResearchRequest,
        raw_request: Request,
    ):
    """
    流式研究接口
    
    返回 text/event-stream 格式的事件流
    
    事件类型:
      - agent_start: Agent 开始
      - step_start: 新步骤开始
      - thought: Agent 思考
      - tool_call: 调用工具
      - tool_result: 工具结果
      - answer_complete: 答案完成
      - agent_complete: Agent 完成
      - error: 错误
    """
    agent = ResearchAgent(
        model=request.model,
        max_steps=request.max_steps,
        max_tokens_budget=request.max_tokens_budget,
        verbose=False,
    )
    async def event_generator():
        try:
            async for event in agent.stream(request.question):
                # ★ 关键：每个事件前检查客户端是否断连
                if await raw_request.is_disconnected():
                    print(f"⚠️ 客户端已断开，提前终止 Agent")
                    break

                yield event.to_sse()
            # 流结束标志
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as e:
            # 流式过程中出错
            err_event = AgentEvent(
                type="error",
                data={"error_type": "internal_error", "message": str(e)},
            )
            yield err_event.to_sse()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # ★ Nginx 不要缓冲
        },
    )

@router.post("/sessions/{session_id}/chat/stream")
async def chat_in_session_stream(
    session_id: str,
    request: ChatInSessionRequest,
    raw_request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """在指定会话中流式提问"""
    # 1. 校验所有权
    session = await _get_session_for_runtime(
        session_id=session_id, 
        user_id=current_user.user_id,
        db=db,
    )

    await session_repo.upsert_session(db, session)

    # 2. 检查会话锁（防并发）
    lock = session_store.get_lock(session_id)
    if lock.locked():
        raise HTTPException(409, "Session is currently processing another request")
    
    # 3. 创建用户消息
    user_msg = Message(
        role="user",
        content=request.question,
        status="complete",
    )

    # 4. 先写内存
    await session_store.append_messages(
        session_id=session_id,
        user_id=current_user.user_id,
        messages=[user_msg],
    )

    # 5. 再写数据库
    await session_repo.add_message(
        db=db,
        session_id=session_id,
        user_id=current_user.user_id,
        message=user_msg,
    )

    # 6. 现在从 Session 重新构造 history
    history = session.to_llm_messages()

    # 7. 创建 run, 并关联 user_message_id
    run = await run_store.create(
        session_id=session_id,
        user_id=current_user.user_id,
        user_message_id=user_msg.id,
        metadata={
            "question": request.question,
            "entrypoint": "chat_stream",
        },
    )
    await run_repo.upsert_run(db, run)

    # 8. 创建 Agent
    agent = ResearchAgent(
        run_id=run.id,
        session_id=session_id,
        user_id=current_user.user_id,
        db=db,
        max_steps=request.max_steps,
        verbose=False,
    )

    async def event_generator():
        async with lock:
            session.is_processing = True
            
            # 新增状态变量 Day12
            process_fragments: list[str] = []  # 多步过程内容，仅用于中断时兜底
            collected_assistant_msg = ""      # 仅 answer_complete 的答案，用于持久化
            last_error_data: Optional[dict] = None
            completed_normally = False

            try:
                # 先告诉客户端 run_id
                run_created = AgentEvent(
                    type="agent_start",
                    data={
                        "run_id": run.id,
                        "session_id": session_id,
                        "message": "Agent run created",
                    },
                )

                updated_run = await run_store.update_from_event(
                    run_id=run.id,
                    event_type=run_created.type,
                    step=run_created.step,
                    data=run_created.data,
                )
                await run_repo.upsert_run(db, updated_run)

                yield run_created.to_sse()

                # ★ 调用 Agent 时把历史传进去
                async for event in agent.stream_with_history(
                    messages=history,
                ):

                    if await raw_request.is_disconnected():
                        interrupted_run = await run_store.mark_interrupted(
                            run_id=run.id,
                            reason="client_disconnected",
                        )
                        await run_repo.upsert_run(db, interrupted_run)
                        print(f"Client disconnected, cancelling session {session_id}")
                        break
                    
                    # 1. 根据 event 更新 run 整体状态
                    updated_run = await run_store.update_from_event(
                        run_id=run.id,
                        event_type=event.type,
                        step=event.step,
                        data=event.data
                    )
                    await run_repo.upsert_run(db, updated_run)

                    # 2. 记录 RunStep / ToolCallRecord
                    trace_result = await run_trace_store.record_event(
                        run_id=run.id,
                        session_id=session_id,
                        user_id=current_user.user_id,
                        event_type=event.type,
                        step_index=event.step,
                        data=event.data,
                    )
                    if trace_result is not None:
                        if trace_result.step is not None:
                            await trace_repo.add_step(db, trace_result.step)

                        if trace_result.tool_call_created is not None:
                            await trace_repo.add_tool_call(
                                db,
                                trace_result.tool_call_created,
                            )

                        if trace_result.tool_call_updated is not None:
                            await trace_repo.upsert_tool_call(
                                db,
                                trace_result.tool_call_updated,
                            )

                    # Day12: 分别维护"过程内容"和"最终回答"
                    # thought 是推理过程，不应直接当作最终回答持久化
                    if event.type == "thought":
                        content = event.data.get("content", "")
                        if content:
                            process_fragments.append(content)
                    elif event.type == "answer_complete":
                        collected_assistant_msg = event.data.get("answer", "")
                    
                    # 记录最后一次错误
                    if event.type == "error":
                        last_error_data = event.data
                    
                    # 标记正常完成
                    if event.type == "agent_complete":
                        if event.data.get("status") == "success":
                            completed_normally = True
                    
                    yield event.to_sse()
                
                yield "event: done\ndata: [DONE]\n\n"

            except Exception as e:
                # event_generator 自己挂了 （极少见）

                failed_run = await run_store.mark_failed(
                    run_id=run.id,
                    error_type="internal_error",
                    error_detail=str(e),
                    error_user_message="服务内部错误，请稍后重试",
                )
                await run_repo.upsert_run(db, failed_run)

                accumulated_content = "\n\n".join(process_fragments)
                err_event = make_error_event(
                    type="internal_error",
                    title="Internal Server Error",
                    detail=str(e),
                    user_message="服务内部错误，请重试",
                    accumulated_content=accumulated_content or None
                )
                yield err_event.to_sse()
            
            finally:
                # 关键：无论如何都持久化
                # 优先保存 answer_complete 的答案；若没有则用过程内容兜底

                latest_run = await run_store.get(run.id, user_id=current_user.user_id)

                if (
                    latest_run.status.value
                    not in {"completed", "failed", "interrupted", "cancelled"}
                ):
                    if completed_normally:
                        latest_run = await run_store.mark_completed(run.id)
                    elif last_error_data:
                        latest_run = await run_store.mark_failed(
                            run_id=run.id,
                            error_type=last_error_data.get("type", "stream_error"),
                            error_detail=json.dumps(
                                last_error_data,
                                ensure_ascii=False,
                            ),
                            error_user_message=last_error_data.get("user_message"),
                        )
                    else:
                        latest_run = await run_store.mark_interrupted(
                            run_id=run.id,
                            reason="stream_finished_without_completion",
                        )
                    await run_repo.upsert_run(db, latest_run)

                accumulated_content = (
                    collected_assistant_msg or "\n\n".join(process_fragments)
                )
                assistant_msg = await _persist_assistant_message(
                    session_id=session_id,
                    user_id=current_user.user_id,
                    accumulated_content=accumulated_content,
                    completed_normally=completed_normally,
                    last_error_data=last_error_data,
                    db=db,
                )
                latest_run.assistant_message_id = assistant_msg.id
                await run_store.update(latest_run)
                await run_repo.upsert_run(db, latest_run)
                
                session.is_processing = False
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

async def _persist_assistant_message(
    *,
    session_id: str,
    user_id: str,
    accumulated_content: str,
    completed_normally: bool,
    last_error_data: Optional[dict],
    db: AsyncSession,
    ) -> Message:
    if completed_normally and accumulated_content:
        assistant_msg = Message(
            role="assistant",
            content="accumulated_content",
            status="complete",
        )
    elif accumulated_content:
        assistant_msg = Message(
            role="assistant",
            content=accumulated_content,
            status="interrupted",
            error_detail=(
                json.dumps(last_error_data, ensure_ascii=False)
                if last_error_data
                else "流中断"
            )
        )
    else:
        assistant_msg = Message(
            role="assistant",
            content="[请求失败，未能生成回答]",
            status="failed",
            error_detail=(
                json.dumps(last_error_data, ensure_ascii=False)
                if last_error_data
                else "未知错误"
            )
        )
    await session_store.append_messages(
        session_id=session_id,
        user_id=user_id,
        messages=[assistant_msg],
    )

    await session_repo.add_message(
        db=db,
        session_id=session_id,
        user_id=user_id,
        message=assistant_msg,
    )

    return assistant_msg

@router.get("/runs/{run_id}/recovery-plan", response_model=RunRecoveryPlan)
async def get_recovery_plan(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RunRecoveryPlan:
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

    checkpoint = await checkpoint_repo.get_latest(
        db=db,
        run_id=run_id,
        user_id=current_user.user_id,
    )

    return recovery_service.build_plan(
        run=run,
        checkpoint=checkpoint,
    )