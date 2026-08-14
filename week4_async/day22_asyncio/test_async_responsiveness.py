import asyncio 
import threading
import time
import os,sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import httpx
import pytest

import deep_research_agent.core.agent as agent_module
from deep_research_agent.api.server import app
from deep_research_agent.core.agent import ResearchAgent
from shared.safety import DangerLevel, ToolMetadata
from deep_research_agent.core.async_runtime import BlockingCallTimeout, run_blocking

@pytest.mark.asyncio
async def test_health_stays_responsive_during_slow_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool_started = threading.Event()

    def slow_safe_execute(**kwargs) -> str:
        tool_started.set()
        time.sleep(0.25)
        return "slow result"

    metadata = ToolMetadata(
        name="slow_tool",
        func=lambda: "unused",
        danger_level=DangerLevel.GREEN,
    )

    monkeypatch.setattr(
        agent_module,
        "safe_execute",
        slow_safe_execute,
    )

    agent = ResearchAgent(verbose=False)

    tool_task = asyncio.create_task(
        agent._execute_tool(
            metadata=metadata,
            tool_args={},
        )
    )

    async with asyncio.timeout(1):
        while not tool_started.is_set():
            await asyncio.sleep(0.005)

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        started_at = time.perf_counter()
        response = await client.get("/health")
        elapsed = time.perf_counter() - started_at

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert elapsed < 0.15
        assert not tool_task.done()

        assert await tool_task == "slow result"

@pytest.mark.asyncio
async def test_block_call_has_timeout() -> None:
    started_at = time.perf_counter()

    with pytest.raises(BlockingCallTimeout):
        await run_blocking(
            time.sleep,
            0.20,
            operation="test:slow-call",
            timeout_seconds=0.02,
        )
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.15