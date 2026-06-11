"""验证 token 计数与 OpenAI usage 字段的差异"""
from email import message
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.token_counter import count_messages_tokens

messages = [
    {"role": "system", "content": "你是一个友好的助手"},
    {"role": "user", "content": "用 100 字介绍 Transformer 架构"},
]

# 估算
estimated = count_messages_tokens(messages, DEFAULT_MODEL)

# 真实调用对比
response = client.chat.completions.create(
    model=DEFAULT_MODEL,
    messages=messages,
)
actual = response.usage.prompt_tokens

print(f"自己估算的 input tokens: {estimated}")
print(f"OpenAI usage 返回的: {actual}")
print(f"误差: {abs(estimated - actual)} tokens ({abs(estimated - actual) / actual * 100:.1f}%)")