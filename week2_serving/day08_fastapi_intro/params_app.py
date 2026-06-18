"""
Day 8 任务 2：理解参数传递的几种方式
"""
from fastapi import FastAPI
from typing import Optional

app = FastAPI()

# ===== 1. Path 参数 =====
@app.get("/research/{task_id}")
def getResearch(task_id: int):
    """
    任务 ID 是 URL 的一部分（path parameter）
    适用：标识"哪一个资源"
    """
    return {"task_id": task_id, "status": "completed"}

# ===== 2. Query 参数 =====
@app.get("/research")
def list_research(
    page: int=1,
    size: int=10,
    status: Optional[str] = None,
):
    """
    查询参数（query parameter）：URL 问号后面
    例：GET /research?page=2&size=20&status=completed
    适用：筛选、分页、排序等"可选条件"
    """
    return {
        "page": page,
        "size": size,
        "status_filter": status,
        "items": []  # 模拟返回空列表
    }

# ===== 3. 必填 vs 可选 =====
@app.get("/search")
def search(
    q: int,
    limit: int=5,
    sort_by: Optional[str] = None, 
):
    return {
        "query": q,
        "limit": limit,
        "sort_by": sort_by,
    }