import asyncio
from typing import Optional

from deep_research_agent.core.run import AgentRun, AgentRunStatus

class AgentRunStore:
    """
    内存版 AgentRun 存储。

    
    后续会迁移到数据库。
    """
    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._lock = asyncio.Lock()
    
    async def create(
        self,
        session_id: str,
        user_id: str,
        user_message_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> AgentRun:
        async with self._lock:
            run = AgentRun(
                session_id=session_id,
                user_id=user_id,
                user_message_id=user_message_id,
                metadata=metadata or {}
            )
            self._runs[run.id] = run
            return run

    async def get(
        self,
        run_id: str,
        user_id: str,
    ) -> AgentRun:
        async with self._lock:
            run = self._runs.get(run_id)

            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            
            if run.user_id != user_id:
                raise KeyError(f"Run not found: {run_id}")
            
            return run

    async def list_by_session(
        self,
        session_id: str,
        user_id: str
    ) -> list[AgentRun]:
        async with self._lock:
            return [
                run
                for run in self._runs.values()
                if run.session_id == session_id and run.user_id == user_id
            ]
    
    async def update(self, run: AgentRun) -> AgentRun:
        async with self._lock:
            self._run[run.id] = run
            return run
    
    async def mark_started(self, run_id: str) -> AgentRun:
        async with self._lock:
            run = self._runs[run_id]
            run.mark_started()
            return run
    
    async def mark_completed(self, run_id: str) -> AgentRun:
        async with self._lock:
            run = self._runs[run_id]
            run.mark_completed()
            return run
    
    async def mark_failed(
        self,
        run_id: str,
        error_type: str,
        error_detail: str,
        error_user_message: Optional[str] = None,
    ) -> AgentRun:
        async with self._lock:
            run = self._runs[run_id]
            run.mark_failed(
                error_type=error_type,
                error_detail=error_detail,
                error_user_message=error_user_message
            )
            return run
    
    async def mark_interrupted(
        self,
        run_id: str,
        reason: str = "client_disconnected",
    ) -> AgentRun:
        async with self._lock:
            run = self._runs[run_id]
            run.mark_interrupted(reason=reason)
            return run
    
    async def update_from_event(
        self,
        run_id: str,
        event_type: str,
        step: int = 0,
        data: Optional[dict] = None
    ) -> AgentRun:
        """
        根据 AgentEvent 更新 AgentRun 状态 
        """
        data = data or {}

        async with self._lock:
            run = self._runs[run_id]
            run.update_event(event_type)

            if step:
                run.update_step(step)
            
            if event_type == "agent_start":
                run.mark_started()

            elif event_type == "step_start":
                run.mark_running()

            elif event_type == "tool_call":
                tool_name = data.get("tool_name")
                run.mark_waiting_tool(tool_name=tool_name)

            elif event_type == "tool_result":
                run.mark_running()

            elif event_type == "answer_complete":
                # 这里不立即 completed，等 agent_complete 更准确
                run.mark_running()

            elif event_type == "agent_complete":
                run.mark_completed()

            elif event_type == "error":
                error_type = data.get("type", "unknown_error")
                detail = data.get("detail") or data.get("message") or str(data)
                user_message = data.get("user_message")

                run.mark_failed(
                    error_type=error_type,
                    error_detail=detail,
                    error_user_message=user_message,
                )

            return run
    
run_store = AgentRunStore()