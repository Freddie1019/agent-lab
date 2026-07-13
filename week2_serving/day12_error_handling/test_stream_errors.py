import asyncio
import os
import sys

import httpx
import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API = "http://127.0.0.1:8000"


async def login_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        f"{API}/v1/auth/login",
        json={"username": "alice", "password": "123456"},
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_stream_with_failures():
    async with httpx.AsyncClient(timeout=120) as client:
        headers = await login_headers(client)

        response = await client.post(
            f"{API}/v1/sessions",
            json={},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        session_id = response.json()["id"]
        print(f"Session: {session_id}\n")

        question = "Why are long-context models more stable on long documents?"
        print(f"Question: {question}\n")

        events_received = {
            "agent_start": 0,
            "step_start": 0,
            "thought": 0,
            "tool_call": 0,
            "tool_result": 0,
            "error": 0,
            "answer_complete": 0,
            "agent_complete": 0,
        }

        async with client.stream(
            "POST",
            f"{API}/v1/sessions/{session_id}/chat/stream",
            json={"question": question, "max_steps": 8},
            headers=headers,
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
                    print(f"Event: {current_event}")
                elif line.startswith("data:"):
                    data = line.split(":", 1)[1].strip()
                    if current_event == "error":
                        print(f"Error: {data[:200]}")

        print("\n=== Event stats ===")
        for key, value in events_received.items():
            print(f"  {key}: {value}")

        assert events_received["agent_start"] == 1
        assert events_received["step_start"] > 0
        assert (
            events_received["agent_complete"] > 0
            or events_received["error"] > 0
        ), "Stream produced neither a completion event nor an error event"

        response = await client.get(
            f"{API}/v1/sessions/{session_id}",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        session_data = response.json()
        print("\n=== Session state ===")
        print(f"Message count: {len(session_data['messages'])}")
        for message in session_data["messages"]:
            status = message.get("status", "complete")
            content = message.get("content") or ""
            print(f"  [{message['role']}] status={status} | {content[:80]}")

        assert len(session_data["messages"]) >= 2
        assistant_message = session_data["messages"][-1]
        assert assistant_message["role"] == "assistant"
        assert assistant_message["status"] in {
            "complete",
            "interrupted",
            "failed",
        }


if __name__ == "__main__":
    asyncio.run(test_stream_with_failures())
