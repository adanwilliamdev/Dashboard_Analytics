from datetime import datetime, timedelta

from tests.test_transactions import add


def seed(client, h):
    now = datetime.utcnow()
    add(client, h, "Salario", 5000, "salario", "income", date=now - timedelta(days=5))
    add(client, h, "Aluguel", 1500, "moradia", date=now - timedelta(days=4))
    add(client, h, "Mercado", 300, "alimentacao", date=now - timedelta(days=2))
    add(client, h, "Velho", 700, "alimentacao", date=now - timedelta(days=45))  # janela anterior (30d)


def test_summary_has_comparison(client, auth):
    seed(client, auth)
    s = client.get("/analytics/summary?days=30", headers=auth).json()
    assert s["total_income"] == 5000 and s["total_expense"] == 1800 and s["balance"] == 3200
    assert s["comparison"]["previous"]["total_expense"] == 700
    assert s["comparison"]["change_pct"]["expense"] == 157.1


def test_summary_empty_user(client, auth):
    s = client.get("/analytics/summary", headers=auth).json()
    assert s["total_income"] == 0 and s["transaction_count"] == 0 and s["savings_rate"] is None


def test_timeseries_has_no_gaps(client, auth):
    seed(client, auth)
    ts = client.get("/analytics/timeseries?days=10", headers=auth).json()
    assert len(ts) == 10
    assert ts[-1]["cumulative_balance"] == 3200


def test_by_category_filter_and_top_expenses(client, auth):
    seed(client, auth)
    cats = client.get("/analytics/by-category?days=30&type=expense", headers=auth).json()
    assert [c["category"] for c in cats] == ["moradia", "alimentacao"]
    top = client.get("/analytics/top-expenses?limit=1&days=30", headers=auth).json()
    assert top[0]["description"] == "Aluguel"


def test_overview_contains_everything(client, auth):
    seed(client, auth)
    o = client.get("/analytics/overview?days=30", headers=auth).json()
    for key in ("summary", "by_category", "timeseries", "weekday", "top_expenses", "monthly",
                "forecast", "anomalies", "recurring", "budgets", "insights"):
        assert key in o
    assert len(o["weekday"]) == 7
    assert "available" in o["forecast"]


def test_monthly_and_forecast_endpoints(client, auth):
    seed(client, auth)
    assert len(client.get("/analytics/monthly?months=3", headers=auth).json()) >= 1
    assert client.get("/analytics/forecast", headers=auth).status_code == 200
    assert client.get("/analytics/anomalies", headers=auth).json() == []
    assert client.get("/analytics/recurring", headers=auth).json() == []


def test_budgets_flow_and_status(client, auth):
    now = datetime.utcnow()
    add(client, auth, "Jantar", 250, "alimentacao", date=now)

    r = client.put("/budgets/Alimentacao", headers=auth, json={"monthly_limit": 200})
    assert r.status_code == 200 and r.json()["category"] == "alimentacao"
    client.put("/budgets/alimentacao", headers=auth, json={"monthly_limit": 200})  # upsert: sem duplicar
    assert len(client.get("/budgets/", headers=auth).json()) == 1

    st = client.get("/analytics/budgets", headers=auth).json()
    assert st[0]["status"] == "exceeded" and st[0]["spent"] == 250

    insights = client.get("/analytics/overview", headers=auth).json()["insights"]
    assert any("estourado" in i["message"] for i in insights)

    assert client.delete("/budgets/alimentacao", headers=auth).status_code == 204
    assert client.delete("/budgets/alimentacao", headers=auth).status_code == 404
    assert client.put("/budgets/x", headers=auth, json={"monthly_limit": 0}).status_code == 422


def test_data_is_isolated_between_users(client, auth):
    from tests.conftest import register_and_login

    seed(client, auth)
    other = register_and_login(client, "outro")
    assert client.get("/analytics/summary", headers=other).json()["transaction_count"] == 0
    assert client.get("/budgets/", headers=other).json() == []
