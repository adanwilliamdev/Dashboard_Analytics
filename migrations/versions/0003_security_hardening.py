"""Seguranca: username unico sem diferenciar maiusculas + token_version (revogacao de JWT).

- users.token_version: incrementado ao trocar a senha; JWTs antigos deixam de valer.
- indice unico em lower(username): "Admin" e "admin" nao coexistem mais.

Se ja existirem usernames que colidem ignorando maiusculas, a migracao PARA com a lista deles:
resolva manualmente (renomeie/exclua um dos lados) e rode `alembic upgrade head` de novo.

Idempotente (bancos criados por create_all ja nascem no formato novo).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INDEX = "uq_users_username_lower"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols = {c["name"] for c in insp.get_columns("users")}
    if "token_version" not in cols:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    clashes = bind.execute(
        sa.text("SELECT lower(username) FROM users GROUP BY lower(username) HAVING COUNT(*) > 1")
    ).fetchall()
    if clashes:
        names = ", ".join(sorted(row[0] for row in clashes))
        raise RuntimeError(
            "Nao e possivel criar o indice unico de username (sem diferenciar maiusculas): "
            f"ha usernames duplicados ignorando a caixa: {names}. Resolva-os e rode a migracao novamente."
        )
    # SQL direto: o reflection do SQLAlchemy nao lista indices funcionais de forma confiavel
    op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON users (lower(username))")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
