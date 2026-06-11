"""
简单的全局调用计数器 + 阈值熔断
真实生产环境会用 Redis + token bucket，今天先用内存版
"""
import time
from collections import defaultdict

class CallTracker:
    def __init__(self):
        self.counts = defaultdict(int)
        self.start_time = time.time()
        self.limits = {}

    def set_limit(self, tool_name: str, max_calls: int):
        self.limits[tool_name] = max_calls
    
    def record(self, tool_name: str) -> bool:
        """记录一次调用，返回是否允许（False 表示已超限）"""
        self.counts[tool_name] += 1
        if tool_name in self.limits:
            if self.counts[tool_name] > self.limits[tool_name]:
                return False
        return True
    
    def report(self):
        elapsed = time.time() - self.start_time
        print(f"\n=== 调用统计（运行 {elapsed:.1f}s）===")
        for name, count in self.counts.items():
            limit = self.limits.get(name, "∞")
            print(f"  {name}: {count} 次（上限 {limit}）")

# 全局单例
tracker = CallTracker()

        