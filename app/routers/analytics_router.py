"""Rotas de analytics (Pandas/NumPy)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import analytics, models, reports
from app import recurring as recurring_service  # o nome `recurring` e da rota abaixo
from app.auth import get_current_user
from app.cache import get_cache, user_ns
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])



def Days():  # noqa: N802 - gera um Query novo por endpoint
    return Query(30, ge=1, le=3650, description="Janela em dias corridos (inclui hoje)")


@router.get("/overview")
def overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Tudo que o dashboard precisa, em uma unica chamada (com cache por usuario)."""
    recurring_service.materialize_due(db, user.id)  # antes do cache: assim ele ja enxerga as recorrentes geradas
    return _cached_overview(db, user.id, days)


def _cached_overview(db: Session, user_id: int, days: int):
    return get_cache().get_or_set(
        user_ns(user_id), f"overview:{days}", lambda: analytics.get_overview(db, user_id, days=days)
    )


@router.get("/report.pdf")
def report_pdf(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Relatorio executivo em PDF."""
    data = reports.build_report_pdf(_cached_overview(db, user.id, days), user.username)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="relatorio_' + str(days) + 'd.pdf"'},
    )


@router.get("/summary")
def summary(days: int = Days(), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return analytics.get_summary(db, user.id, days=days)


@router.get("/by-category")
def by_category(
    days: int = Days(),
    type: Optional[Literal["income", "expense"]] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return analytics.get_by_category(db, user.id, days=days, tx_type=type)


@router.get("/timeseries")
def timeseries(days: int = Days(), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return analytics.get_timeseries(db, user.id, days=days)


@router.get("/monthly")
def monthly(
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return analytics.get_monthly(db, user.id, months=months)


@router.get("/weekday")
def weekday(days: int = Query(90, ge=7, le=3650), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return analytics.get_weekday(db, user.id, days=days)


@router.get("/top-expenses")
def top_expenses(
    limit: int = Query(5, ge=1, le=50),
    days: Optional[int] = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return analytics.get_top_expenses(db, user.id, limit=limit, days=days)


@router.get("/forecast")
def forecast(
    horizon: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return analytics.get_forecast(db, user.id, horizon=horizon)


@router.get("/anomalies")
def anomalies(
    days: int = Query(90, ge=7, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return analytics.get_anomalies(db, user.id, days=days, limit=limit)


@router.get("/recurring")
def recurring(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return analytics.get_recurring(db, user.id)


@router.get("/budgets")
def budgets(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    recurring_service.materialize_due(db, user.id)
    return analytics.get_budget_status(db, user.id)
