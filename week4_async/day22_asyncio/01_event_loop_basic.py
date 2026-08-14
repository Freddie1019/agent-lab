import asyncio
import time

def blocking_work() -> str:
    time.sleep(5)
    return "blocking work finished"

async def heartbeat() -> None:
    for index in range(5):
        print(f"heartbeat: {index}")
        await asyncio.sleep(0.2)

async def bad_example() -> None:
    heartbeat_task = asyncio.create_task(heartbeat())
    started_at = time.perf_counter()

    # 错误：同步函数直接占用 Event Loop 线程
    result = blocking_work()

    print(result)
    print(f"elapsed: {time.perf_counter() - started_at:.2f}s")

    await heartbeat_task

async def good_example() -> None:
    heartbeat_task = asyncio.create_task(heartbeat())

    started_at = time.perf_counter()

    # 正确：同步阻塞工作进入线程池
    result = await asyncio.to_thread(blocking_work)

    print(result)
    print(f"elapsed: {time.perf_counter() - started_at:.2f}s")

    await heartbeat_task

async def main() -> None:
    print("=== bad example ===")
    await bad_example()

    print("\n=== good example ===")
    await good_example()

if __name__ == "__main__":
    asyncio.run(main())
