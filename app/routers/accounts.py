"""Contas/carteiras. Saldo = saldo inicial + receitas - despesas das transacoes vinculadas."""
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, recurring, schemas
from app.auth import get_current_user, require_writer
from app.cache import get_cache, user_ns
from app.database import get_db

router = APIRouter(prefix="/accounts", tags=["Contas"])


def _get_owned(db: Session, account_id: int, owner_id: int) -> models.Account:
    acc = (
        db.query(models.Account)
        .filter(models.Account.id == account_id, models.Account.owner_id == owner_id)
        .first()
    )
    if not acc:
        raise HTTPException(status_code=404, detail="Conta nao encontrada")
    return acc


def _name_taken(db: Session, owner_id: int, name: str, exclude_id: int = 0) -> bool:
    return (
        db.query(models.Account.id)
        .filter(
            models.Account.owner_id == owner_id,
            func.lower(models.Account.name) == name.lower(),
            models.Account.id != exclude_id,
        )
        .first()
        is not None
    )


def _totals(db: Session, owner_id: int) -> Dict[int, Dict[str, float]]:
    T = models.Transaction
    rows = (
        db.query(T.account_id, T.type, func.coalesce(func.sum(T.amount), 0), func.count(T.id))
        .filter(T.owner_id == owner_id, T.account_id.isnot(None))
        .group_by(T.account_id, T.type)
        .all()
    )
    out: Dict[int, Dict[str, float]] = {}
    for account_id, tx_type, total, count in rows:
        d = out.setdefault(account_id, {"income": 0.0, "expense": 0.0, "count": 0})
        d[tx_type] = float(total)
        d["count"] += int(count)
    return out


def _out(acc: models.Account, totals: Dict[int, Dict[str, float]]) -> schemas.AccountOut:
    t = totals.get(acc.id, {"income": 0.0, "expense": 0.0, "count": 0})
    initial = float(acc.initial_balance or 0)
    return schemas.AccountOut(
        id=acc.id,
        name=acc.name,
        type=acc.type,
        initial_balance=round(initial, 2),
        income=round(t["income"], 2),
        expense=round(t["expense"], 2),
        balance=round(initial + t["income"] - t["expense"], 2),
        transaction_count=int(t["count"]),
    )


@router.get("/", response_model=List[schemas.AccountOut])
def list_accounts(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    recurring.materialize_due(db, user.id)  # o saldo precisa incluir as recorrentes vencidas
    totals = _totals(db, user.id)
    accounts = db.query(models.Account).filter(models.Account.owner_id == user.id).order_by(models.Account.name).all()
    return [_out(a, totals) for a in accounts]


@router.post("/", response_model=schemas.AccountOut, status_code=201)
def create_account(
    payload: schemas.AccountIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    if _name_taken(db, user.id, payload.name):
        raise HTTPException(status_code=400, detail="Ja existe uma conta com esse nome")
    acc = models.Account(
        name=payload.name, type=payload.type, initial_balance=payload.initial_balance, owner_id=user.id
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    get_cache().invalidate(user_ns(user.id))
    return _out(acc, _totals(db, user.id))


@router.put("/{account_id}", response_model=schemas.AccountOut)
def update_account(
    account_id: int,
    payload: schemas.AccountUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    acc = _get_owned(db, account_id, user.id)
    data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in data and _name_taken(db, user.id, data["name"], exclude_id=acc.id):
        raise HTTPException(status_code=400, detail="Ja existe uma conta com esse nome")
    for key, value in data.items():
        setattr(acc, key, value)
    db.commit()
    db.refresh(acc)
    get_cache().invalidate(user_ns(user.id))
    return _out(acc, _totals(db, user.id))


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Exclui a conta. As transacoes NAO sao apagadas: ficam sem conta."""
    acc = _get_owned(db, account_id, user.id)
    db.query(models.Transaction).filter(
        models.Transaction.owner_id == user.id, models.Transaction.account_id == acc.id
    ).update({"account_id": None}, synchronize_session=False)
    db.query(models.RecurringRule).filter(
        models.RecurringRule.owner_id == user.id, models.RecurringRule.account_id == acc.id
    ).update({"account_id": None}, synchronize_session=False)
    db.delete(acc)
    db.commit()
    get_cache().invalidate(user_ns(user.id))
    return Response(status_code=204)
