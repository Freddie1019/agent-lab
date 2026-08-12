import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from deep_research_agent.core.db import models  # noqa: F401
from deep_research_agent.core.db.base import Base
from deep_research_agent.core.settings import get_settings


# Alembic Config，包含 alembic.ini 中的配置。
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# 数据库地址只维护在 Settings/.env 中，不在 alembic.ini 重复配置。
# ConfigParser 会把 % 当成插值语法，因此需要转义 URL 中可能存在的 %。
database_url = get_settings().DATABASE_URL
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)


# 导入 models 后，所有 ORM 表都会注册到 Base.metadata，供 autogenerate 使用。
target_metadata = Base.metadata


def _context_options(*, is_sqlite: bool) -> dict:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        # SQLite 不直接支持大部分 ALTER COLUMN 操作，batch 模式会重建表。
        "render_as_batch": is_sqlite,
    }


def run_migrations_offline() -> None:
    """在不创建数据库连接的情况下生成迁移 SQL。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_context_options(is_sqlite=url.startswith("sqlite")),
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        **_context_options(is_sqlite=connection.dialect.name == "sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    configuration = config.get_section(
        config.config_ini_section,
        {},
    )
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """使用 Settings 中配置的异步数据库执行迁移。"""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
