"""
领域模型：业务内部的"权威"数据结构
与 API 层完全解耦
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

@dataclass(frozen=True)
class ResearchTask:
    """业务内部的研究任务表示（不可变）"""
    task_id: str
    question: str
    max_steps: int
    max_tokens_budget: int
    model: str
    user_id: Optional[str]
    created_at: datetime

    @classmethod
    def from_api_request(cls, request, user_id: Optional[str] = None) -> "ResearchTask":
        """边界转换：API DTO → 领域模型"""
        return cls(
            task_id=str(uuid.uuid4()),
            question=request.question,
            max_steps=request.max_steps,
            max_tokens_budget=request.max_tokens_budget,
            model=request.model,
            user_id=user_id or request.user_id,
            created_at=datetime.now(),
        )
    