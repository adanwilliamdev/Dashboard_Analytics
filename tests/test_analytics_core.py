"""Testes do nucleo de analise (nao precisam de FastAPI nem banco)."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app import analytics_core as core

TODAY = datetime(2026, 10, 15, 12, 0)


def make_df(rows):
    return pd.DataFrame(
        [
            {"id": i, "description": d, "amount": a, "category": c, "type": t, "date": dt}
            for i, (d, a, c, t, dt) in enumerate(rows, start=1)
        ]
    )


@pytest.fixture()
def basic():
    return make_df(
        [
            ("Salario", 5000, "salario", "income", TODAY - timedelta(days=5)),
            ("Aluguel", 1500, "moradia", "expense", TODAY - timedelta(days=4)),
            ("Mercado", 300, "alimentacao", "expense", TODAY - timedelta(days=2)),
            ("Cinema", 60, "lazer", "expense", TODAY - timedelta(days=2)),
        ]
    )


def test_summarize(basic):
    s = core.summarize(basic, days=30)
    assert s["total_income"] == 5000
    assert s["total_expense"] == 1860
    assert s["balance"] == 3140
    assert s["transaction_count"] == 4
    assert s["savings_rate"] == 62.8
    assert s["largest_expense"] == 1500
    assert s["avg_daily_expense"] == 62.0


def test_summarize_empty():
    s = core.summarize(pd.DataFrame(columns=core.COLUMNS), days=30)
    assert s["total_income"] == 0 and s["savings_rate"] is None and s["transaction_count"] == 0


def test_pct_change():
    assert core.pct_change(150, 100) == 50.0
    assert core.pct_change(50, 100) == -50.0
    assert core.pct_change(10, 0) is None


def test_comparison(basic):
    prev = make_df([("Aluguel", 1000, "moradia", "expense", TODAY - timedelta(days=40))])
    s = core.summary_with_comparison(basic, prev, 30)
    assert s["comparison"]["change_pct"]["expense"] == 86.0
    assert s["comparison"]["change_pct"]["income"] is None


def test_by_category_share(basic):
    cats = core.by_category(basic)
    exp = [c for c in cats if c["type"] == "expense"]
    assert exp[0]["category"] == "moradia"
    assert sum(c["share_pct"] for c in exp) == pytest.approx(100, abs=0.2)


def test_timeseries_fills_gaps(basic):
    start = TODAY - timedelta(days=9)
    ts = core.timeseries(basic, start=start, end=TODAY)
    assert len(ts) == 10  # 10 dias corridos, sem buracos
    days = [r["day"] for r in ts]
    assert days == sorted(days) and len(set(days)) == len(days)
    assert ts[-1]["cumulative_balance"] == pytest.approx(5000 - 1860)
    assert ts[0]["expense"] == 0


def test_timeseries_empty():
    assert core.timeseries(pd.DataFrame(columns=core.COLUMNS)) == []


def test_monthly_and_mom():
    df = make_df(
        [
            ("a", 100, "x", "expense", datetime(2026, 8, 3)),
            ("b", 150, "x", "expense", datetime(2026, 9, 3)),
            ("c", 1000, "s", "income", datetime(2026, 9, 5)),
        ]
    )
    m = core.monthly(df)
    assert [r["month"] for r in m] == ["2026-08", "2026-09"]
    assert m[1]["expense_change_pct"] == 50.0
    assert m[0]["savings_rate"] is None  # sem receita em agosto
    assert m[1]["savings_rate"] == 85.0


def test_weekday_profile_has_seven_rows(basic):
    wd = core.weekday_profile(basic)
    assert len(wd) == 7 and sum(w["count"] for w in wd) == 3


def test_top_expenses(basic):
    top = core.top_expenses(basic, 2)
    assert [t["description"] for t in top] == ["Aluguel", "Mercado"]


def test_forecast_unavailable_with_little_data(basic):
    assert core.forecast(basic, today=TODAY)["available"] is False


def test_forecast_constant_spend():
    rows = [("Dia", 50, "x", "expense", TODAY - timedelta(days=i)) for i in range(60)]
    f = core.forecast(make_df(rows), horizon=30, today=TODAY)
    assert f["available"] and len(f["daily"]) == 30
    assert f["projected_expense"] == pytest.approx(50 * 30, rel=0.05)
    assert f["projected_expense_lower"] <= f["projected_expense"] <= f["projected_expense_upper"]


def test_forecast_follows_trend_upwards_but_is_bounded():
    rows = [("Dia", 20 + i, "x", "expense", TODAY - timedelta(days=60 - i)) for i in range(60)]
    f = core.forecast(make_df(rows), horizon=30, today=TODAY)
    assert f["trend_per_day"] > 0
    assert f["projected_expense"] > f["daily_baseline"] * 30  # sobe
    assert f["projected_expense"] < f["daily_baseline"] * 30 * 1.5  # mas amortecido


def test_anomalies_flags_outlier_only():
    rows = [("Mercado", 100 + (i % 5), "alimentacao", "expense", TODAY - timedelta(days=i)) for i in range(10)]
    rows.append(("Jantar caro", 2000, "alimentacao", "expense", TODAY - timedelta(days=1)))
    out = core.detect_anomalies(make_df(rows))
    assert len(out) == 1 and out[0]["description"] == "Jantar caro"
    assert out[0]["times_expected"] > 10


def test_fixed_bill_in_mixed_category_is_not_anomalous():
    rows = [("Plano de saude", 320 + (i % 3), "saude", "expense", TODAY - timedelta(days=30 * i)) for i in range(6)]
    rows += [("Farmacia", 20 + 5 * (i % 4), "saude", "expense", TODAY - timedelta(days=7 * i)) for i in range(8)]
    assert core.detect_anomalies(make_df(rows)) == []


def test_small_variation_is_not_flagged_even_with_tiny_mad():
    rows = [("Padaria", 50.0, "alimentacao", "expense", TODAY - timedelta(days=i)) for i in range(9)]
    rows.append(("Padaria", 58.0, "alimentacao", "expense", TODAY))  # +16%: ruido, nao anomalia
    assert core.detect_anomalies(make_df(rows)) == []


def test_anomalies_identical_values_no_crash():
    rows = [("Streaming", 40, "lazer", "expense", TODAY - timedelta(days=30 * i)) for i in range(6)]
    assert core.detect_anomalies(make_df(rows)) == []


def test_irregular_purchases_are_not_recurring():
    gaps = [0, 25, 51, 76, 102]  # intervalo ~25, mas valores muito diferentes
    amounts = [15, 120, 30, 95, 18]
    rows = [("Farmacia", a, "saude", "expense", TODAY - timedelta(days=g)) for g, a in zip(gaps, amounts)]
    assert core.detect_recurring(make_df(rows)) == []


def test_recurring_detection():
    rows = [("Netflix", 39.9, "lazer", "expense", TODAY - timedelta(days=30 * i)) for i in range(4)]
    rows += [("Mercado", 100, "alimentacao", "expense", TODAY - timedelta(days=i)) for i in range(6)]
    rec = core.detect_recurring(make_df(rows))
    assert [r["description"] for r in rec] == ["Netflix"]
    assert rec[0]["every_days"] == 30


def test_budget_status_levels():
    df = make_df(
        [
            ("a", 90, "lazer", "expense", datetime(2026, 10, 3)),
            ("b", 250, "alimentacao", "expense", datetime(2026, 10, 4)),
            ("c", 999, "lazer", "expense", datetime(2026, 9, 4)),  # outro mes: ignorado
        ]
    )
    st = core.budget_status(df, {"lazer": 100, "alimentacao": 200, "saude": 50}, today=datetime(2026, 10, 15))
    by = {r["category"]: r for r in st}
    assert by["lazer"]["status"] == "warning" and by["lazer"]["spent"] == 90
    assert by["alimentacao"]["status"] == "exceeded" and by["alimentacao"]["remaining"] == -50
    assert by["saude"]["status"] == "ok" and by["saude"]["spent"] == 0
    assert by["lazer"]["projected_exceeds"] is True  # 90/15*31 > 100


def test_insights_cover_main_cases(basic):
    prev = make_df([("Aluguel", 500, "moradia", "expense", TODAY - timedelta(days=40))])
    s = core.summary_with_comparison(basic, prev, 30)
    msgs = core.build_insights(s, core.by_category(basic), core.weekday_profile(basic), [], [], 30)
    text = " ".join(m["message"] for m in msgs)
    assert "subiram" in text and "moradia" in text
    assert all(m["level"] in {"info", "warning", "success"} for m in msgs)


def test_outputs_are_json_safe(basic):
    import json

    payload = {
        "summary": core.summarize(basic, 30),
        "cats": core.by_category(basic),
        "ts": core.timeseries(basic, start=TODAY - timedelta(days=9), end=TODAY),
        "monthly": core.monthly(basic),
        "wd": core.weekday_profile(basic),
    }
    json.dumps(payload, allow_nan=False)  # falha se houver NaN/numpy
    assert not np.isnan(payload["summary"]["total_income"])


def test_all_complex_outputs_are_json_safe():
    import json

    rows = [("Dia", 50 + (i % 7) * 3, "x", "expense", TODAY - timedelta(days=i)) for i in range(70)]
    rows += [("Salario", 4000, "salario", "income", TODAY - timedelta(days=30 * i)) for i in range(3)]
    rows += [("Compra", 3000, "x", "expense", TODAY - timedelta(days=3))]
    df = make_df(rows)
    payload = {
        "forecast": core.forecast(df, today=TODAY),
        "anomalies": core.detect_anomalies(df),
        "recurring": core.detect_recurring(df),
        "budgets": core.budget_status(df, {"x": 1000.0}, today=TODAY),
        "monthly": core.monthly(df),
    }
    json.dumps(payload, allow_nan=False)
    assert payload["forecast"]["available"] and payload["anomalies"]
