from tests.conftest import register_and_login


def test_health_and_root(client):
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/").json()["status"] == "ok"


def test_register_login_me(client):
    h = register_and_login(client, "ana")
    r = client.get("/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["username"] == "ana"


def test_duplicate_username_rejected(client):
    register_and_login(client, "dup")
    r = client.post(
        "/auth/register",
        json={"username": "dup", "email": "other@example.com", "password": "secret123"},
    )
    assert r.status_code == 400


def test_weak_password_and_bad_username_rejected(client):
    r = client.post("/auth/register", json={"username": "bob", "email": "b@example.com", "password": "123"})
    assert r.status_code == 422
    r = client.post("/auth/register", json={"username": "b ob!", "email": "b@example.com", "password": "secret123"})
    assert r.status_code == 422


def test_protected_routes_require_token(client):
    for path in ("/transactions/", "/analytics/summary", "/analytics/overview", "/budgets/"):
        assert client.get(path).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer lixo"}).status_code == 401


def test_wrong_password_and_lockout(client):
    register_and_login(client, "carl")
    for _ in range(5):
        r = client.post("/auth/login", data={"username": "carl", "password": "errada123"})
        assert r.status_code == 401
    r = client.post("/auth/login", data={"username": "carl", "password": "secret123"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_change_password(client):
    h = register_and_login(client, "dora")
    bad = client.post("/auth/change-password", headers=h, json={"current_password": "x", "new_password": "novasenha1"})
    assert bad.status_code == 400
    ok = client.post("/auth/change-password", headers=h, json={"current_password": "secret123", "new_password": "novasenha1"})
    assert ok.status_code == 204
    assert client.post("/auth/login", data={"username": "dora", "password": "novasenha1"}).status_code == 200
