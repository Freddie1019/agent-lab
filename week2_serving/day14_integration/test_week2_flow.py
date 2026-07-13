import json
import time
import httpx
import asyncio
from typing import Any, Optional
from dataclasses import dataclass

BASE_URL = "http://127.0.0.1:8000/v1"

@dataclass
class TestUser:
    username: str
    password: str
    token: Optional[str] = None

alice = TestUser(username="alice", password="123456")
admin = TestUser(username="admin", password="admin123")

def pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)

async def login(client: httpx.AsyncClient, user: TestUser) -> str:
    resp = await client.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": user.username,
            "password": user.password,
        },
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"登陆失败：{user.username},"
            f"status={resp.status_code}, body={resp.text}"
        )
    
    data = resp.json()
    token = data["access_token"]
    user.token = token
    return token

def auth_headers(user: TestUser) -> dict[str, str]:
    if not user.token:
        raise RuntimeError(f"用户 {user.username} 未登录")
    
    return {
        "Authorization": f"Bearer {user.token}"
    }

async def create_session(
    client: httpx.AsyncClient,
    user: TestUser,
    title: str,
) -> str:
    resp = await client.post(
        f"{BASE_URL}/sessions",
        headers=auth_headers(user),
        json={
            "title": title,
        }
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"创建 session 失败：status={resp.status_code}, body={resp.text}"
        )

    data = resp.json()

    # 兼容不同返回字段
    session_id = data.get("session_id") or data.get("id")
    if not session_id:
        raise RuntimeError(
            f"无法从响应中获取 session_id: {pretty(data)}"
        )
    return session_id

async def get_session(
    client: httpx.AsyncClient,
    user: TestUser,
    session_id: str,
    ) -> httpx.Response:
    return await client.get(
        f"{BASE_URL}/sessions/{session_id}",
        headers=auth_headers(user)
    )

async def test_auth_and_session_isolation(client: httpx.AsyncClient) -> str:
    print("\n=== 测试1: 认证与 session 隔离 ===")

    await login(client, alice)
    await login(client, admin)

    alice_session_id = await create_session(
        client, 
        alice,
        title="Day14 Alice Integration Session"
    )

    print(f"alice_session_id={alice_session_id}")

    # alice 能访问自己的 session
    resp = await get_session(client, alice, alice_session_id)
    assert resp.status_code == 200, resp.text
    print(f"alice 可以访问自己的 session")

    # admin 不能访问 alice 的 session
    resp = await get_session(client, admin, alice_session_id)
    assert resp.status_code in (403, 404), resp.text
    print("admin 不能访问 alice 的 session")

    # 不带 token， 试图只传 X-User-Id
    resp = await client.get(
        f"{BASE_URL}/sessions/{alice_session_id}",
        headers={
            "X-User-Id": "user_alice"
        },
    )
    assert resp.status_code == 401, resp.text
    print("只传 X-User-Id 不能访问受保护接口")

    return alice_session_id

async def test_pre_stream_errors(
        client: httpx.AsyncClient,
        session_id: str,
    ):
    print("\n=== 测试2: 流前错误 ===")

    # 1. 无 token
    resp = await client.post(
        f"{BASE_URL}/sessions/{session_id}/chat/stream",
        json={
            "question": " 无 token 测试",
        },
    )
    assert resp.status_code == 401, resp.text
    assert "event:" not in resp.text
    print(" 无 token -> HTTP 401, 不进入 SSE")

    # 2. 假 token
    resp = await client.post(
        f"{BASE_URL}/sessions/{session_id}/chat/stream",
        headers={
            "Authorization": "Bearer fake_token",
        },
        json={
            "question": " 假 token 测试",
        },
    )
    assert resp.status_code == 401, resp.text
    assert "event:" not in resp.text
    print(" 假 token -> HTTP 401, 不进入 SSE")

    # 3. session 不存在
    resp = await client.post(
        f"{BASE_URL}/sessions/fake_session_id/chat/stream",
        headers=auth_headers(alice),
        json={
            "question": " session 不存在测试",
        },
    )
    assert resp.status_code in (403, 404), resp.text
    assert "event:" not in resp.text
    print(" session 不存在 -> HTTP 403/404, 不进入 SSE")

async def collect_sse_events(
    client: httpx.AsyncClient,
    user: TestUser,
    session_id: str,
    question: str,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    """
    收集 SSE 事件

    返回格式：
    [
        {"event": "agent_start", "data": {...}},
        {"event": "thought", "data": {...}},
        ...
    ]
    """
    events: list[dict[str, Any]]  = []

    async with client.stream(
        "POST",
        f"{BASE_URL}/sessions/{session_id}/chat/stream",
        headers=auth_headers(user),
        json={
            "question": question,
        },
        timeout=timeout,
    ) as resp:
        assert resp.status_code == 200, await resp.aread()

        current_event: Optional[str] = None
        current_data_lines: list[str] = []

        async for line in resp.aiter_lines():
            if not line:
                if current_event:
                    raw_data = "\n".join(current_data_lines)

                    if raw_data == "[DONE]":
                        events.append({"event": current_event, "data": "[DONE]"})
                    else:
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            data = raw_data

                        events.append({"event": current_event, "data": data})

                    current_event = None
                    current_data_lines = []
                
                continue
            
            if line.startswith("event:"):
                current_event = line.replace("event:", "", 1).strip()
            elif line.startswith("data:"):
                current_data_lines.append(line.replace("data:", "", 1).strip())
    
    return events

async def test_normal_stream(client: httpx.AsyncClient, session_id: str):
    print("\n=== 测试3: 正常 SSE 流式请求 ===")

    events = await collect_sse_events(
        client=client,
        user=alice,
        session_id=session_id,
        question="请用三句话解释下为什么 Agent 服务需要 session",
    )

    event_names = [e["event"] for e in events]
    print("event:", event_names)

    assert "agent_start" in event_names, event_names
    assert "done" in event_names, event_names

    assert  "agent_complete" in event_names, event_names

    print("SSE 正常流式请求测试通过")

# async def test_stream_with_fault_injection(
#     client: httpx.AsyncClient,
#     session_id: str,
# ):
#     print("\n=== 测试 4: 故障注入与流中错误")

#     events = await collect_sse_events(
#         client=client,
#         user=alice,
#         session_id=session_id,
#         question=(
#             "请搜索并总结一个需要调用外部工具的问题。"
#             "如果工具失败，请说明失败原因。"
#         ),
#         timeout=90.0
#     )

#     event_names = [e["event"] for e in events]
#     print("events:", event_names)

#     if "error" in event_names:
#         print("✅ 捕获到 SSE event:error，流中错误处理生效")

#         error_events = [e for e in events if e["event"] == "error"]
#         print("error event:")
#         print(pretty(error_events[0]["data"]))

#         # error 事件里最好包含这些字段
#         data = error_events[0]["data"]
#         assert "type" in data
#         assert "user_message" in data or "message" in data
#         assert "recoverable" in data

#     else:
#         print("⚠️ 本次没有触发 error，可能是故障注入未开启或随机未命中")
#         print("这不一定是失败，但建议提高 FAULT_RATE 后重试")

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. 认证与 session 隔离
        session_id = await test_auth_and_session_isolation(client)

        # 2. 流前错误
        await test_pre_stream_errors(client, session_id)

        # 3. 正常 SSE 流
        await test_normal_stream(client, session_id)

        # # 4. 故障注入与流中错误
        # await test_stream_with_fault_injection(client, session_id)

    print("\n🎉 Day14 Week2 集成测试完成")


if __name__ == "__main__":
    asyncio.run(main())