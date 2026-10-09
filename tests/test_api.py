"""Testes basicos da API."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite:///./test_dashboard.db"

from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _register_and_login(username="tester"):
    client.post(
        "/auth/register",
        json={"username": username, "email": username + "@x.com", "password": "secret123"},
    )
    r = client.post("/auth/login", data={"username": username, "password": "secret123"})
    return r.json()["access_token"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_register_and_login():
    token = _register_and_login("user_a")
    assert token


def test_create_and_list_transaction():
    token = _register_and_login("user_b")
    headers = {"Authorization": "Bearer " + token}

    r = client.post(
        "/transactions/",
        headers=headers,
        json={
            "description": "Cafe",
            "amount": 9.5,
            "category": "alimentacao",
            "type": "expense",
        },
    )
    assert r.status_code == 201

    r = client.get("/transactions/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_analytics_endpoints():
    token = _register_and_login("user_c")
    headers = {"Authorization": "Bearer " + token}

    client.post(
        "/transactions/",
        headers=headers,
        json={"description": "Salario", "amount": 5000, "category": "salario", "type": "income"},
    )
    client.post(
        "/transactions/",
        headers=headers,
        json={"description": "Aluguel", "amount": 1500, "category": "moradia", "type": "expense"},
    )

    s = client.get("/analytics/summary?days=30", headers=headers).json()
    assert s["total_income"] == 5000
    assert s["total_expense"] == 1500
    assert s["balance"] == 3500

    assert client.get("/analytics/by-category", headers=headers).status_code == 200
    assert client.get("/analytics/timeseries?days=30", headers=headers).status_code == 200
    assert client.get("/analytics/top-expenses", headers=headers).status_code == 200
