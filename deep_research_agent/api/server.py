"""
HTTP API 入口，只做路由组装
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from deep_research_agent.api.v1.routes import router as v1_router
from deep_research_agent.api.error_handlers import register_error_handlers
from deep_research_agent.api.v1 import sessions_routes
from deep_research_agent.core.settings import get_settings
from deep_research_agent.services.run_health_service import run_health_service
from shared.runtime_identity import runtime_identity
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# 挂载 auth 路由
from deep_research_agent.api.v1 import auth_routes

# 挂载 run 路由
from deep_research_agent.api.v1 import runs_routes

# 挂载 task 路由
from deep_research_agent.api.v1 import task_routers

settings = get_settings()

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Application runtime started: runtime_id=%s",
        runtime_identity.instance_id,
    )

    if settings.RUN_RECONCILE_ON_STARTUP:
        report = (
            await run_health_service.reconcile_stale_runs()
        )
        app.state.run_reconcile_report = report
        logger.info(
            "Run reconciliation completed: repaired=%s",
            report.repaired_count,
        )
        for item in report.items:
            logger.warning(
                "Stale Run repaired: run_id=%s "
                "previous=%s new=%s manual_review=%s",
                item.run_id,
                item.previous_status,
                item.new_status,
                item.requires_manual_review,
            )
    reconciler_handle = run_health_service.start_reconciler()
    try:
        yield
    finally:
        await reconciler_handle.stop()
        logger.info(
            "Application runtime stopped: runtime_id=%s",
            runtime_identity.instance_id,
        )
app = FastAPI(
    title="Deep Research Agent API",
    version="0.2.0",  # ← 升级了版本
    lifespan=lifespan
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

# 挂载 auth 路由
app.include_router(auth_routes.router)

# 挂载 run 路由
app.include_router(runs_routes.router)

# 挂载 task 路由
app.include_router(task_routers.router)
