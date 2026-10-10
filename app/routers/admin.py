"""Administracao de usuarios (somente role=admin)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_admin
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_target(db: Session, user_id: int, admin: models.User) -> models.User:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Voce nao pode alterar a propria conta por aqui")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return user


@router.get("/users", response_model=List[schemas.AdminUserOut])
def list_users(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    counts = dict(
        db.query(models.Transaction.owner_id, func.count(models.Transaction.id))
        .group_by(models.Transaction.owner_id)
        .all()
    )
    users = db.query(models.User).order_by(models.User.id).all()
    return [
        schemas.AdminUserOut.model_validate(u).model_copy(update={"transaction_count": int(counts.get(u.id, 0))})
        for u in users
    ]


@router.put("/users/{user_id}/role", response_model=schemas.UserOut)
def set_role(
    user_id: int,
    payload: schemas.RoleIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    user = _get_target(db, user_id, admin)
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/active", response_model=schemas.UserOut)
def set_active(
    user_id: int,
    payload: schemas.ActiveIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    user = _get_target(db, user_id, admin)
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
