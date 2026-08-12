"""Add the AgentRun idempotency key to an existing database."""

import asyncio

from sqlalchemy import inspect, text

from deep_research_agent.core.db.session import engine


async def migrate() -> None:
    async with engine.begin() as connection:
        column_names = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("agent_runs")
            }
        )

        if "idempotency_key" not in column_names:
            await connection.execute(
                text(
                    "ALTER TABLE agent_runs "
                    "ADD COLUMN idempotency_key VARCHAR(128) NULL"
                )
            )

        await connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_agent_run_user_idempotency_key "
                "ON agent_runs (user_id, idempotency_key)"
            )
        )


if __name__ == "__main__":
    asyncio.run(migrate())
