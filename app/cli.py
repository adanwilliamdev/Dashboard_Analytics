"""Comandos administrativos (rodam no servidor, nunca expostos pela API).

    python -m app.cli create-admin <usuario> <email>   # pede a senha no terminal
    python -m app.cli promote <usuario>                # promove um usuario ja cadastrado
    python -m app.cli run-recurring                    # gera as transacoes recorrentes vencidas (cron diario)

Em Docker:  docker compose exec api python -m app.cli create-admin ana ana@exemplo.com

A senha tambem pode vir da variavel ADMIN_PASSWORD (util em automacao); evite deixa-la no historico.
"""
import argparse
import getpass
import os
import sys
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import hash_password


class CliError(Exception):
    pass


def _find(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(func.lower(models.User.username) == username.strip().lower()).first()


def create_admin(db: Session, username: str, email: str, password: str) -> models.User:
    try:
        data = schemas.UserCreate(username=username, email=email, password=password)  # mesmas regras do cadastro
    except ValidationError as exc:
        raise CliError("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc
    if _find(db, data.username):
        raise CliError(f"O usuario {data.username!r} ja existe. Use `promote` para torna-lo admin.")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise CliError(f"O e-mail {data.email!r} ja esta cadastrado.")
    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="admin",
        email_verified=True,  # criado pelo operador no servidor: dispensa o link de verificacao
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def promote(db: Session, username: str) -> models.User:
    user = _find(db, username)
    if user is None:
        raise CliError(f"Usuario {username!r} nao encontrado.")
    user.role = "admin"
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def run_recurring(db: Session) -> dict:
    """Gera as recorrentes vencidas de todos os usuarios ativos. Retorna {usuario: criadas}."""
    from app import recurring

    out = {}
    for user in db.query(models.User).filter(models.User.is_active.is_(True)).order_by(models.User.id).all():
        created = recurring.materialize_due(db, user.id)
        if created:
            out[user.username] = created
    return out


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_create = sub.add_parser("create-admin", help="cria um usuario ja com perfil admin")
    p_create.add_argument("username")
    p_create.add_argument("email")
    p_promote = sub.add_parser("promote", help="promove um usuario existente a admin")
    p_promote.add_argument("username")
    sub.add_parser("run-recurring", help="gera as transacoes recorrentes vencidas de todos os usuarios")
    args = parser.parse_args(argv)

    from app.database import SessionLocal  # import tardio: o parser de argumentos nao abre o banco

    try:
        with SessionLocal() as db:
            if args.command == "create-admin":
                password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Senha do admin: ")
                user = create_admin(db, args.username, args.email, password)
                print(f"Admin {user.username!r} criado.")
            elif args.command == "run-recurring":
                created = run_recurring(db)
                total = sum(created.values())
                print(f"{total} transacao(oes) recorrente(s) gerada(s) para {len(created)} usuario(s).")
            else:
                user = promote(db, args.username)
                print(f"{user.username!r} agora e admin.")
    except CliError as exc:
        print("Erro: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
