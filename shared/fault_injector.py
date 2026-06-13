"""
故障注入器：对工具调用以概率注入故障
用来验证 Agent 的健壮性
"""
import random
import time
from typing import Callable
from shared.agent_errors import (
    ToolTimeout, ToolRateLimit, ToolUnavailable, AgentError
)

class FaultInjector:
    def __init__(
        self,
        timeout_rate: float = 0.15,
        rate_limit_rate: float = 0.10,
        garbage_rate: float = 0.05,
        unavailable_rate: float = 0.10,
        enabled: bool = True,
    ):
        self.timeout_rate = timeout_rate
        self.rate_limit_rate = rate_limit_rate
        self.garbage_rate = garbage_rate
        self.unavailable_rate = unavailable_rate
        self.enabled = enabled

        self.stats = {
            "total": 0, "timeout": 0, "rate_limit": 0,
            "garbage": 0, "unavailable": 0, "passed": 0,
        }
    
    def wrap(self, func: Callable) -> Callable:
        """包装一个函数，使其有概率失败"""
        def wrapper(*args, **kwargs):
            if not self.enabled:
                return func(*args, **kwargs)
            
            self.stats["total"] += 1
            r = random.random()

            if r < self.timeout_rate:
                self.stats["timeout"] += 1
                raise ToolTimeout("[注入] 模拟超时")
            
            if r < self.timeout_rate + self.rate_limit_rate:
                self.stats["rate_limit"] += 1
                raise ToolRateLimit("[注入] 模拟限流")

            if r < self.timeout_rate + self.rate_limit_rate + self.unavailable_rate:
                self.stats["unavailable"] += 1
                raise ToolUnavailable("[注入] 模拟服务不可用")
            
            if r < (self.timeout_rate + self.rate_limit_rate + 
                    self.unavailable_rate + self.garbage_rate):
                self.stats["garbage"] += 1
                return "x" * 100 + "���乱码���" + "y" * 100  # 返回乱码
            
            self.stats["passed"] += 1
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    
    def report(self):
        print(f"\n=== 故障注入统计 ===")
        for k, v in self.stats.items():
            print(f"  {k}: {v}")
        if self.stats["total"] > 0:
            failure_rate = (self.stats["total"] - self.stats["passed"]) / self.stats["total"]
            print(f"  实际故障率: {failure_rate*100:.1f}%")