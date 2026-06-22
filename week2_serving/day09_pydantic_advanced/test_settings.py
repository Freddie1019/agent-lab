"""
看看 settings 怎么工作
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deep_research_agent.core.settings import Settings, get_settings

# === 实验 1：直接调用 ===
settings = get_settings()
print(f"API Key 前 10 位: {settings.openai_api_key[:10]}...")
print(f"默认模型: {settings.default_model}")
print(f"Token 预算: {settings.default_token_budget}")

# === 实验 2：缺少必需字段时的报错 ===
import os
old_key = os.environ.pop("OPENAI_API_KEY", None)
try:
    s = Settings(_env_file=".does-not-exist")
except Exception as e:
    print(f"\n[预期错误] 缺少必填字段: {e}")
finally:
    if old_key:
        os.environ["OPENAI_API_KEY"] = old_key


# === 实验 3：测试时直接传参，不依赖 .env ===
test_settings = Settings(
    openai_api_key="fake-key-for-test",
    tavily_api_key="fake-tavily",
)
print(f"\n[测试模式] {test_settings.openai_api_key}")