"""
V1 API 的请求/响应模型
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

AllowedModel = Literal["gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet"]

class ResearchRequest(BaseModel):
    """研究请求 - 完整校验版"""
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "examples": [
                {
                    "question": "2025 年最受欢迎的开源 Agent 框架有哪些？",
                    "max_steps": 10,
                    "model": "gpt-4o-mini",
                }
            ]
        }
    }
    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="研究问题，至少 5 个字符",
    )
    max_steps: int = Field(
        default=10,
        ge=1,
        le=30,
        description="最大执行步数（1-30）",
    )
    max_tokens_budget: int = Field(
        default=50_000,
        ge=1000,
        le=200_000,
        description="Token 预算上限（1000-200000）",
    )
    model: AllowedModel = Field(
        default="gpt-4o-mini",
        description="使用的 LLM 模型",
    )
    user_id:Optional[str] = Field(
        default=None,
        max_length=100,
        description="用户标识，用于审计日志"
    )
    # === Field Validator: 单字段清洗 ===
    @field_validator("question")
    @classmethod
    def question_must_be_meaningful(cls, v: str) -> str:
        v = v.strip()
        # 去除连续空格
        import re
        v = re.sub(r'\s+', ' ', v)
        # 防止纯标点
        if not re.search(r'[\w\u4e00-\u9fa5]', v):
            raise ValueError("question must contain meaningful text")
        # 防止 trivial 问题
        trivial = {"hi", "hello", "test", "你好", "?"}
        if v.lower() in trivial:
            raise ValueError(f"question '{v}' seems too trivial for research")
        return v
    
    # === Model Validator: 跨字段校验 ===
    @model_validator(mode="after")
    def check_budget_consistency(self):
        # 步数 × 平均每步成本 不能超过预算
        # 简化估算：gpt-4o-mini 每步约 3000 tokens
        TOKENS_PER_STEP = {"gpt-4o-mini": 3000, "gpt-4o": 5000, "claude-3-5-sonnet": 4000}
        estimated = self.max_steps * TOKENS_PER_STEP.get(self.model, 3000)
        if estimated > self.max_tokens_budget:
            raise ValueError(
                f"max_steps ({self.max_steps}) with model {self.model} "
                f"may exceed max_tokens_budget ({self.max_tokens_budget}). "
                f"Estimated: ~{estimated} tokens."
            )
        return self

class ResearchResponse(BaseModel):
    """V1 响应"""
    status: str
    answer: Optional[str]
    steps: int
    tool_calls: int
    duration_seconds: float
    total_tokens: int
    estimated_cost_usd: float
    errors: list