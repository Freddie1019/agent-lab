"""
对比两种压缩策略的行为
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.context_manager import ContextManager
from shared.token_counter import count_messages_tokens

# 构造一段长对话
messages = [{"role": "system", "content": "你是一个友好的助手"}]
for i in range(1, 21):
    messages.append({"role": "user", "content": f"这是用户第{i}轮的提问，关于话题 {i}。" * 10})
    messages.append({"role": "assistant", "content": f"这是助手第{i}轮的回答。" * 10})

print(f"原始消息数： {len(messages)}")
print(f"原始 token 数: {count_messages_tokens(messages)}")

# 策略 1：滑窗
cm1 = ContextManager(strategy="sliding_window", max_tokens=1500, keep_recent_messages=6)
compressed1 = cm1.compress(messages)
print(f"\n[滑窗] 压缩后消息数: {len(compressed1)}, tokens: {count_messages_tokens(compressed1)}")

# 策略 2：摘要
cm2 = ContextManager(strategy="summarization", max_tokens=1500, keep_recent_messages=6)
compressed2 = cm2.compress(messages)
print(f"[摘要] 压缩后消息数: {len(compressed2)}, tokens: {count_messages_tokens(compressed2)}")
print("\n[摘要] 摘要内容：")
for m in compressed2:
    if "[历史对话摘要]" in (m.get("content") or ""):
        print(m["content"])

