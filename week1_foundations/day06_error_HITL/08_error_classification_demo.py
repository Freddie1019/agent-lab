import httpx
import sys
from pathlib import Path

# 将项目根目录（agent-lab）加入路径
project_root = Path(__file__).parent.parent.parent  # 上两级：week1_foundations -> agent-lab
sys.path.insert(0, str(project_root))

from shared.agent_errors import classify_exception, ErrorCategory

# 测试用例
test_cases = [
    httpx.TimeoutException("timeout"),
    httpx.HTTPStatusError("429", request=None, response=type("R", (), {"status_code": 429})()),
    ValueError("bad arg"),
    ConnectionError("dns fail"),
    Exception("???"),
]

for e in test_cases:
    err = classify_exception(e)
    print(f"原始: {type(e).__name__}: {e}")
    print(f"  → 分类: {err.category.value}, 可重试: {err.retryable}")
    print(f"  → LLM 看到: {err.to_llm_message()}\n")

