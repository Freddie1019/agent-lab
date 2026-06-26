"""
会话仓库（Repository 模式）
今天用内存字典，下周升级为 PostgreSQL，接口保持不变
"""
import asyncio
from typing import Optional
from fastapi import HTTPException

from deep_research_agent.core.session import Session, Message

class InMemorySessionStore:
    """
    内存版会话仓库
    
    ⚠️ 已知局限：
    1. 服务重启数据全丢
    2. 多 worker 进程不共享
    3. 无自动清理（内存会持续增长）
    
    Week 3 用 PostgreSQL 替换。接口保持不变。
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        # 会话级互斥锁（任务 4 用）
        self._locks: dict[str, asyncio.Lock] = {}

    # ===== 基础 CRUD =====    
    async def create(self, user_id: str, title: Optional[str]=None) -> Session:
        session = Session(user_id=user_id, title=title)
        self._sessions[session.id] = session
        return session
    
    async def get(self, session_id: str, user_id: str) -> Session:
        """
        ★ 关键：每次获取都做所有权校验
        防止 IDOR 漏洞
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(404, f"Session {session_id} not found")
        if session.user_id != user_id:
            # 注意：报 404 而不是 403，防止枚举攻击
            raise HTTPException(404, f"Session {session_id} not found")
        return session
    
    async def list_by_user(self, user_id: str, limit: int = 50) -> list[Session]:
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]
    
    async def delete(self, session_id: str, user_id: str) -> bool:
        session = await self.get(session_id, user_id)
        del self._sessions[session.id]
        if session.id in self._locks:
            del self._locks[session.id]
        return True
    
    async def append_messages(
        self,
        session_id: str,
        user_id: str,
        messages: list[Message]
    ) -> Session:
        session = await self.get(session_id, user_id)
        for msg in messages:
            session.add_message(msg)
        return session

    # ===== 并发控制 =====
    def get_lock(self, session_id: str) -> asyncio.Lock:
        """获取会话级锁（任务 4 使用）"""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]
# 全局单例
session_store = InMemorySessionStore()

