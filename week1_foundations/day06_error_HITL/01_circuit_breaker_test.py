"""
验证熔断器的三状态切换是否正确
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.circuit_breaker import CircuitBreaker
from shared.agent_errors import ToolUnavailable

# 故意构造一个会失败的函数
call_count = 0

def flaky_service():
    global call_count
    call_count =+ 1
    if call_count <=7:
        raise ConnectionError(f"假装挂了 (call #{call_count})")
    return f"成功！(call #{call_count})"

breaker = CircuitBreaker(name="test", failure_threshold=5, recovery_timeout=3.0)

# 阶段 1: 连续失败触发熔断
print("=== 阶段 1: 触发熔断 ===")
for i in range(7):
    try:
        breaker.call(flaky_service)
    except ConnectionError as e:
        print(f"  Call {i+1}: ConnectionError")
    except ToolUnavailable as e:
        print(f"  Call {i+1}: 被熔断器拒绝 - {e.detail[:60]}")
    
# 阶段 2: 等冷却
print(f"\n=== 阶段 2: 等待冷却 (3s) ===")
time.sleep(3.1)

# 阶段 3: 试探恢复
print("=== 阶段 3: 试探恢复 ===")
try:
    result = breaker.call(flaky_service)
    print(f"  恢复成功: {result}")
except Exception as e:
    print(f"  仍然失败: {e}")

# 阶段 4: 验证恢复后正常
print("\n=== 阶段 4: 验证恢复后 ===")
for i in range(2):
    try:
        result = breaker.call(flaky_service)
        print(f"  Call: {result}")
    except Exception as e:
        print(f"  Failed: {e}")