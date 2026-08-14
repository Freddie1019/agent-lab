""" 不可避免的同步调用与 AsyncIO 之间的适配边界。 """
import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

class BlockingCallTimeout(TimeoutError):
    """同步调用超过异步等待预算"""

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
    ) -> None:
        self.operation = operation
        self.timeout_seconds = timeout_seconds

        super().__init__(
            f"Blocking operation '{operation}' exceeded"
            f"{timeout_seconds:.3f} seconds"
        )

async def run_blocking(
    func: Callable[..., T],
    /,
    *args: Any,
    operation: str,
    timeout_seconds: float,
    **kwargs: Any,
) -> T:
    """在线程池执行同步调用，同时限制等待时间"""

    try:
        async with asyncio.timeout(timeout_seconds):
            return await asyncio.to_thread(
                func,
                *args,
                **kwargs,
            )
    except TimeoutError as exc:
        raise BlockingCallTimeout(
            operation=operation,
            timeout_seconds=timeout_seconds,
        ) from exc

    