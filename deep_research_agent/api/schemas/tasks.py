import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from deep_research_agent.core.task import TaskStatus

AllowedTaskModel = Literal[
    "gpt-4o-mini",
    "gpt-4o",
    "claude-3-5-sonnet",
]

class TaskSubmitRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    question: str = Field(
        min_length=5,
        max_length=2000,
    )

    max_steps: int = Field(
        default=10,
        ge=1,
        le=30,
    )

    max_tokens_budget: int = Field(
        default=50_000,
        ge=1000,
        le=200_000,
    )

    model: AllowedTaskModel = "gpt-4o-mini"

    @field_validator("question")
    @classmethod
    def validate_question(
        cls,
        value: str,
    ) -> str:
        value = re.sub(r"\s+", " ", value.strip())

        if not re.search(
            r"[\w\u4e00-\u9fa5]",
            value,
        ):
            raise ValueError(
                "question must contain meaningful text"
            )

        trivial = {
            "hi"
            "hello",
            "test",
            "你好",
            "?",
        }

        if value.lower() in trivial:
            raise ValueError(
                "question is too trivial for research"
            )

        return value

    @classmethod
    @model_validator(mode="after")
    def validate_budget(self):
        tokens_per_step = {
            "gpt-4o-mini": 3000,
            "gpt-4o": 5000,
            "claude-3-5-sonnet": 4000,
        }

        estimated = (
            self.max_steps
            * tokens_per_step[self.model]
        )

        if estimated > self.max_tokens_budget:
            raise ValueError(
                "max_steps and model may exceed "
                "max_tokens_budget"
            )

        return self

class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created: bool
    status_url: str
    result_url: str

class TaskDetailResponse(BaseModel):
    id: str
    user_id: str
    session_id: str
    task_type: str
    status: TaskStatus
    request_payload: dict[str, Any]
    error_type: str | None
    error_detail: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class TaskResultResponse(BaseModel):
    task_id: str
    status: TaskStatus
    ready: bool
    run_id: str | None = None
    answer: str | None = None
    error_type: str | None = None
    error_detail: str | None = None