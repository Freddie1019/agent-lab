"""
API v1 路由
"""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from deep_research_agent.core.agent import ResearchAgent
from deep_research_agent.core.domain import ResearchTask
from deep_research_agent.api.schemas.v1 import ResearchRequest, ResearchResponse

router = APIRouter(prefix="/v1", tags=["v1"])

@router.post("/research", response_model=ResearchResponse)
def create_research(request: ResearchRequest):
    # ★ 防腐层：API 模型 → 领域模型
    task = ResearchTask.from_api_request(request)

    agent = ResearchAgent(
        model=task.model,
        max_steps=task.max_steps,
        max_tokens_budget=task.max_tokens_budget,
        verbose=False,
    )
    
    report = agent.run(task.question)
    
    return ResearchResponse(
        status=report.status,
        answer=report.final_answer,
        steps=report.steps,
        tool_calls=report.tool_calls,
        duration_seconds=report.duration_seconds,
        total_tokens=report.total_tokens,
        estimated_cost_usd=report.estimated_cost_usd,
        errors=report.errors,
    )

