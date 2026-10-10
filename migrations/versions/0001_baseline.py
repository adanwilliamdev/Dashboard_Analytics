"""Baseline: esquema da v1 (users e transactions).

Bancos criados pela v1 ja tem estas tabelas: use `alembic stamp 0001` neles e depois
`alembic upgrade head`. Em bancos novos esta migracao cria as tabelas.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(50), nullable=False),
            sa.Column("email", sa.String(120), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not insp.has_table("transactions"):
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("description", sa.String(200), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("type", sa.String(20), nullable=False),
            sa.Column("date", sa.DateTime(), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        )
        op.create_index("ix_transactions_id", "transactions", ["id"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("users")
