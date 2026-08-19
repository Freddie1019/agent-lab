"""add task records

Revision ID: d23_task_records
Revises: c1357bf15f54
Create Date: 2026-08-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d23_task_records"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "c1357bf15f54"
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "task_records",
        sa.Column(
            "id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "task_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "request_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "request_payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "error_type",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "error_detail",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_task_user_idempotency_key",
        ),
    )

    op.create_index(
        op.f("ix_task_records_user_id"),
        "task_records",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_task_records_session_id"),
        "task_records",
        ["session_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_task_records_status"),
        "task_records",
        ["status"],
        unique=False,
    )

    with op.batch_alter_table(
        "agent_runs",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_id",
                sa.String(length=128),
                nullable=True,
            )
        )

        batch_op.create_index(
            batch_op.f(
                "ix_agent_runs_task_id"
            ),
            ["task_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_agent_runs_task_id_task_records",
            "task_records",
            ["task_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "agent_runs",
        schema=None,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_agent_runs_task_id_task_records",
            type_="foreignkey",
        )

        batch_op.drop_index(
            batch_op.f(
                "ix_agent_runs_task_id"
            )
        )

        batch_op.drop_column("task_id")

    op.drop_index(
        op.f("ix_task_records_status"),
        table_name="task_records",
    )

    op.drop_index(
        op.f("ix_task_records_session_id"),
        table_name="task_records",
    )

    op.drop_index(
        op.f("ix_task_records_user_id"),
        table_name="task_records",
    )

    op.drop_table("task_records")
