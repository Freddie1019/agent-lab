"""
API v1 路由
"""
import json
import asyncio
from itertools import accumulate
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from fastapi import Request
from shared.rate_limiter import tracker
from fastapi.responses import StreamingResponse
from deep_research_agent.core.events import AgentEvent
from deep_research_agent.core.agent import ResearchAgent
from deep_research_agent.core.domain import ResearchTask
from deep_research_agent.api.schemas.v1 import ResearchRequest, ResearchResponse

from deep_research_agent.core.session_store import session_store
from deep_research_agent.core.session import Message
from deep_research_agent.core.events import AgentEvent, make_error_event

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
    user_id: str = Header(..., alias="X-User-ID"),
):
    """在指定会话中流式提问"""
    # 1. 校验所有权
    session = await session_store.get(session_id, user_id)

    # 2. 检查会话锁（防并发）
    lock = session_store.get_lock(session_id)
    if lock.locked():
        raise HTTPException(409, "Session is currently processing another request")
    
    # 3. 拼装历史 + 新问题
    history = session.to_llm_messages()
    history.append({"role": "user", "content": request.question})

    # 4. 创建 Agent
    agent = ResearchAgent(
        max_steps=request.max_steps,
        verbose=False,
    )

    async def event_generator():
        async with lock:
            session.is_processing = True
            
            # 新增状态变量 Day12
            collected_assistant_msg = ""
            last_error_data: Optional[dict] = None
            completed_normally = False

            try:
                # ★ 调用 Agent 时把历史传进去
                async for event in agent.stream_with_history(
                    messages=history,
                ):

                    if await raw_request.is_disconnected():
                        print(f"Client disconnected, cancelling session {session_id}")
                        break
                    
                    # Day12 新增 累计内容 （不论是 thought 还是 answer）
                    if event.type == "thought":
                        accumulated_content = event.data.get("content", "")
                    elif event.type == "answer_complete":
                        accumulated_content = event.data.get("answer", "")
                    
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
                await _persist_session_messages(
                    session_id=session_id,
                    user_id=user_id,
                    user_question=request.question,
                    accumulated_content=accumulated_content,
                    completed_normally=completed_normally,
                    last_error_data=last_error_data,
                )
                session.is_processing = False
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

async def _persist_session_messages(
    session_id: str,
    user_id: str,
    user_question: str,
    accumulated_content: str,
    completed_normally: bool,
    last_error_data: Optional[dict],
):
    """智能持久化：根据流式结果决定怎么存"""
    user_msg = Message(
        role="user",
        content=user_question,
        status="complete",
    )
    if completed_normally and accumulated_content:
        # 完整成功
        assistant_msg = Message(
            role="assistant",
            content=accumulated_content,
            status="complete",
        )
    elif accumulated_content:
        # 部分成功（流中断或错误，但有内容）
        assistant_msg = Message(
            role="assistant",
            content=accumulated_content,
            status="interrupted",
            error_detail=json.dumps(last_error_data) if last_error_data else "流中断",
        )
    else:
        # 完全失败，没有任何 assistant 内容
        assistant_msg = Message(
            role="assistant",
            content="[请求失败，未能生成回答]",
            status="failed",
            error_detail=json.dumps(last_error_data) if last_error_data else "未知错误",
        )
    await session_store.append_messages(
        session_id=session_id,
        user_id=user_id,
        messages=[user_msg, assistant_msg],
    )