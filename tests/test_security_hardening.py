"""Correcoes de seguranca/robustez: admin, username, senha, tokens, fuso, rate limit, cache, logs, CLI."""
import logging
from datetime import timedelta

import bcrypt
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app import analytics, cli, models
from app import auth as auth_module
from app.cache import build_cache
from app.config import Settings, settings
from app.database import SessionLocal
from app.security import LoginRateLimiter, RedisLoginRateLimiter
from app.utils import local_now, utcnow
from tests.conftest import register_and_login
from tests.test_transactions import add


def _register(client, username, password="secret123"):
    return client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )


def _bearer(client, username, password="secret123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


# ---------------------------------------------------------------- admin
def test_register_never_grants_admin_even_for_reserved_names(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "fulano,chefe")  # variavel descontinuada: ignorada
    for name in ("chefe", "fulano", "admin", "root"):
        h = register_and_login(client, name)
        assert client.get("/auth/me", headers=h).json()["role"] == "user"
        assert client.get("/admin/users", headers=h).status_code == 403


def test_cli_create_admin_and_promote(client):
    with SessionLocal() as db:
        u = cli.create_admin(db, "Chefe", "chefe@example.com", "secret123")
        assert u.role == "admin" and u.username == "chefe"
        with pytest.raises(cli.CliError):
            cli.create_admin(db, "CHEFE", "outro@example.com", "secret123")  # duplicado (sem caixa)
        with pytest.raises(cli.CliError):
            cli.create_admin(db, "novo", "novo@example.com", "123")  # mesmas regras do cadastro
        with pytest.raises(cli.CliError):
            cli.promote(db, "inexistente")

    assert client.get("/admin/users", headers=_bearer(client, "chefe")).status_code == 200

    comum = register_and_login(client, "comum")
    assert client.get("/admin/users", headers=comum).status_code == 403
    with SessionLocal() as db:
        cli.promote(db, "COMUM")
    assert client.get("/admin/users", headers=comum).status_code == 200


def test_cli_main_reads_password_from_env(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    assert cli.main(["create-admin", "viaenv", "viaenv@example.com"]) == 0
    assert cli.main(["create-admin", "viaenv", "viaenv@example.com"]) == 1  # ja existe
    assert client.get("/admin/users", headers=_bearer(client, "viaenv")).status_code == 200


# ------------------------------------------------------------- username
def test_username_is_case_insensitive(client):
    r = _register(client, "Ana")
    assert r.status_code == 201 and r.json()["username"] == "ana"
    assert client.post("/auth/login", data={"username": "ANA", "password": "secret123"}).status_code == 200
    assert _register(client, "aNa").status_code == 400


def test_legacy_mixed_case_account_still_works_and_is_protected(client):
    with SessionLocal() as db:
        db.add(
            models.User(
                username="Legado", email="legado@example.com", hashed_password=auth_module.hash_password("secret123")
            )
        )
        db.commit()
    for name in ("Legado", "legado"):
        h = _bearer(client, name)
        assert client.get("/auth/me", headers=h).status_code == 200
    assert _register(client, "LEGADO").status_code == 400


def test_database_enforces_case_insensitive_unique_username(client):
    with SessionLocal() as db:
        db.add(models.User(username="Dup", email="a@example.com", hashed_password="x"))
        db.commit()
        db.add(models.User(username="dup", email="b@example.com", hashed_password="x"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------- senha
def test_password_limit_is_72_bytes_not_characters(client):
    assert _register(client, "ok72", "a" * 72).status_code == 201
    assert _register(client, "acentos36", "é" * 36).status_code == 201  # 72 bytes
    r = _register(client, "acentos37", "é" * 37)  # 37 caracteres, mas 74 bytes
    assert r.status_code == 422 and "72 bytes" in r.text
    assert _register(client, "longa", "a" * 73).status_code == 422


def test_change_password_also_rejects_over_72_bytes(client):
    h = register_and_login(client, "trocasenha")
    r = client.post(
        "/auth/change-password", headers=h, json={"current_password": "secret123", "new_password": "é" * 37}
    )
    assert r.status_code == 422


def test_hash_rejects_long_password_but_verify_keeps_legacy_hashes_working():
    long_pw = "x" * 72 + "CAUDA"
    with pytest.raises(ValueError):
        auth_module.hash_password(long_pw)
    # conta antiga: o hash foi gerado so com os 72 primeiros bytes
    legacy = bcrypt.hashpw(b"x" * 72, bcrypt.gensalt()).decode()
    assert auth_module.verify_password(long_pw, legacy)
    assert not auth_module.verify_password("outra", legacy)
    assert not auth_module.verify_password("qualquer", "isto-nao-e-um-hash")
    assert auth_module.verify_password("secret123", auth_module.hash_password("secret123"))


# --------------------------------------------------------------- tokens
def test_change_password_revokes_previous_tokens(client):
    old = register_and_login(client, "rev")
    assert client.get("/auth/me", headers=old).status_code == 200
    r = client.post(
        "/auth/change-password", headers=old, json={"current_password": "secret123", "new_password": "novasenha1"}
    )
    assert r.status_code == 204
    assert client.get("/auth/me", headers=old).status_code == 401  # token antigo derrubado
    assert client.get("/auth/me", headers=_bearer(client, "rev", "novasenha1")).status_code == 200


def test_token_without_version_claim_is_valid_until_password_change(client):
    register_and_login(client, "semtv")
    h = {"Authorization": "Bearer " + auth_module.create_access_token({"sub": "semtv"})}  # token emitido antes da 0003
    assert client.get("/auth/me", headers=h).status_code == 200
    client.post(
        "/auth/change-password",
        headers=_bearer(client, "semtv"),
        json={"current_password": "secret123", "new_password": "novasenha1"},
    )
    assert client.get("/auth/me", headers=h).status_code == 401


# ------------------------------------------------------------------ fuso
def test_aware_dates_are_stored_in_app_timezone(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "APP_TIMEZONE", "America/Sao_Paulo")
    r = client.post(
        "/transactions/",
        headers=auth,
        json={"description": "tz", "amount": 1, "date": "2026-10-09T10:00:00-03:00"},
    )
    assert r.status_code == 201 and r.json()["date"].startswith("2026-10-09T10:00")


def test_date_filters_with_offset_use_app_timezone(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "APP_TIMEZONE", "America/Sao_Paulo")
    from datetime import datetime

    add(client, auth, "antes", 1, date=datetime(2026, 10, 8, 23, 30))
    add(client, auth, "depois", 1, date=datetime(2026, 10, 9, 0, 30))
    # meia-noite de Sao Paulo: 00:00-03:00 == 00:00 no horario de parede da aplicacao
    r = client.get("/transactions/", headers=auth, params={"start_date": "2026-10-09T00:00:00-03:00"})
    assert [t["description"] for t in r.json()] == ["depois"]
    r = client.get("/transactions/", headers=auth, params={"end_date": "2026-10-09T00:00:00-03:00"})
    assert [t["description"] for t in r.json()] == ["antes"]


def test_local_now_and_analytics_today_follow_app_timezone(monkeypatch):
    monkeypatch.setattr(settings, "APP_TIMEZONE", "Pacific/Kiritimati")  # UTC+14
    diff = local_now() - utcnow()
    assert timedelta(hours=13, minutes=55) < diff < timedelta(hours=14, minutes=5)
    today = analytics._today()
    assert today.tzinfo is None
    assert 0 <= (local_now() - today.to_pydatetime()).total_seconds() < 86400 + 5


def test_default_transaction_date_uses_app_timezone(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "APP_TIMEZONE", "Pacific/Kiritimati")
    tx = add(client, auth, "sem data")
    from datetime import datetime

    created = datetime.fromisoformat(tx["date"])
    assert abs((created - local_now()).total_seconds()) < 60


def test_invalid_timezone_is_rejected_at_startup():
    with pytest.raises(ValueError):
        Settings(APP_TIMEZONE="Marte/Base", _env_file=None)


# ----------------------------------------------------------- rate limit
class FakeRedis:
    def __init__(self):
        self.data, self.ttls = {}, {}

    def get(self, k):
        v = self.data.get(k)
        return None if v is None else str(v).encode()

    def incr(self, k):
        self.data[k] = int(self.data.get(k, 0)) + 1
        return self.data[k]

    def ttl(self, k):
        return self.ttls.get(k, -1) if k in self.data else -2

    def expire(self, k, seconds):
        self.ttls[k] = seconds
        return True

    def delete(self, k):
        self.data.pop(k, None)
        self.ttls.pop(k, None)

    def scan_iter(self, pattern):
        return [k for k in list(self.data) if k.startswith(pattern.rstrip("*"))]


class BrokenRedis:
    def __getattr__(self, name):
        def boom(*a, **k):
            raise ConnectionError("redis fora do ar")

        return boom


def test_redis_limiter_is_shared_between_workers():
    shared = FakeRedis()
    worker_a = RedisLoginRateLimiter(3, 300, client=shared)
    worker_b = RedisLoginRateLimiter(3, 300, client=shared)  # outro processo, mesmo Redis
    for _ in range(3):
        worker_a.record_failure("1.2.3.4|ana")
    assert shared.ttls["loginfail:1.2.3.4|ana"] == 300  # a janela expira sozinha
    with pytest.raises(HTTPException) as exc:
        worker_b.check("1.2.3.4|ana")
    assert exc.value.status_code == 429 and "Retry-After" in exc.value.headers
    worker_b.check("1.2.3.4|outro")  # outra chave segue livre

    worker_b.reset("1.2.3.4|ana")
    worker_a.check("1.2.3.4|ana")


def test_redis_limiter_reset_all_and_ttl_repair():
    fake = FakeRedis()
    lim = RedisLoginRateLimiter(2, 60, client=fake)
    fake.data["loginfail:k"] = 1  # chave sem TTL (um expire anterior falhou)
    lim.record_failure("k")
    assert fake.ttls["loginfail:k"] == 60
    lim.reset_all()
    assert fake.data == {}


def test_redis_limiter_falls_back_to_local_counter_when_redis_is_down():
    lim = RedisLoginRateLimiter(3, 300, client=BrokenRedis())
    for _ in range(2):
        lim.record_failure("k")
        lim.check("k")  # abaixo do limite: nao bloqueia
    lim.record_failure("k")
    with pytest.raises(HTTPException) as exc:
        lim.check("k")  # login continua protegido mesmo sem Redis
    assert exc.value.status_code == 429
    lim.reset("k")
    lim.check("k")


def test_memory_limiter_still_works():
    lim = LoginRateLimiter(2, 300)
    lim.record_failure("k")
    lim.record_failure("k")
    with pytest.raises(HTTPException):
        lim.check("k")


# ----------------------------------------------------------------- cache
def test_memory_cache_is_disabled_when_running_multiple_workers_without_redis(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "")
    monkeypatch.setattr(settings, "CACHE_TTL_SECONDS", 30)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    assert build_cache().enabled is False  # evita dado velho entre workers
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    assert build_cache().enabled is True
    monkeypatch.setenv("WEB_CONCURRENCY", "lixo")
    assert build_cache().enabled is True


# ------------------------------------------------------------------ logs
def test_application_loggers_are_configured():
    import app.main  # noqa: F401  (configura o logging ao importar)

    assert logging.getLogger("dashboard").handlers
    for name in ("dashboard.access", "dashboard.cache", "dashboard.security"):
        assert logging.getLogger(name).isEnabledFor(logging.INFO)


def test_setup_logging_falls_back_to_info_on_unknown_level():
    from app.logging_config import setup_logging

    setup_logging("nao-existe")
    assert logging.getLogger("dashboard").level == logging.INFO
    setup_logging(settings.LOG_LEVEL)

