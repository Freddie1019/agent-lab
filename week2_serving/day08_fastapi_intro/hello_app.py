"""
Day 8 任务 1：第一个 FastAPI 接口
跑通 HTTP 服务端的"Hello World"
"""
from fastapi import FastAPI

app = FastAPI(
    title="My First Agent API",
    description="Week 2 Day 8: 学 FastAPI",
    version="0.0.1",
)

@app.get('/')
def root():
    """ 根路径 返回简单问候 """
    return {"message": "Hello, FastAPI"}

@app.get("/health")
def health():
    """健康检查接口（业界标准实践）"""
    return {"status": "ok"}