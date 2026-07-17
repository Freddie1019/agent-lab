"""
会话管理接口
- POST /v1/sessions       创建会话
- GET  /v1/sessions       列出我的会话
- GET  /v1/sessions/{id}  查看某个会话
- DELETE /v1/sessions/{id} 删除会话
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException,status
from pydantic import BaseModel, Field

from deep_research_agent.core.session_store import session_store
from deep_research_agent.core.session import Message
from deep_research_agent.api.auth import CurrentUser, get_current_user

# 添加至 DB
from sqlalchemy.ext.asyncio import AsyncSession
from deep_research_agent.core.db.session import get_db_session
from deep_research_agent.core.db.repositories import session_repo

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
    current_user: CurrentUser = Depends(get_current_user)
):
    """创建新会话"""
    session = await session_store.create(user_id=current_user.user_id, title=request.title)
    return SessionDetail(
        id=session.id,
        title=session.title,
        messages=session.messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

@router.get("")
async def list_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """列出当前用户的所有会话"""
    return await session_repo.list_sessions(
        db=db,
        user_id=current_user.user_id
    )

@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """获取会话详情（含完整对话历史）"""
    session = await session_repo.get_session(
        db=db,
        session_id=session_id, 
        user_id=current_user.user_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    return session

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """删除会话"""
    await session_store.delete(session_id, current_user.user_id)
    return {"session_id": session_id, "status": "deleted"}

@router.get("/{session_id}/messages")
async def list_session_messages(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    session = await session_repo.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.user_id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Session not found"
        )

    return session.messages
