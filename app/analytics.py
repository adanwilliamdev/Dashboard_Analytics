"""Processamento de dados com Pandas."""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app import models


def _load_dataframe(db: Session, owner_id: int, days: Optional[int] = None) -> pd.DataFrame:
    query = db.query(models.Transaction).filter(models.Transaction.owner_id == owner_id)
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(models.Transaction.date >= since)
    rows = query.all()

    if not rows:
        return pd.DataFrame(columns=["id", "description", "amount", "category", "type", "date"])

    df = pd.DataFrame([
        {
            "id": r.id,
            "description": r.description,
            "amount": r.amount,
            "category": r.category,
            "type": r.type,
            "date": r.date,
        }
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_summary(db: Session, owner_id: int, days: Optional[int] = None) -> dict:
    df = _load_dataframe(db, owner_id, days)

    if df.empty:
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "balance": 0.0,
            "transaction_count": 0,
            "avg_transaction": 0.0,
        }

    income = df.loc[df["type"] == "income", "amount"].sum()
    expense = df.loc[df["type"] == "expense", "amount"].sum()

    return {
        "total_income": round(float(income), 2),
        "total_expense": round(float(expense), 2),
        "balance": round(float(income - expense), 2),
        "transaction_count": int(len(df)),
        "avg_transaction": round(float(df["amount"].mean()), 2),
    }


def get_by_category(db: Session, owner_id: int, days: Optional[int] = None) -> list:
    df = _load_dataframe(db, owner_id, days)
    if df.empty:
        return []

    grouped = (
        df.groupby(["category", "type"])["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    return grouped.to_dict(orient="records")


def get_timeseries(db: Session, owner_id: int, days: int = 30) -> list:
    df = _load_dataframe(db, owner_id, days)
    if df.empty:
        return []

    df["day"] = df["date"].dt.date
    daily = (
        df.groupby(["day", "type"])["amount"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )

    for col in ("income", "expense"):
        if col not in daily.columns:
            daily[col] = 0.0

    daily["balance"] = daily["income"] - daily["expense"]
    daily["day"] = daily["day"].astype(str)

    return daily.to_dict(orient="records")


def get_top_expenses(db: Session, owner_id: int, limit: int = 5) -> list:
    df = _load_dataframe(db, owner_id)
    if df.empty:
        return []

    top = (
        df[df["type"] == "expense"]
        .nlargest(limit, "amount")[["description", "amount", "category", "date"]]
    )
    top["date"] = top["date"].astype(str)
    return top.to_dict(orient="records")
