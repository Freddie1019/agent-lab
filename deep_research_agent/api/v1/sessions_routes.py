"""
会话管理接口
- POST /v1/sessions       创建会话
- GET  /v1/sessions       列出我的会话
- GET  /v1/sessions/{id}  查看某个会话
- DELETE /v1/sessions/{id} 删除会话
"""
from datetime import datetime
from email import message
from turtle import title
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from requests import session

from deep_research_agent.api.v1.routes import router
from deep_research_agent.core.session_store import session_store
from deep_research_agent.core.session import Session, Message

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

# ===== Request/Response Models =====
class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)

class SessionSummary(BaseModel):
    """ 会话列表中的简要信息 （不含完整 messages）"""
    id: str
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime

class SessionDetail(BaseModel):
    """会话详情（含完整 messages）"""
    id: str
    title: Optional[str]
    messages: list[Message]
    created_at: datetime
    updated_at: datetime

# ===== Endpoints =====
@router.post("", response_model=SessionDetail)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """创建新会话"""
    session = await session_store.create(user_id=user_id, title=request.title)
    return SessionDetail(
        id=session.id,
        title=session.title,
        messages=session.messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 50,
):
    """列出当前用户的所有会话"""
    sessions = await session_store.list_by_user(user_id, limit=limit)
    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            message_count=len(s.messages),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]

@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """获取会话详情（含完整对话历史）"""
    session = await session_store.get(session_id, user_id)
    return SessionDetail(
        id=session.id,
        title=session.title,
        messages=session.messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """删除会话"""
    await session_store.delete(session_id, user_id)
    return {"session_id": session_id, "status": "deleted"}
