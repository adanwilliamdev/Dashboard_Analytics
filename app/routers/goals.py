"""Metas de poupanca: valor alvo, quanto ja foi guardado e prazo opcional."""
import math
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_writer
from app.database import get_db
from app.utils import local_now

router = APIRouter(prefix="/goals", tags=["Metas"])


def _out(goal: models.Goal, today: date) -> schemas.GoalOut:
    target = float(goal.target_amount)
    saved = float(goal.saved_amount or 0)
    remaining = max(target - saved, 0.0)
    completed = saved >= target
    days_left = (goal.deadline - today).days if goal.deadline else None
    if completed:
        status = "completed"
    elif days_left is not None and days_left < 0:
        status = "overdue"
    else:
        status = "active"

    required_monthly = None
    if not completed and days_left is not None and days_left >= 0:
        months_left = max(math.ceil(days_left / 30.4375), 1)
        required_monthly = round(remaining / months_left, 2)
    return schemas.GoalOut(
        id=goal.id,
        name=goal.name,
        target_amount=round(target, 2),
        saved_amount=round(saved, 2),
        deadline=goal.deadline,
        remaining=round(remaining, 2),
        pct=round(min(saved / target * 100, 100.0), 1) if target > 0 else 0.0,
        status=status,
        days_left=days_left,
        required_monthly=required_monthly,
    )


def _get_owned(db: Session, goal_id: int, owner_id: int) -> models.Goal:
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id, models.Goal.owner_id == owner_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Meta nao encontrada")
    return goal


def _today() -> date:
    return local_now().date()


@router.get("/", response_model=List[schemas.GoalOut])
def list_goals(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    goals = db.query(models.Goal).filter(models.Goal.owner_id == user.id).order_by(models.Goal.id).all()
    today = _today()
    return [_out(g, today) for g in goals]


@router.post("/", response_model=schemas.GoalOut, status_code=201)
def create_goal(
    payload: schemas.GoalIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    goal = models.Goal(
        name=payload.name,
        target_amount=payload.target_amount,
        saved_amount=payload.saved_amount,
        deadline=payload.deadline,
        owner_id=user.id,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _out(goal, _today())


@router.put("/{goal_id}", response_model=schemas.GoalOut)
def update_goal(
    goal_id: int,
    payload: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    goal = _get_owned(db, goal_id, user.id)
    data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "deadline" in payload.model_fields_set:  # null explicito remove o prazo
        data["deadline"] = payload.deadline
    for key, value in data.items():
        setattr(goal, key, value)
    db.commit()
    db.refresh(goal)
    return _out(goal, _today())


@router.post("/{goal_id}/contribute", response_model=schemas.GoalOut)
def contribute(
    goal_id: int,
    payload: schemas.GoalContribution,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Soma (ou, com valor negativo, retira) um valor do que ja foi guardado. Nunca fica abaixo de zero."""
    goal = _get_owned(db, goal_id, user.id)
    goal.saved_amount = max(float(goal.saved_amount or 0) + payload.amount, 0.0)
    db.commit()
    db.refresh(goal)
    return _out(goal, _today())


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    goal = _get_owned(db, goal_id, user.id)
    db.delete(goal)
    db.commit()
    return Response(status_code=204)
