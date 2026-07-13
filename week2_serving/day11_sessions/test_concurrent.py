import asyncio
import time

import httpx


API = "http://127.0.0.1:8000"


async def login_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        f"{API}/v1/auth/login",
        json={"username": "alice", "password": "123456"},
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def main():
    async with httpx.AsyncClient() as client:
        headers = await login_headers(client)
        response = await client.post(
            f"{API}/v1/sessions",
            json={"title": "Concurrent test"},
            headers=headers,
        )
        response.raise_for_status()
        session_id = response.json()["id"]
        print(f"Session: {session_id}")

    async def request_one(idx: int):
        async with httpx.AsyncClient(timeout=60) as client:
            headers = await login_headers(client)
            start = time.time()
            try:
                response = await client.post(
                    f"{API}/v1/sessions/{session_id}/chat/stream",
                    json={"question": f"Question {idx}: What is Python?"},
                    headers=headers,
                )
                elapsed = time.time() - start
                print(f"[Request {idx}] Status: {response.status_code}, elapsed: {elapsed:.1f}s")
            except Exception as exc:
                print(f"[Request {idx}] Error: {exc}")

    print("\n=== Sending 2 concurrent requests ===")
    await asyncio.gather(
        request_one(1),
        request_one(2),
    )


if __name__ == "__main__":
    asyncio.run(main())
