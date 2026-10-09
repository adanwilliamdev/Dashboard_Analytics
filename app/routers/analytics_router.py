"""Rotas de analytics (usa Pandas)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import analytics, models
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def summary(
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return analytics.get_summary(db, current_user.id, days=days)


@router.get("/by-category")
def by_category(
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return analytics.get_by_category(db, current_user.id, days=days)


@router.get("/timeseries")
def timeseries(
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return analytics.get_timeseries(db, current_user.id, days=days)


@router.get("/top-expenses")
def top_expenses(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return analytics.get_top_expenses(db, current_user.id, limit=limit)
