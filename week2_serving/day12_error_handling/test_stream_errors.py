"""
流式错误处理的故障注入测试
"""
import asyncio
import httpx
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.fault_injector import FaultInjector
from shared import real_tools


# 注入故障
injector = FaultInjector(
    timeout_rate=0.30,
    rate_limit_rate=0.20,
    unavailable_rate=0.00,
    garbage_rate=0.00,
)

# Monkey-patch
original_search = real_tools.web_search
real_tools.web_search = injector.wrap(original_search)


API = "http://127.0.0.1:8000"


async def test_stream_with_failures():
    """流式接口在故障下的行为"""
    async with httpx.AsyncClient(timeout=120) as client:
        # 创建 session
        resp = await client.post(
            f"{API}/v1/sessions",
            json={},
            headers={"X-User-ID": "test_user"},
        )
        session_id = resp.json()["id"]
        print(f"Session: {session_id}\n")
        
        question = "对比 LangGraph、CrewAI、AutoGen 三个框架"
        print(f"问题: {question}\n")
        
        events_received = {
            "agent_start": 0, "step_start": 0,
            "thought": 0, "tool_call": 0,
            "tool_result": 0, "error": 0,
            "answer_complete": 0, "agent_complete": 0,
        }
        
        async with client.stream(
            "POST",
            f"{API}/v1/sessions/{session_id}/chat/stream",
            json={"question": question, "max_steps": 8},
            headers={"X-User-ID": "test_user"},
        ) as response:
            print(f"HTTP Status: {response.status_code}")
            
            current_event = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    if current_event in events_received:
                        events_received[current_event] += 1
                    print(f"📡 {current_event}")
                elif line.startswith("data:"):
                    data = line.split(":", 1)[1].strip()
                    if current_event == "error":
                        print(f"   ⛔ Error: {data[:200]}")
        
        # 统计
        print("\n=== 事件统计 ===")
        for k, v in events_received.items():
            print(f"  {k}: {v}")
        
        # 检查 session 持久化
        resp = await client.get(
            f"{API}/v1/sessions/{session_id}",
            headers={"X-User-ID": "test_user"},
        )
        session_data = resp.json()
        print(f"\n=== Session 状态 ===")
        print(f"消息数: {len(session_data['messages'])}")
        for m in session_data['messages']:
            status = m.get('status', 'complete')
            print(f"  [{m['role']}] status={status} | {(m.get('content') or '')[:80]}")
        
        # 故障注入统计
        print(f"\n=== 故障注入统计 ===")
        injector.report()


if __name__ == "__main__":
    asyncio.run(test_stream_with_failures())