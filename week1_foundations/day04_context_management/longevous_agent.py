"""
集大成：能持续对话 100+ 轮的 Agent
- 每轮调用前自动压缩
- 实时监控 token 用量
- 自动选择压缩策略
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.context_manager import ContextManager
from shared.token_counter import count_messages_tokens

class LongevousChatAgent:
    def __init__(
        self,
        strategy: str = "summarization",
        max_tokens: int = 3000,
        keep_recent_messages: int = 4,
    ):
        self.messages = [
            {"role": "system", "content": "你是一个有耐心、记性好的长期对话助手。"}
        ]
        self.context_manager = ContextManager(
            strategy=strategy,
            max_tokens=max_tokens,
            keep_recent_messages=keep_recent_messages,
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.compression_count = 0
        self.turn = 0
    
    def chat(self, user_input: str) -> str:
        self.turn += 1
        self.messages.append({"role": "user", "content": user_input})

        # ★ 关键步骤：每轮前压缩
        before_tokens = count_messages_tokens(self.messages)
        if self.context_manager.needs_compression(self.messages):
            self.messages = self.context_manager.compress(self.messages)
            self.compression_count += 1
            after_tokens = count_messages_tokens(self.messages)
            print(f" [自动压缩] {before_tokens} → {after_tokens} tokens")
        
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=self.messages,
            temperature=0.7,
        )

        self.total_input_tokens += response.usage.prompt_tokens
        self.total_output_tokens += response.usage.completion_tokens

        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply
    
    def stats(self):
        return {
            "turn": self.turn,
            "messages_count": len(self.messages),
            "current_context_tokens": count_messages_tokens(self.messages),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "compression_count": self.compression_count,
        }

# ===== 交互式使用 =====
if __name__ == "__main__":
    agent = LongevousChatAgent(strategy="summarization", max_tokens=2000)
    print("长寿命对话 Agent 已启动（输入 'quit' 退出，'stats' 查看统计）\n")

    while True:
        user_input = input("你：").strip()
        if user_input == "quit":
            break
        if user_input == "status":
            print(agent.stats())
            continue
        reply = agent.chat(user_input)
        print(f"AI: {reply}\n")

    print("\n最终统计:", agent.stats())  