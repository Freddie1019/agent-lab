"""
HTTP API 入口，只做路由组装
"""
# import os, sys
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fastapi import FastAPI
from deep_research_agent.api.v1.routes import router as v1_router
from deep_research_agent.api.error_handlers import register_error_handlers

app = FastAPI(
    title="Deep Research Agent API",
    version="0.2.0",  # ← 升级了版本
)

register_error_handlers(app)

@app.get("/")
def root():
    return {
        "service": "Deep Research Agent",
        "versions": ["v1"],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# 挂载 v1 路由
app.include_router(v1_router)