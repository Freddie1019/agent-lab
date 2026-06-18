"""
Deep Research Agent - HTTP API Server (v1)
Week 2 Day 8：把 Week 1 的 Agent 包成 HTTP 接口
"""
import time
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from deep_research_agent.core.agent import ResearchAgent


app = FastAPI(
    title="Deep Research Agent API",
    description="一个能自主搜索互联网的研究 Agent 的 HTTP 接口",
    version="0.1.0",
)


# ===== 请求 / 响应模型 =====
class ResearchRequest(BaseModel):
    question: str
    max_steps: int = 10
    max_tokens_budget: int = 50_000
    model: str = "gpt-4o-mini"


class ResearchResponse(BaseModel):
    status: str
    answer: Optional[str]
    steps: int
    tool_calls: int
    duration_seconds: float
    total_tokens: int
    estimated_cost_usd: float
    errors: list

# ===== 接口 =====
@app.get("/")
def root():
    return {
        "service": "Deep Research Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest):
    """
    执行一次研究任务（同步阻塞，可能要等几十秒）
    
    ⚠️ 注意：这个版本是同步阻塞的——服务在 Agent 执行期间无法响应其他请求。
    Day 10 加流式输出，Week 4 加异步队列。
    """
    agent = ResearchAgent(
        model=request.model,
        max_steps=request.max_steps,
        max_tokens_budget=request.max_tokens_budget,
        verbose=False,  # API 模式不打印到控制台
    )
    
    report = agent.run(request.question)
    time.sleep(20)
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