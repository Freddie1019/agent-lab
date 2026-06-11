"""
上下文管理器
支持两种策略：
1. sliding_window: 保留最近 N 条消息
2. summarization: 超过阈值时自动用 LLM 摘要

设计原则：
- system message 永远保留
- 工具调用对 (assistant.tool_calls + tool result) 不可拆开
- 提供 token 预算检查接口
"""
from re import S
from typing import Literal
from shared.token_counter import count_messages_tokens
from shared.llm_client import client, DEFAULT_MODEL

class ContextManager:
    def __init__(
        self,
        strategy: Literal["sliding_window", "summarization"] = "sliding_window",
        max_tokens: int = 4000,
        keep_recent_messages: int = 4,
        model: str = DEFAULT_MODEL,
    ):
        self.strategy = strategy
        self.max_tokens = max_tokens
        self.keep_recent_messages = keep_recent_messages
        self.model = model
    
    def current_tokens(self, messages: list) -> int:
        return count_messages_tokens(messages, self.model)
    
    def needs_compression(self, messages: list) -> bool:
        return self.current_tokens(messages) > self.max_tokens
    
    def compress(self, messages: list) -> list:
        """根据 strategy 自动选择压缩方式"""
        if not self.needs_compression(messages):
            return messages

        if self.strategy == "sliding_window":
            return self._sliding_window(messages)
        elif self.strategy == "summarization":
            return self._summarize(messages)
        else:
            raise ValueError(f"Unknow strategy: {self.strategy}")
    
    # ===== 策略 1：滑窗 =====
    def _sliding_window(self, messages: list) -> list:
        """
        保留 system 消息 + 最近 N 条
        ⚠️ 注意：不能把工具调用对拆开
        """
        system_msgs = [m for m in messages if (m["role"] if isinstance(m, dict) else m.role) == "system"]
        non_system = [m for m in messages if (m["role"] if isinstance(m, dict) else m.role) != "system"]

        if len(non_system) <= self.keep_recent_messages:
            return messages
        
        recent = non_system[-self.keep_recent_messages:]

        # 修复工具调用配对：如果第一条 recent 是 role="tool"，往前找它对应的 assistant
        recent = self._fix_tool_pairs(non_system, recent)

        return system_msgs + recent

    def _fix_tool_pairs(self, all_msgs, recent):
        """确保不会单独保留没有 assistant tool_calls 的 tool 消息"""
        if not recent:
            return recent
        
        first = recent[0]
        first_role = first["role"] if isinstance(first, dict) else first.role
        if first_role == "tool":
            # 找它对应的 assistant 消息
            start_idx = len(all_msgs) - len(recent)
            for i in range(start_idx - 1, -1, -1):
                msg = all_msgs[i]
                role = msg["role"] if isinstance(msg, dict) else msg.role
                if role == "assistant":
                    # 把这条 assistant 也带上
                    return all_msgs[i:]
        return recent
    
    # ===== 策略 2：摘要 =====
    def _summarize(self, messages: list) -> list:
        """
        把"老消息"用 LLM 压缩成一段 system 摘要
        保留 system 消息 + 摘要 + 最近 N 条
        """
        system_msgs = [m for m in messages if (m["role"] if isinstance(m, dict) else m.role) == "system"]
        non_system = [m for m in messages if (m["role"] if isinstance(m, dict) else m.role) != "system"]

        if len(non_system) <= self.keep_recent_messages:
            return messages
        
        # 拆分：要被摘要的老消息 vs 要保留的近期消息
        to_summarize = non_system[:-self.keep_recent_messages]
        recent = non_system[-self.keep_recent_messages:]
        recent = self._fix_tool_pairs(non_system, recent)

        # 构造摘要请求
        history_text = self._format_messages_for_summary(to_summarize)
        summary_response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是对话摘要专家。请把下面这段对话历史压缩成简洁的摘要，重点保留：用户的关键身份信息、明确表达过的偏好、达成的共识、未完成的待办事项。用中文输出，不超过 200 字。"},
                {"role": "user", "content": history_text}
            ],
            temperature=0,
        )
        summary = summary_response.choices[0].message.content

        # 把摘要包装成一条 system 消息插入
        summary_msg = {
            "role": "system",
            "content": f"[历史对话摘要]\n{summary}"
        }

        return system_msgs + [summary_msg] + recent
    
    def _format_messages_for_summary(self, messages):
        """把 messages 渲染成可读文本喂给摘要 LLM"""
        lines = []
        for m in messages:
            role = m["role"] if isinstance(m, dict) else m.role
            content = m.get("content") if isinstance(m, dict) else m.content
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)     

