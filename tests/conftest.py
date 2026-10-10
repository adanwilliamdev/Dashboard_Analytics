"""Fixtures. O ambiente e configurado ANTES de importar a aplicacao."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = tempfile.mkdtemp(prefix="dash_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + _TMP.replace("\\", "/") + "/test.db"
os.environ["APP_ENV"] = "test"
os.environ["ADMIN_USERNAMES"] = "chefe"
os.environ["SECRET_KEY"] = "test_secret_key_with_more_than_32_characters_ok"

import pytest  # noqa: E402


@pytest.fixture()
def client():
    """TestClient com banco limpo a cada teste (importa FastAPI sob demanda)."""
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app
    from app.cache import get_cache
    from app.security import login_limiter

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_limiter.reset_all()
    get_cache().clear()
    with TestClient(app) as c:
        yield c


def register_and_login(client, username="tester", password="secret123"):
    client.post(
        "/auth/register",
        json={"username": username, "email": username + "@example.com", "password": password},
    )
    r = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture()
def auth(client):
    return register_and_login(client)
