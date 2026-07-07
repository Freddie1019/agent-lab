"""
流式错误处理的故障注入测试

使用方式：
  # 1. 先以故障注入模式启动服务器
  $env:FAULT_INJECTION="1"
  uv run python -m deep_research_agent.api.server

  # 2. 再运行本测试
  uv run python week2_serving/day12_error_handling/test_stream_errors.py
"""
import asyncio
import httpx
import time
import sys, os
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


API = "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_stream_with_failures():
    """流式接口在故障下的行为"""
    async with httpx.AsyncClient(timeout=120) as client:
        # 创建 session
        resp = await client.post(
            f"{API}/v1/sessions",
            json={},
            headers={"X-User-ID": "test_user"},
        )
        assert resp.status_code == 200, resp.text
        session_id = resp.json()["id"]
        print(f"Session: {session_id}\n")
        
        question = "为什么Claude code模型在处理长文本时比GPT-4更稳定？"
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
            assert response.status_code == 200, await response.aread()
            
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

        assert events_received["agent_start"] == 1
        assert events_received["step_start"] > 0
        assert (
            events_received["agent_complete"] > 0
            or events_received["error"] > 0
        ), "流中既没有完成事件，也没有错误事件"
        
        # 检查 session 持久化
        resp = await client.get(
            f"{API}/v1/sessions/{session_id}",
            headers={"X-User-ID": "test_user"},
        )
        assert resp.status_code == 200, resp.text
        session_data = resp.json()
        print(f"\n=== Session 状态 ===")
        print(f"消息数: {len(session_data['messages'])}")
        for m in session_data['messages']:
            status = m.get('status', 'complete')
            print(f"  [{m['role']}] status={status} | {(m.get('content') or '')[:80]}")

        assert len(session_data["messages"]) >= 2
        assistant_message = session_data["messages"][-1]
        assert assistant_message["role"] == "assistant"
        assert assistant_message["status"] in {
            "complete", "interrupted", "failed",
        }
        
        # 故障注入统计（服务端日志中查看）
        print(f"\n=== 故障注入 ===")
        print("  请在服务器终端查看 FaultInjector 统计输出")


if __name__ == "__main__":
    asyncio.run(test_stream_with_failures())
