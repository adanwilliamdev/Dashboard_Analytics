"""Transacoes recorrentes: regras que geram sozinhas a transacao de cada ocorrencia."""
from datetime import datetime, time
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import alerts, models, recurring, schemas
from app.auth import get_current_user, require_writer
from app.cache import get_cache, user_ns
from app.database import get_db
from app.routers.transactions import check_account
from app.utils import local_now

router = APIRouter(prefix="/recurring", tags=["Recorrentes"])


def _midnight(d) -> datetime:
    return datetime.combine(d, time.min)


def _get_owned(db: Session, rule_id: int, owner_id: int) -> models.RecurringRule:
    rule = (
        db.query(models.RecurringRule)
        .filter(models.RecurringRule.id == rule_id, models.RecurringRule.owner_id == owner_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Regra recorrente nao encontrada")
    return rule


@router.get("/", response_model=List[schemas.RecurringOut])
def list_rules(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    recurring.materialize_due(db, user.id)
    return (
        db.query(models.RecurringRule)
        .filter(models.RecurringRule.owner_id == user.id)
        .order_by(models.RecurringRule.next_date, models.RecurringRule.id)
        .all()
    )


@router.post("/", response_model=schemas.RecurringOut, status_code=201)
def create_rule(
    payload: schemas.RecurringIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Cria a regra. A primeira ocorrencia e `start_date` (padrao: hoje); datas passadas geram o retroativo."""
    check_account(db, payload.account_id, user.id)
    start = payload.start_date or local_now().date()
    if payload.end_date is not None and payload.end_date < start:
        raise HTTPException(status_code=422, detail="end_date nao pode ser anterior a start_date")
    rule = models.RecurringRule(
        description=payload.description,
        amount=payload.amount,
        category=payload.category,
        type=payload.type,
        frequency=payload.frequency,
        anchor_day=start.day,
        next_date=_midnight(start),
        end_date=_midnight(payload.end_date) if payload.end_date else None,
        account_id=payload.account_id,
        owner_id=user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=schemas.RecurringOut)
def update_rule(
    rule_id: int,
    payload: schemas.RecurringUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    rule = _get_owned(db, rule_id, user.id)
    sent = payload.model_fields_set
    data = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None and k not in ("next_date", "end_date", "account_id")
    }
    if "account_id" in sent:  # null desvincula
        check_account(db, payload.account_id, user.id)
        data["account_id"] = payload.account_id
    if payload.next_date is not None:
        data["next_date"] = _midnight(payload.next_date)
        data["anchor_day"] = payload.next_date.day
    if "end_date" in sent:  # null remove o fim
        data["end_date"] = _midnight(payload.end_date) if payload.end_date else None
    for key, value in data.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Remove a regra. As transacoes ja geradas permanecem."""
    rule = _get_owned(db, rule_id, user.id)
    db.query(models.Transaction).filter(
        models.Transaction.owner_id == user.id, models.Transaction.recurring_rule_id == rule.id
    ).update({"recurring_rule_id": None}, synchronize_session=False)
    db.delete(rule)
    db.commit()
    get_cache().invalidate(user_ns(user.id))
    return Response(status_code=204)


@router.post("/run", response_model=schemas.RecurringRunResult)
def run_now(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Gera agora as ocorrencias vencidas (tambem acontece sozinho ao abrir o dashboard)."""
    created = recurring.materialize_due(db, user.id)
    if created:
        alerts.schedule(background, user.id)
    return {"created": created}
