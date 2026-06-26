"""
并发测试：同一 session 被两个请求同时调用，验证锁机制
"""
import asyncio
import httpx
import time

API = "http://127.0.0.1:8000"

async def main():
    # 1. 创建 session
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/v1/sessions",
            json={"title": "并发测试"},
            headers={"X-User-ID": "alice"},
        )
        # 临时修改第 18 行前后的代码进行排查
        # print(f"Status Code: {resp.status_code}")
        # print(f"Response Text: {resp.text}")  # 看看服务器到底吐了什么

        session_id = resp.json()["id"]
        print(f"Session: {session_id}")
    
    # 2. 同时发两个请求
    async def request_one(idx: int):
        async with httpx.AsyncClient(timeout=60) as client:
            start = time.time()
            try:
                resp = await client.post(
                    f"{API}/v1/sessions/{session_id}/chat/stream",
                    json={"question": f"问题 {idx}：什么是 Python？"},
                    headers={"X-User-ID": "alice"},
                )
                elapsed = time.time() - start
                print(f"[Request {idx}] Status: {resp.status_code}, 耗时: {elapsed:.1f}s")
            except Exception as e:
                print(f"[Request {idx}] Error: {e}")
    
    print("\n=== 同时发起 2 个请求 ===")
    await asyncio.gather(
        request_one(1),
        request_one(2),
    )


if __name__ == "__main__":
    asyncio.run(main())