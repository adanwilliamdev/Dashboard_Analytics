"""v2: orcamentos, perfis de usuario, indices e valores monetarios em NUMERIC(12,2).

Idempotente: verifica o que ja existe (bancos criados com create_all ja nascem no formato novo).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _columns(insp, table):
    return {c["name"]: c for c in insp.get_columns(table)}


def _indexes(insp, table):
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ---- users: role / is_active
    ucols = _columns(insp, "users")
    with op.batch_alter_table("users") as batch:
        if "role" not in ucols:
            batch.add_column(sa.Column("role", sa.String(20), nullable=False, server_default="user"))
        if "is_active" not in ucols:
            batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    # ---- transactions: indices + NUMERIC
    existing = _indexes(insp, "transactions")
    if "ix_tx_owner_date" not in existing:
        op.create_index("ix_tx_owner_date", "transactions", ["owner_id", "date"])
    if "ix_tx_owner_type_category" not in existing:
        op.create_index("ix_tx_owner_type_category", "transactions", ["owner_id", "type", "category"])

    amount_type = _columns(insp, "transactions")["amount"]["type"]
    if not isinstance(amount_type, sa.Numeric) or isinstance(amount_type, sa.Float):
        with op.batch_alter_table("transactions") as batch:
            batch.alter_column(
                "amount",
                existing_type=sa.Float(),
                type_=sa.Numeric(12, 2),
                existing_nullable=False,
            )

    # ---- budgets
    if not insp.has_table("budgets"):
        op.create_table(
            "budgets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.UniqueConstraint("owner_id", "category", name="uq_budget_owner_category"),
        )
        op.create_index("ix_budgets_id", "budgets", ["id"])
        op.create_index("ix_budgets_owner_id", "budgets", ["owner_id"])


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_index("ix_tx_owner_type_category", table_name="transactions")
    op.drop_index("ix_tx_owner_date", table_name="transactions")
    with op.batch_alter_table("transactions") as batch:
        batch.alter_column("amount", existing_type=sa.Numeric(12, 2), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
        batch.drop_column("role")
