"""
HTTP API 入口，只做路由组装
"""
# import os, sys
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fastapi import FastAPI
from deep_research_agent.api.v1.routes import router as v1_router
from deep_research_agent.api.error_handlers import register_error_handlers
from deep_research_agent.api.v1 import sessions_routes
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="Deep Research Agent API",
    version="0.2.0",  # ← 升级了版本
)

# 挂载静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

register_error_handlers(app)

@app.get("/")
def root():
    """返回 HTML 前端"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


# 挂载 v1 路由, 会话路由
app.include_router(v1_router)
app.include_router(sessions_routes.router)