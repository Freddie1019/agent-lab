"""
Day 8 任务 3：POST 请求 + JSON Body
开始接近"包 Agent 成 API"的样子
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# ===== Pydantic 模型：定义请求体的结构 =====
class ResearchRequest(BaseModel):
    """研究请求的数据模型"""
    question: str
    max_steps: int = 10
    model: str = "gpt-4o-mini"
    user_id: Optional[str] = None

class ResearchResponse(BaseModel):
    """ 研究响应的数据模型 """
    task_id: str
    status: str
    answer: Optional[str] = None
    duration_seconds: float = 0.0

@app.post('/research', response_model=ResearchResponse)
def create_research(request: ResearchRequest):
    """模拟"""
    print(f"question={request.question}, max_steps={request.max_steps}")

    return ResearchResponse(
        task_id="fake-task-001",
        status="completed",
        answer=f"这是对'{request.question}'的假回答",
        duration_seconds=1.5,
    )


