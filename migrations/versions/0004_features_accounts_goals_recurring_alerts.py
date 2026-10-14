"""v4: contas, metas, transacoes recorrentes, alertas de orcamento e verificacao de e-mail.

- users.email_verified
- transactions.account_id / transactions.recurring_rule_id
- tabelas accounts, goals, recurring_rules, alert_settings, alert_logs

Idempotente (bancos criados por create_all ja nascem no formato novo).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _money():
    return sa.Numeric(12, 2)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ---- tabelas novas (accounts e recurring_rules antes: transactions aponta para elas)
    if not insp.has_table("accounts"):
        op.create_table(
            "accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("type", sa.String(20), nullable=False, server_default="checking"),
            sa.Column("initial_balance", _money(), nullable=False, server_default="0"),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("owner_id", "name", name="uq_account_owner_name"),
        )
        op.create_index("ix_accounts_id", "accounts", ["id"])
        op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"])

    if not insp.has_table("recurring_rules"):
        op.create_table(
            "recurring_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("description", sa.String(200), nullable=False),
            sa.Column("amount", _money(), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("type", sa.String(20), nullable=False),
            sa.Column("frequency", sa.String(10), nullable=False),
            sa.Column("anchor_day", sa.Integer(), nullable=False),
            sa.Column("next_date", sa.DateTime(), nullable=False),
            sa.Column("end_date", sa.DateTime(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_recurring_rules_id", "recurring_rules", ["id"])
        op.create_index("ix_recurring_rules_next_date", "recurring_rules", ["next_date"])
        op.create_index("ix_recurring_rules_owner_id", "recurring_rules", ["owner_id"])

    if not insp.has_table("goals"):
        op.create_table(
            "goals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("target_amount", _money(), nullable=False),
            sa.Column("saved_amount", _money(), nullable=False, server_default="0"),
            sa.Column("deadline", sa.Date(), nullable=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_goals_id", "goals", ["id"])
        op.create_index("ix_goals_owner_id", "goals", ["owner_id"])

    if not insp.has_table("alert_settings"):
        op.create_table(
            "alert_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("webhook_url", sa.String(500), nullable=True),
            sa.Column("threshold_pct", sa.Integer(), nullable=False, server_default="100"),
        )

    if not insp.has_table("alert_logs"):
        op.create_table(
            "alert_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("month", sa.String(7), nullable=False),
            sa.Column("threshold_pct", sa.Integer(), nullable=False),
            sa.Column("sent_at", sa.DateTime()),
            sa.UniqueConstraint("owner_id", "category", "month", "threshold_pct", name="uq_alert_once"),
        )
        op.create_index("ix_alert_logs_owner_id", "alert_logs", ["owner_id"])

    # ---- colunas novas
    if "email_verified" not in {c["name"] for c in insp.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))

    tx_cols = {c["name"] for c in insp.get_columns("transactions")}
    with op.batch_alter_table("transactions") as batch:
        if "account_id" not in tx_cols:
            batch.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_transactions_account", "accounts", ["account_id"], ["id"], ondelete="SET NULL")
        if "recurring_rule_id" not in tx_cols:
            batch.add_column(sa.Column("recurring_rule_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_transactions_recurring_rule", "recurring_rules", ["recurring_rule_id"], ["id"], ondelete="SET NULL"
            )
    if "ix_transactions_account_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("transactions")}:
        op.create_index("ix_transactions_account_id", "transactions", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_constraint("fk_transactions_recurring_rule", type_="foreignkey")
        batch.drop_constraint("fk_transactions_account", type_="foreignkey")
        batch.drop_column("recurring_rule_id")
        batch.drop_column("account_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified")
    for table in ("alert_logs", "alert_settings", "goals", "recurring_rules", "accounts"):
        op.drop_table(table)
