"""
最小可用的电路熔断器实现
三状态：CLOSED / OPEN / HALF_OPEN
"""
from ast import Call
import time
from enum import Enum
from typing import Callable, Any
from shared.agent_errors import ToolUnavailable

class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = BreakerState.CLOSED
        self.failure_count  = 0
        self.last_failure_time: float = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """包装一个函数调用，自动管理状态机"""
        # 状态 1： OPEN
        if self.state == BreakerState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                # 进入 HALF_OPEN 试探
                self.state = BreakerState.HALF_OPEN
                print(f"  [熔断器 {self.name}] OPEN → HALF_OPEN（试探）")
            else:
                # 还在冷却，直接拒绝
                raise ToolUnavailable(
                    f"熔断器 {self.name} 处于 OPEN 状态，"
                    f"还需 {self.recovery_timeout - elapsed:.0f}s 才能重试"
                )
        
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result
    
    def _on_success(self):
        if self.state == BreakerState.HALF_OPEN:
            print(f"  [熔断器 {self.name}] HALF_OPEN → CLOSED（恢复）")
        self.state = BreakerState.CLOSED
        self.failure_count = 0
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == BreakerState.HALF_OPEN:
            # 试探失败，回到 OPEN
            self.state = BreakerState.OPEN
            print(f"  [熔断器 {self.name}] HALF_OPEN → OPEN（试探失败）")
        elif self.failure_count >= self.failure_threshold:
            self.state = BreakerState.OPEN
            print(f"  [熔断器 {self.name}] CLOSED → OPEN（连续失败 {self.failure_count} 次）")


# 全局熔断器注册表（每个工具一个独立熔断器）
_breakers: dict[str, CircuitBreaker] = {}

def get_breaker(tool_name: str) -> CircuitBreaker:
    if tool_name not in _breakers:
        _breakers[tool_name] = CircuitBreaker(name=tool_name)
    return _breakers[tool_name]
