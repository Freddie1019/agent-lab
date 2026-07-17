import asyncio
from typing import Optional
from deep_research_agent.core.run_trace import (
    RunStep,
    RunStepType,
    RunStepStatus,
    ToolCallRecord,
)
from pydantic import BaseModel

class TraceRecordResult(BaseModel):
    step: Optional[RunStep] = None
    tool_call_created: Optional[ToolCallRecord] = None
    tool_call_updated: Optional[ToolCallRecord] = None

class RunTraceStore:
    """
    内存版 RunTrace 存储。

    存储：
    - RunStep
    - ToolCallRecord

    """
    def __init__(self) -> None:
        self._steps: dict[str, RunStep] = {}
        self._tool_calls: dict[str, ToolCallRecord] ={}
        self._lock = asyncio.Lock()
    
    async def add_step(self, step: RunStep) -> RunStep:
        async with self._lock:
            self._steps[step.id] = step
            return step
    
    async def list_steps(
        self,
        run_id: str,
        user_id: str,
    ) -> list[RunStep]:
        async with self._lock:
            steps = [
                step
                for step in self._steps.values()
                if step.run_id == run_id and step.user_id == user_id
            ]
            return sorted(steps, key=lambda s: (s.step_index, s.created_at))
    
    async def create_tool_call(
        self,
        record: ToolCallRecord,
    ) -> ToolCallRecord:
        async with self._lock:
            self._tool_calls[record.id] = record
            return record
    
    async def list_tool_calls(
        self,
        run_id: str,
        user_id: str,
    ) -> list[ToolCallRecord]:
        async with self._lock:
            calls = [
                call
                for call in self._tool_calls.values()
                if call.run_id == run_id and call.user_id == user_id
            ]
            return sorted(calls, key=lambda c: (c.step_index, c.created_at))
    
    async def find_latest_running_tool_call(
        self,
        run_id: str,
        user_id: str,
        tool_name: Optional[str] = None,
    ) -> Optional[ToolCallRecord]:
        async with self._lock:
            candidates = [
                call
                for call in self._tool_calls.values()
                if call.run_id == run_id
                and call.user_id == user_id
                and call.status.value == "running"
            ]

            if tool_name:
                candidates = [
                    call for call in candidates if call.tool_name == tool_name
                ]

            if not candidates:
                return None

            return sorted(candidates, key=lambda c: c.created_at)[-1]
    
    async def update_tool_call(self, record: ToolCallRecord) -> ToolCallRecord:
        async with self._lock:
            self._tool_calls[record.id] = record
            return record
    
    async def record_event(
        self,
        *,
        run_id: str,
        session_id: str,
        user_id: str,
        event_type: str,
        step_index: int,
        data: dict,
    ) -> Optional[TraceRecordResult]:
        """
        根据 AgentEvent 记录 RunStep / ToolCallRecord。
        """
        step_type = self._map_event_to_step_type(event_type)
        if step_type is None:
            return None

        step = RunStep(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            step_index=step_index,
            event_type=event_type,
            step_type=step_type,
            status=RunStepStatus.COMPLETED,
            content=self._extract_content(event_type, data),
            summary=self._extract_summary(event_type, data),
            raw_event_data=data,
        )

        result = TraceRecordResult(step=step)

        if event_type == "error":
            step.mark_failed(
                error_type=data.get("type", "unknown_error"),
                error_detail=data.get("detail") or str(data),
            )

        await self.add_step(step)

        # 工具调用记录
        if event_type == "tool_call":
            record = await self._record_tool_call(
                run_id=run_id,
                session_id=session_id,
                user_id=user_id,
                step_index=step_index,
                data=data,
            )
            result.tool_call_created = record

        elif event_type == "tool_result":
            record = await self._complete_tool_call(
                run_id=run_id,
                user_id=user_id,
                data=data,
            )
            result.tool_call_updated = record

        return result

    def _map_event_to_step_type(
        self,
        event_type: str,
    ) -> Optional[RunStepType]:
        mapping = {
            "agent_start": RunStepType.SYSTEM,
            "run_created": RunStepType.SYSTEM,
            "step_start": RunStepType.SYSTEM,
            "thought": RunStepType.THOUGHT,
            "tool_call": RunStepType.TOOL_CALL,
            "tool_result": RunStepType.TOOL_RESULT,
            "answer_complete": RunStepType.ANSWER,
            "agent_complete": RunStepType.SYSTEM,
            "error": RunStepType.ERROR,
        }
        return mapping.get(event_type)

    def _extract_content(
        self,
        event_type: str,
        data: dict,
    ) -> Optional[str]:
        if event_type == "thought":
            return data.get("content")

        if event_type == "answer_complete":
            return data.get("answer")

        if event_type == "error":
            return data.get("user_message") or data.get("detail")

        if event_type == "tool_result":
            return data.get("result_preview")

        return None
    
    def _extract_summary(
        self,
        event_type: str,
        data: dict,
    ) -> Optional[str]:
        if event_type == "tool_call":
            return f"调用工具：{data.get('tool_name')}"

        if event_type == "tool_result":
            success = data.get("success")
            return f"工具结果：success={success}"

        if event_type == "step_start":
            return f"开始步骤：{data.get('step')}"

        return None
    
    async def _record_tool_call(
        self,
        *,
        run_id: str,
        session_id: str,
        user_id: str,
        step_index: int,
        data: dict,
    ) -> ToolCallRecord:
        tool_name = (
            data.get("tool_name")
            or data.get("name")
            or data.get("tool")
            or "unknown_tool"
        )

        tool_args = (
            data.get("tool_args")
            or data.get("args")
            or data.get("arguments")
            or {}
        )

        record = ToolCallRecord(
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            step_index=step_index,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        await self.create_tool_call(record)
        return record

    async def _complete_tool_call(
        self,
        *,
        run_id: str,
        user_id: str,
        data: dict,
    ) -> ToolCallRecord | None:
        tool_name = (
            data.get("tool_name")
            or data.get("name")
            or data.get("tool")
        )

        record = await self.find_latest_running_tool_call(
            run_id=run_id,
            user_id=user_id,
            tool_name=tool_name,
        )

        if record is None:
            return

        success = data.get("success", True)
        result_preview = data.get("result_preview") or data.get("result")

        if success:
            record.mark_completed(result_preview=str(result_preview)[:500])
        else:
            record.mark_failed(
                error_type=data.get("error_type", "tool_error"),
                error_detail=str(result_preview),
            )

        await self.update_tool_call(record)
        return record


run_trace_store = RunTraceStore()
