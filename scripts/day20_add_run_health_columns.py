import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from deep_research_agent.core.db.session import engine

COLUMN_DDL = {
    "runtime_id": (
        "ALTER TABLE agent_runs "
        "ADD COLUMN runtime_id VARCHAR(160)"
    ),
    "last_heartbeat_at": (
        "ALTER TABLE agent_runs "
        "ADD COLUMN last_heartbeat_at TIMESTAMP"
    ),
    "stale_detected_at": (
        "ALTER TABLE agent_runs "
        "ADD COLUMN stale_detected_at TIMESTAMP"
    ),
}

def get_existing_columns(sync_connection) -> set[str]:
    inspector = inspect(sync_connection)

    return {
        column["name"]
        for column in inspector.get_columns("agent_runs")
    }

async def migrate() -> None:
    async with engine.begin() as connection:
        existing_columns = await connection.run_sync(
            get_existing_columns
        )

        for column_name, ddl in COLUMN_DDL.items():
            if column_name in existing_columns:
                print(f"[skip] {column_name} 已存在")
                continue

            await connection.execute(text(ddl))
            print(f"[add] {column_name}")

    print("Day20 AgentRun 健康字段迁移完成")


if __name__ == "__main__":
    asyncio.run(migrate())