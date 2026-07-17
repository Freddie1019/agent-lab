import asyncio
from pathlib import Path
from deep_research_agent.core.db.base import Base
from deep_research_agent.core.db.session import engine

# 重要：必须导入 models，让 SQLAlchemy 知道有哪些表
from deep_research_agent.core.db import models

async def init_db() -> None:

    """
    初始化数据库表
    """
    Path("data").mkdir(exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    

async def drop_db() -> None:
    """
    删除所有表
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

if __name__ == "__main__":
    asyncio.run(init_db())

