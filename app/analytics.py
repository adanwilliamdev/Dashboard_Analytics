"""Camada de dados da analise: carrega do banco e delega ao nucleo puro (analytics_core)."""
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import analytics_core as core
from app import models
from app.utils import local_now

HISTORY_DAYS = 400  # janela maxima carregada em memoria por requisicao


# ------------------------------------------------------------------ loaders
def _load_df(db: Session, owner_id: int, since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    T = models.Transaction
    stmt = select(T.id, T.description, T.amount, T.category, T.type, T.date).where(T.owner_id == owner_id)
    if since is not None:
        stmt = stmt.where(T.date >= since.to_pydatetime())
    rows = db.execute(stmt).all()
    return core.normalize(pd.DataFrame([tuple(r) for r in rows], columns=core.COLUMNS))


def _budgets(db: Session, owner_id: int) -> Dict[str, float]:
    rows = db.query(models.Budget).filter(models.Budget.owner_id == owner_id).all()
    return {b.category: float(b.monthly_limit) for b in rows}


def _today() -> pd.Timestamp:
    """Hoje no fuso da aplicacao (APP_TIMEZONE), como Timestamp naive a meia-noite."""
    return pd.Timestamp(local_now()).normalize()


def _split(df: pd.DataFrame, days: int, today: pd.Timestamp):
    """Janela atual (ultimos `days` dias corridos, incluindo hoje) e a anterior equivalente."""
    start = today - pd.Timedelta(days=days - 1)
    prev_start = start - pd.Timedelta(days=days)
    cur = df[df["date"] >= start]
    prev = df[(df["date"] >= prev_start) & (df["date"] < start)]
    return cur, prev, start


def _load_window(db: Session, owner_id: int, days: int):
    today = _today()
    since = today - pd.Timedelta(days=max(2 * days, HISTORY_DAYS))
    df = _load_df(db, owner_id, since)
    return df, today


def _anomalies(df: pd.DataFrame, today: pd.Timestamp, start: pd.Timestamp, limit: int) -> List[Dict[str, Any]]:
    """Baseline = ate 180 dias de historico; so reporta o que caiu na janela atual."""
    base_start = min(start, today - pd.Timedelta(days=179))
    found = core.detect_anomalies(df[df["date"] >= base_start], limit=500)
    in_window = [a for a in found if a["date"] >= start.strftime("%Y-%m-%d")]
    return in_window[:limit]


# ------------------------------------------------------- funcoes por endpoint
def get_summary(db: Session, owner_id: int, days: int = 30) -> Dict[str, Any]:
    df, today = _load_window(db, owner_id, days)
    cur, prev, _ = _split(df, days, today)
    return core.summary_with_comparison(cur, prev, days)


def get_by_category(db: Session, owner_id: int, days: int = 30, tx_type: Optional[str] = None) -> List[Dict[str, Any]]:
    df, today = _load_window(db, owner_id, days)
    cur, _, _ = _split(df, days, today)
    rows = core.by_category(cur)
    return [r for r in rows if r["type"] == tx_type] if tx_type else rows


def get_timeseries(db: Session, owner_id: int, days: int = 30) -> List[Dict[str, Any]]:
    df, today = _load_window(db, owner_id, days)
    cur, _, start = _split(df, days, today)
    return core.timeseries(cur, start=start, end=today)


def get_top_expenses(db: Session, owner_id: int, limit: int = 5, days: Optional[int] = None) -> List[Dict[str, Any]]:
    df, today = _load_window(db, owner_id, days or HISTORY_DAYS)
    if days:
        df, _, _ = _split(df, days, today)
    return core.top_expenses(df, limit)


def get_monthly(db: Session, owner_id: int, months: int = 12) -> List[Dict[str, Any]]:
    today = _today()
    first_of_month = today.replace(day=1) - pd.DateOffset(months=months - 1)
    return core.monthly(_load_df(db, owner_id, first_of_month), months)


def get_weekday(db: Session, owner_id: int, days: int = 90) -> List[Dict[str, Any]]:
    df, today = _load_window(db, owner_id, days)
    cur, _, _ = _split(df, days, today)
    return core.weekday_profile(cur)


def get_forecast(db: Session, owner_id: int, horizon: int = 30) -> Dict[str, Any]:
    df, today = _load_window(db, owner_id, 90)
    return core.forecast(df, horizon=horizon, today=today.to_pydatetime())


def get_anomalies(db: Session, owner_id: int, days: int = 90, limit: int = 20) -> List[Dict[str, Any]]:
    df, today = _load_window(db, owner_id, max(days, 180))
    _, _, start = _split(df, days, today)
    return _anomalies(df, today, start, limit)


def get_recurring(db: Session, owner_id: int) -> List[Dict[str, Any]]:
    df, _ = _load_window(db, owner_id, HISTORY_DAYS // 2)
    return core.detect_recurring(df)


def get_budget_status(db: Session, owner_id: int) -> List[Dict[str, Any]]:
    today = _today()
    df = _load_df(db, owner_id, today.replace(day=1))
    return core.budget_status(df, _budgets(db, owner_id), today=today.to_pydatetime())


# ---------------------------------------------------------------- overview
def get_overview(db: Session, owner_id: int, days: int = 30) -> Dict[str, Any]:
    """Tudo em UMA consulta ao banco: ideal para o dashboard (menos round-trips)."""
    df, today = _load_window(db, owner_id, days)
    cur, prev, start = _split(df, days, today)

    summary = core.summary_with_comparison(cur, prev, days)
    categories = core.by_category(cur)
    weekday = core.weekday_profile(cur)
    anomalies = _anomalies(df, today, start, 10)
    budgets = core.budget_status(df, _budgets(db, owner_id), today=today.to_pydatetime())

    return {
        "days": days,
        "summary": summary,
        "by_category": categories,
        "timeseries": core.timeseries(cur, start=start, end=today),
        "weekday": weekday,
        "top_expenses": core.top_expenses(cur, 5),
        "monthly": core.monthly(df, 12),
        "forecast": core.forecast(df, horizon=30, today=today.to_pydatetime()),
        "anomalies": anomalies,
        "recurring": core.detect_recurring(df),
        "budgets": budgets,
        "insights": core.build_insights(summary, categories, weekday, anomalies, budgets, days),
    }
