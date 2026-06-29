"""
会话数据模型
今天的版本是内存版，下周升级为持久化
"""
import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel,Field

class Message(BaseModel):
    """ 对话历史中的一条消息 """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: Literal["user", "assistant", "system", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    created_at:  datetime = Field(default_factory=datetime.now)

    # 新增 Day12
    status: Literal["complete", "interrupted", "failed"] = "complete"
    error_detail: Optional[str] = None

class Session(BaseModel):
    """ 一个对话会话 """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_processing: bool = False

    def add_message(self, message: Message):
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def to_llm_messages(self) -> list[dict]:
        """转换为 LLM API 接受的格式"""
        result = []
        for m in self.messages:
            msg = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            result.append(msg)
        return result

