"""
Agent 流式事件类型定义
"""
from typing import Literal, Optional
from pydantic import BaseModel

# 所有可能的事件类型
AgentEventType = Literal[
    "agent_start",      # Agent 开始执行
    "step_start",       # 一个新步骤开始
    "thought",          # Agent 的思考
    "tool_call",        # 调用工具
    "tool_result",      # 工具执行结果
    "answer_chunk",     # 最终答案的 token 增量（流式 LLM 输出）
    "answer_complete",  # 答案完整生成完毕
    "error",            # 错误
    "agent_complete",   # Agent 整体完成
]

class AgentEvent(BaseModel):
    """统一的 Agent 事件结构"""
    type: AgentEventType
    step: int = 0
    data: dict = {}

    def to_sse(self) -> str:
        """序列化为 SSE 事件帧"""
        import json
        # event: type
        # data: {json}
        # \n\n
        return f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"

