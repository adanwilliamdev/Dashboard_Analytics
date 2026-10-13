"""Nucleo de analise (puro): recebe DataFrames e devolve estruturas serializaveis.

Nao depende de banco nem de FastAPI, o que torna tudo facil de testar.
Colunas esperadas: id, description, amount, category, type, date.
"""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.utils import local_now

COLUMNS = ["id", "description", "amount", "category", "type", "date"]
WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]


# ----------------------------------------------------------------- helpers
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Garante tipos corretos (date -> datetime64, amount -> float)."""
    if df is None or df.empty:
        return pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "description": pd.Series(dtype="object"),
                "amount": pd.Series(dtype="float64"),
                "category": pd.Series(dtype="object"),
                "type": pd.Series(dtype="object"),
                "date": pd.Series(dtype="datetime64[ns]"),
            }
        )
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["amount"] = out["amount"].astype(float)
    return out


def _records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """DataFrame -> lista de dicts JSON-safe (NaN vira None)."""
    if df.empty:
        return []
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def pct_change(current: float, previous: float) -> Optional[float]:
    """Variacao percentual; None quando nao ha base de comparacao."""
    if previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _r2(x: float) -> float:
    return round(float(x), 2)


# ----------------------------------------------------------------- resumo
def summarize(df: pd.DataFrame, days: Optional[int] = None) -> Dict[str, Any]:
    df = normalize(df)
    income = float(df.loc[df["type"] == "income", "amount"].sum())
    expense = float(df.loc[df["type"] == "expense", "amount"].sum())
    balance = income - expense
    exp_df = df[df["type"] == "expense"]
    return {
        "total_income": _r2(income),
        "total_expense": _r2(expense),
        "balance": _r2(balance),
        "transaction_count": int(len(df)),
        "avg_transaction": _r2(df["amount"].mean()) if len(df) else 0.0,
        "savings_rate": round(balance / income * 100, 1) if income > 0 else None,
        "avg_daily_expense": _r2(expense / days) if days else None,
        "largest_expense": _r2(exp_df["amount"].max()) if len(exp_df) else 0.0,
    }


def summary_with_comparison(
    current: pd.DataFrame, previous: pd.DataFrame, days: int
) -> Dict[str, Any]:
    cur = summarize(current, days)
    prev = summarize(previous, days)
    cur["comparison"] = {
        "previous": {k: prev[k] for k in ("total_income", "total_expense", "balance", "transaction_count")},
        "change_pct": {
            "income": pct_change(cur["total_income"], prev["total_income"]),
            "expense": pct_change(cur["total_expense"], prev["total_expense"]),
            "balance": pct_change(cur["balance"], prev["balance"]),
            "transactions": pct_change(cur["transaction_count"], prev["transaction_count"]),
        },
    }
    return cur


# ------------------------------------------------------------- categorias
def by_category(df: pd.DataFrame) -> List[Dict[str, Any]]:
    df = normalize(df)
    if df.empty:
        return []
    grouped = (
        df.groupby(["category", "type"])["amount"]
        .agg(amount="sum", count="count")
        .reset_index()
    )
    totals = grouped.groupby("type")["amount"].transform("sum")
    grouped["share_pct"] = (grouped["amount"] / totals * 100).round(1)
    grouped["amount"] = grouped["amount"].round(2)
    grouped["count"] = grouped["count"].astype(int)
    grouped = grouped.sort_values("amount", ascending=False)
    return _records(grouped)


# ----------------------------------------------------------- series temporais
def timeseries(
    df: pd.DataFrame, start: Optional[datetime] = None, end: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Serie diaria SEM buracos (dias sem movimento = 0), com saldo acumulado e media movel."""
    df = normalize(df)
    if df.empty:
        return []

    day = df["date"].dt.normalize()
    start = pd.Timestamp(start).normalize() if start is not None else day.min()
    end = pd.Timestamp(end).normalize() if end is not None else day.max()
    end = max(end, day.max())
    idx = pd.date_range(start, end, freq="D")

    daily = (
        df.assign(day=day)
        .pivot_table(index="day", columns="type", values="amount", aggfunc="sum", fill_value=0.0)
        .reindex(idx, fill_value=0.0)
    )
    for col in ("income", "expense"):
        if col not in daily.columns:
            daily[col] = 0.0

    out = pd.DataFrame(
        {
            "day": idx.strftime("%Y-%m-%d"),
            "income": daily["income"].round(2).to_numpy(),
            "expense": daily["expense"].round(2).to_numpy(),
        }
    )
    out["balance"] = (out["income"] - out["expense"]).round(2)
    out["cumulative_balance"] = out["balance"].cumsum().round(2)
    out["expense_ma7"] = out["expense"].rolling(7, min_periods=1).mean().round(2)
    return _records(out)


def monthly(df: pd.DataFrame, months: int = 12) -> List[Dict[str, Any]]:
    df = normalize(df)
    if df.empty:
        return []
    tmp = df.assign(month=df["date"].dt.to_period("M").astype(str))
    pv = tmp.pivot_table(
        index="month", columns="type", values="amount", aggfunc="sum", fill_value=0.0
    )
    for col in ("income", "expense"):
        if col not in pv.columns:
            pv[col] = 0.0
    pv = pv.sort_index()
    out = pd.DataFrame(
        {
            "month": pv.index.astype(str),
            "income": pv["income"].round(2).to_numpy(),
            "expense": pv["expense"].round(2).to_numpy(),
        }
    )
    out["balance"] = (out["income"] - out["expense"]).round(2)
    out["savings_rate"] = np.where(
        out["income"] > 0, (out["balance"] / out["income"] * 100).round(1), np.nan
    )
    prev_expense = out["expense"].shift(1)
    out["expense_change_pct"] = np.where(
        prev_expense > 0, ((out["expense"] - prev_expense) / prev_expense * 100).round(1), np.nan
    )
    return _records(out.tail(months))


def weekday_profile(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Gasto total e medio por dia da semana (sempre 7 linhas)."""
    df = normalize(df)
    exp = df[df["type"] == "expense"]
    rows = []
    for i, name in enumerate(WEEKDAYS_PT):
        sub = exp[exp["date"].dt.dayofweek == i]
        rows.append(
            {
                "weekday": name,
                "weekday_index": i,
                "total": _r2(sub["amount"].sum()),
                "avg": _r2(sub["amount"].mean()) if len(sub) else 0.0,
                "count": int(len(sub)),
            }
        )
    return rows


def top_expenses(df: pd.DataFrame, limit: int = 5) -> List[Dict[str, Any]]:
    df = normalize(df)
    exp = df[df["type"] == "expense"]
    if exp.empty:
        return []
    top = exp.nlargest(limit, "amount")[["description", "amount", "category", "date"]].copy()
    top["amount"] = top["amount"].round(2)
    top["date"] = top["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return _records(top)


# ------------------------------------------------------------- previsao
def forecast(
    df: pd.DataFrame, horizon: int = 30, lookback: int = 90, today: Optional[datetime] = None
) -> Dict[str, Any]:
    """Projecao de despesas: nivel (media 30d) + tendencia amortecida + sazonalidade semanal.

    Metodo simples e explicavel (nao e um modelo de ML). A faixa e ~80% (1,28 desvio).
    """
    df = normalize(df)
    exp = df[df["type"] == "expense"]
    if exp.empty:
        return {"available": False, "reason": "Sem despesas registradas."}

    today_ts = pd.Timestamp(today if today is not None else local_now()).normalize()
    first = exp["date"].min().normalize()
    start = max(first, today_ts - pd.Timedelta(days=lookback - 1))
    idx = pd.date_range(start, today_ts, freq="D")
    if len(idx) < 14:
        return {"available": False, "reason": "Sao necessarios ao menos 14 dias de historico."}

    s = (
        exp.assign(day=exp["date"].dt.normalize())
        .groupby("day")["amount"]
        .sum()
        .reindex(idx, fill_value=0.0)
    )

    baseline = float(s.tail(30).mean())
    smooth = s.rolling(7, min_periods=1).mean()
    slope = float(np.polyfit(np.arange(len(smooth)), smooth.to_numpy(), 1)[0])
    limit = 0.02 * baseline
    slope = float(np.clip(slope, -limit, limit)) if baseline > 0 else 0.0

    seasonal = np.ones(7)
    if len(s) >= 56 and s.mean() > 0:
        by_wd = s.groupby(s.index.dayofweek).mean().reindex(range(7)).fillna(s.mean())
        seasonal = 0.5 + 0.5 * (by_wd / s.mean()).to_numpy()  # encolhe para reduzir ruido

    std = float(s.tail(30).std(ddof=0))
    future = pd.date_range(today_ts + pd.Timedelta(days=1), periods=horizon, freq="D")
    rows, total = [], 0.0
    for i, d in enumerate(future, start=1):
        value = max(0.0, baseline + slope * i * 0.5) * float(seasonal[d.dayofweek])
        total += value
        rows.append(
            {
                "day": d.strftime("%Y-%m-%d"),
                "expense": _r2(value),
                "lower": _r2(max(0.0, value - 1.28 * std)),
                "upper": _r2(value + 1.28 * std),
            }
        )

    band = 1.28 * std * float(np.sqrt(horizon))
    inc = df[df["type"] == "income"]
    income_total = 0.0
    if not inc.empty:
        inc_start = max(inc["date"].min().normalize(), today_ts - pd.Timedelta(days=lookback - 1))
        span = max((today_ts - inc_start).days + 1, 1)
        income_total = float(inc[inc["date"] >= inc_start]["amount"].sum()) / span * horizon

    return {
        "available": True,
        "method": "media 30d + tendencia amortecida + sazonalidade semanal",
        "horizon_days": horizon,
        "history_days": int(len(s)),
        "daily_baseline": _r2(baseline),
        "trend_per_day": round(slope, 3),
        "projected_expense": _r2(total),
        "projected_expense_lower": _r2(max(0.0, total - band)),
        "projected_expense_upper": _r2(total + band),
        "projected_income": _r2(income_total),
        "projected_balance": _r2(income_total - total),
        "daily": rows,
    }


# ------------------------------------------------------------- anomalias
def _robust_stats(x: np.ndarray):
    """(mediana, escala robusta). Escala = MAD; se MAD=0 usa 1,2533 * desvio medio absoluto."""
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    if mad > 0:
        return med, mad / 0.6745
    mean_ad = float(np.mean(np.abs(x - med)))
    return med, (1.253314 * mean_ad if mean_ad > 0 else 0.0)


def detect_anomalies(
    df: pd.DataFrame,
    threshold: float = 3.5,
    min_samples: int = 5,
    min_ratio: float = 1.5,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Despesas fora do padrao (z-score modificado, Iglewicz-Hoaglin).

    - Descricoes frequentes (>= min_samples) sao comparadas com o proprio historico
      (assim uma conta fixa de R$ 320 nao e "anomala" so por estar numa categoria com itens de R$ 20).
    - Descricoes raras sao comparadas com a categoria inteira.
    - So sinaliza valores >= min_ratio x o tipico (evita ruido quando a variacao e minima).
    """
    df = normalize(df)
    exp = df[df["type"] == "expense"].copy()
    if exp.empty:
        return []
    exp["_d"] = exp["description"].str.strip().str.lower()
    counts = exp.groupby(["category", "_d"])["amount"].transform("count")

    found: List[Dict[str, Any]] = []

    def evaluate(rows: pd.DataFrame, reference: pd.DataFrame, label: str) -> None:
        med, scale = _robust_stats(reference["amount"].to_numpy())
        if scale == 0 or med <= 0:
            return
        for _, row in rows.iterrows():
            score = (float(row["amount"]) - med) / scale
            if score >= threshold and row["amount"] >= med * min_ratio:
                found.append(
                    {
                        "description": row["description"],
                        "category": row["category"],
                        "amount": _r2(row["amount"]),
                        "date": row["date"].strftime("%Y-%m-%d"),
                        "expected": _r2(med),
                        "times_expected": round(float(row["amount"]) / med, 1),
                        "score": round(float(score), 1),
                        "compared_with": label,
                    }
                )

    frequent = exp[counts >= min_samples]
    for _, g in frequent.groupby(["category", "_d"]):
        evaluate(g, g, "historico da propria descricao")

    rare = exp[counts < min_samples]
    for cat, g in rare.groupby("category"):
        reference = exp[exp["category"] == cat]
        if len(reference) >= min_samples:
            evaluate(g, reference, "categoria")

    found.sort(key=lambda r: r["score"], reverse=True)
    return found[:limit]


# ------------------------------------------------------------ recorrentes
def detect_recurring(df: pd.DataFrame, min_occurrences: int = 3) -> List[Dict[str, Any]]:
    """Itens ~mensais: intervalo de 25 a 35 dias, regular (desvio <= 4,5 dias) e valor estavel (CV <= 30%)."""
    df = normalize(df)
    if df.empty:
        return []
    key = df["description"].str.strip().str.lower()
    out = []
    for (_, tx_type), g in df.assign(_k=key).groupby(["_k", "type"]):
        if len(g) < min_occurrences:
            continue
        dates = g["date"].sort_values()
        gaps = dates.diff().dt.days.dropna()
        if gaps.empty:
            continue
        med_gap = float(gaps.median())
        mean_amount = float(g["amount"].mean())
        cv = float(g["amount"].std(ddof=0)) / mean_amount if mean_amount > 0 else 1.0
        if not 25 <= med_gap <= 35 or float(gaps.std(ddof=0)) > 4.5 or cv > 0.30:
            continue
        last = dates.iloc[-1]
        out.append(
            {
                "description": g["description"].iloc[-1],
                "type": tx_type,
                "category": g["category"].iloc[-1],
                "avg_amount": _r2(mean_amount),
                "occurrences": int(len(g)),
                "every_days": round(med_gap),
                "last_date": last.strftime("%Y-%m-%d"),
                "next_expected": (last + pd.Timedelta(days=round(med_gap))).strftime("%Y-%m-%d"),
            }
        )
    out.sort(key=lambda r: r["avg_amount"], reverse=True)
    return out


# ------------------------------------------------------------- orcamentos
def budget_status(
    df: pd.DataFrame, budgets: Dict[str, float], today: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Gasto do mes corrente versus limite de cada categoria."""
    df = normalize(df)
    now = pd.Timestamp(today if today is not None else local_now())
    month_df = df[
        (df["type"] == "expense")
        & (df["date"].dt.year == now.year)
        & (df["date"].dt.month == now.month)
    ]
    spent_by_cat = month_df.groupby("category")["amount"].sum().to_dict()
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    elapsed = max(now.day, 1)

    rows = []
    for category, limit in sorted(budgets.items()):
        spent = float(spent_by_cat.get(category, 0.0))
        pct = spent / limit * 100 if limit > 0 else 0.0
        projected = spent / elapsed * days_in_month
        if pct > 100:
            status = "exceeded"
        elif pct >= 80:
            status = "warning"
        else:
            status = "ok"
        rows.append(
            {
                "category": category,
                "monthly_limit": _r2(limit),
                "spent": _r2(spent),
                "remaining": _r2(limit - spent),
                "pct_used": round(pct, 1),
                "projected_month_end": _r2(projected),
                "projected_exceeds": bool(projected > limit),
                "status": status,
            }
        )
    rows.sort(key=lambda r: r["pct_used"], reverse=True)
    return rows


# --------------------------------------------------------------- insights
def build_insights(
    summary: Dict[str, Any],
    categories: List[Dict[str, Any]],
    weekday: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    budgets: List[Dict[str, Any]],
    days: int,
) -> List[Dict[str, str]]:
    """Frases prontas (pt-BR) com nivel: info | warning | success."""
    msgs: List[Dict[str, str]] = []

    change = (summary.get("comparison") or {}).get("change_pct", {})
    exp_change = change.get("expense")
    if exp_change is not None and abs(exp_change) >= 10:
        if exp_change > 0:
            msgs.append(
                {"level": "warning",
                 "message": f"As despesas subiram {exp_change:.0f}% em relação aos {days} dias anteriores."}
            )
        else:
            msgs.append(
                {"level": "success",
                 "message": f"As despesas caíram {abs(exp_change):.0f}% em relação aos {days} dias anteriores."}
            )

    rate = summary.get("savings_rate")
    if rate is not None:
        if rate < 0:
            msgs.append({"level": "warning", "message": "Você gastou mais do que recebeu no período."})
        elif rate < 10:
            msgs.append(
                {"level": "warning",
                 "message": f"Taxa de poupança de {rate:.0f}%: abaixo da referência de 10% a 20%."}
            )
        elif rate >= 20:
            msgs.append({"level": "success", "message": f"Ótima taxa de poupança: {rate:.0f}% da receita."})

    expense_cats = [c for c in categories if c["type"] == "expense"]
    if expense_cats:
        top = expense_cats[0]
        msgs.append(
            {"level": "info",
             "message": f"Maior categoria de gasto: {top['category']} ({top['share_pct']:.0f}% das despesas)."}
        )

    wd = [w for w in weekday if w["total"] > 0]
    if wd:
        peak = max(wd, key=lambda w: w["total"])
        msgs.append({"level": "info", "message": f"O dia da semana com mais gastos é {peak['weekday']}."})

    for b in budgets:
        if b["status"] == "exceeded":
            msgs.append(
                {"level": "warning",
                 "message": f"Orçamento de {b['category']} estourado ({b['pct_used']:.0f}% do limite)."}
            )
        elif b["projected_exceeds"] and b["status"] != "exceeded":
            msgs.append(
                {"level": "warning",
                 "message": f"No ritmo atual, {b['category']} deve ultrapassar o limite até o fim do mês."}
            )

    if anomalies:
        a = anomalies[0]
        msgs.append(
            {"level": "warning",
             "message": f"{len(anomalies)} gasto(s) atípico(s) detectado(s). Maior desvio: "
                        f"{a['description']} (R$ {a['amount']:.2f} em {a['category']})."}
        )
    return msgs
