"""Orcamentos mensais por categoria."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_writer
from app.cache import get_cache, user_ns
from app.database import get_db

router = APIRouter(prefix="/budgets", tags=["Orcamentos"])


def _key(category: str) -> str:
    key = category.strip().lower()
    if not key or len(key) > 80:
        raise HTTPException(status_code=422, detail="Categoria invalida")
    return key


@router.get("/", response_model=List[schemas.BudgetOut])
def list_budgets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Budget)
        .filter(models.Budget.owner_id == current_user.id)
        .order_by(models.Budget.category)
        .all()
    )


@router.put("/{category}", response_model=schemas.BudgetOut)
def upsert_budget(
    category: str,
    payload: schemas.BudgetIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    key = _key(category)
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.owner_id == current_user.id, models.Budget.category == key)
        .first()
    )
    if budget:
        budget.monthly_limit = payload.monthly_limit
    else:
        budget = models.Budget(category=key, monthly_limit=payload.monthly_limit, owner_id=current_user.id)
        db.add(budget)
    db.commit()
    db.refresh(budget)
    get_cache().invalidate(user_ns(current_user.id))
    return budget


@router.delete("/{category}", status_code=204)
def delete_budget(
    category: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    key = _key(category)
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.owner_id == current_user.id, models.Budget.category == key)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Orcamento nao encontrado")
    db.delete(budget)
    db.commit()
    get_cache().invalidate(user_ns(current_user.id))
    return Response(status_code=204)
