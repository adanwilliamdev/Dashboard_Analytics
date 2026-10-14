"""Edicao, importacao sem duplicar + OFX, categorias, contas, metas, recorrentes, alertas e LGPD."""
import re
from datetime import datetime, timedelta

from app import alerts, mailer
from app.config import settings
from tests.conftest import register_admin, register_and_login
from tests.test_transactions import add


def _today():
    return datetime.utcnow().date()  # APP_TIMEZONE=UTC nos testes


def _csv(client, headers, text, name="t.csv", params=None):
    return client.post(
        "/transactions/import", headers=headers, params=params or {},
        files={"file": (name, text.encode(), "text/csv")},
    )


# ---------------------------------------------------------------- importacao
CSV = (
    "descricao;valor;categoria;tipo;data\n"
    "Mercado;150,50;alimentacao;despesa;09/10/2026\n"
    "Salario;5.000,00;salario;receita;05/10/2026\n"
    "Cafe;5,00;alimentacao;despesa;09/10/2026\n"
    "Cafe;5,00;alimentacao;despesa;09/10/2026\n"
)


def test_reimport_skips_duplicates_but_keeps_repeats_inside_the_file(client, auth):
    first = _csv(client, auth, CSV).json()
    assert first["imported"] == 4 and first["duplicates"] == 0  # dois cafes iguais no mesmo arquivo valem

    again = _csv(client, auth, CSV).json()
    assert again["imported"] == 0 and again["duplicates"] == 4
    assert client.get("/transactions/", headers=auth).headers["X-Total-Count"] == "4"

    forced = _csv(client, auth, CSV, params={"skip_duplicates": "false"}).json()
    assert forced["imported"] == 4 and forced["duplicates"] == 0
    assert client.get("/transactions/", headers=auth).headers["X-Total-Count"] == "8"


def test_import_also_dedups_against_manual_transactions_and_other_users_are_independent(client, auth):
    add(client, auth, "MERCADO", 150.5, "outros", date=datetime(2026, 10, 9, 18, 45))
    res = _csv(client, auth, CSV).json()
    assert res["duplicates"] == 1 and res["imported"] == 3

    other = register_and_login(client, "outro")
    assert _csv(client, other, CSV).json()["imported"] == 4  # dedup e por usuario


OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261009120000[-3:BRT]<TRNAMT>-150.50<FITID>1<MEMO>MERCADO CENTRAL</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261005<TRNAMT>5000.00<FITID>2<NAME>SALARIO<MEMO>EMPRESA X</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_import_ofx_and_reimport_is_deduplicated(client, auth):
    acc = client.post("/accounts/", headers=auth, json={"name": "Itau", "initial_balance": 100}).json()
    files = {"file": ("extrato.ofx", OFX.encode(), "application/x-ofx")}
    r = client.post("/transactions/import", headers=auth, params={"account_id": acc["id"]}, files=files)
    assert r.status_code == 200 and r.json()["imported"] == 2

    rows = {t["description"]: t for t in client.get("/transactions/", headers=auth).json()}
    assert rows["MERCADO CENTRAL"]["type"] == "expense" and rows["MERCADO CENTRAL"]["amount"] == 150.5
    assert rows["SALARIO - EMPRESA X"]["type"] == "income"
    assert rows["MERCADO CENTRAL"]["account_id"] == acc["id"]

    again = client.post(
        "/transactions/import", headers=auth, files={"file": ("extrato.ofx", OFX.encode(), "application/x-ofx")}
    ).json()
    assert again["imported"] == 0 and again["duplicates"] == 2

    balance = client.get("/accounts/", headers=auth).json()[0]["balance"]
    assert balance == 100 + 5000 - 150.5


def test_import_rejects_foreign_account(client, auth):
    other = register_and_login(client, "outro")
    acc = client.post("/accounts/", headers=other, json={"name": "Dele"}).json()
    r = _csv(client, auth, CSV, params={"account_id": acc["id"]})
    assert r.status_code == 422


# ---------------------------------------------------------------- edicao
def test_edit_transaction_fields_and_unlink_account(client, auth):
    acc = client.post("/accounts/", headers=auth, json={"name": "Carteira", "type": "cash"}).json()
    tx = client.post(
        "/transactions/", headers=auth,
        json={"description": "Padaria", "amount": 12, "category": "alimentacao", "account_id": acc["id"]},
    ).json()
    assert tx["account_id"] == acc["id"]

    r = client.put(
        f"/transactions/{tx['id']}", headers=auth,
        json={"description": "Padaria Nova", "amount": 15.5, "type": "income", "date": "2026-10-01T00:00:00"},
    )
    body = r.json()
    assert r.status_code == 200 and body["description"] == "Padaria Nova" and body["amount"] == 15.5
    assert body["type"] == "income" and body["date"].startswith("2026-10-01") and body["account_id"] == acc["id"]

    r = client.put(f"/transactions/{tx['id']}", headers=auth, json={"account_id": None})
    assert r.json()["account_id"] is None


# ---------------------------------------------------------------- categorias
def test_rename_category_updates_transactions_and_budget(client, auth):
    add(client, auth, "a", 10, "mercado")
    add(client, auth, "b", 20, "mercado")
    client.put("/budgets/mercado", headers=auth, json={"monthly_limit": 500})

    r = client.put("/categories/Mercado", headers=auth, json={"new_name": "  Alimentacao "})
    assert r.status_code == 200
    assert r.json() == {"target": "alimentacao", "transactions_updated": 2, "merged": False}
    assert client.get("/transactions/categories", headers=auth).json() == ["alimentacao"]
    assert [b["category"] for b in client.get("/budgets/", headers=auth).json()] == ["alimentacao"]

    assert client.put("/categories/inexistente", headers=auth, json={"new_name": "x"}).status_code == 404
    assert client.put("/categories/alimentacao", headers=auth, json={"new_name": "ALIMENTACAO"}).status_code == 400


def test_rename_into_existing_category_merges_and_target_budget_wins(client, auth):
    add(client, auth, "a", 10, "mercado")
    add(client, auth, "b", 20, "supermercado")
    client.put("/budgets/mercado", headers=auth, json={"monthly_limit": 100})
    client.put("/budgets/supermercado", headers=auth, json={"monthly_limit": 900})

    r = client.put("/categories/mercado", headers=auth, json={"new_name": "supermercado"})
    assert r.json()["merged"] is True and r.json()["transactions_updated"] == 1
    budgets = client.get("/budgets/", headers=auth).json()
    assert [(b["category"], b["monthly_limit"]) for b in budgets] == [("supermercado", 900)]


def test_merge_many_categories_moves_the_first_budget_and_drops_the_rest(client, auth):
    add(client, auth, "a", 10, "mercado")
    add(client, auth, "b", 20, "supermercado")
    add(client, auth, "c", 30, "lazer")
    client.put("/budgets/mercado", headers=auth, json={"monthly_limit": 500})
    client.put("/budgets/supermercado", headers=auth, json={"monthly_limit": 300})

    r = client.post(
        "/categories/merge", headers=auth, json={"sources": ["mercado", "supermercado"], "target": "comida"}
    )
    assert r.status_code == 200 and r.json()["transactions_updated"] == 2 and r.json()["merged"] is True
    cats = {c["category"]: c for c in client.get("/categories/", headers=auth).json()}
    assert set(cats) == {"comida", "lazer"} and cats["comida"]["transactions"] == 2
    assert cats["comida"]["budget_limit"] == 500

    # nada e alterado quando uma das origens nao existe
    bad = client.post("/categories/merge", headers=auth, json={"sources": ["lazer", "nao-existe"], "target": "x"})
    assert bad.status_code == 404
    assert "lazer" in {c["category"] for c in client.get("/categories/", headers=auth).json()}


def test_viewer_cannot_change_categories(client, auth):
    add(client, auth, "a", 10, "mercado")
    viewer = register_admin(client, "chefe")  # so para promover o outro
    me = client.get("/auth/me", headers=auth).json()
    client.put(f"/admin/users/{me['id']}/role", headers=viewer, json={"role": "viewer"})
    assert client.put("/categories/mercado", headers=auth, json={"new_name": "x"}).status_code == 403
    assert client.get("/categories/", headers=auth).status_code == 200


# ---------------------------------------------------------------- contas
def test_accounts_balance_filter_and_delete_keeps_transactions(client, auth):
    acc = client.post("/accounts/", headers=auth, json={"name": "Nubank", "initial_balance": 1000}).json()
    assert client.post("/accounts/", headers=auth, json={"name": "NUBANK"}).status_code == 400  # sem diferenciar caixa
    for desc, amount, kind in (("Salario", 200, "income"), ("Mercado", 50, "expense")):
        r = client.post(
            "/transactions/", headers=auth,
            json={"description": desc, "amount": amount, "type": kind, "account_id": acc["id"]},
        )
        assert r.status_code == 201
    add(client, auth, "Sem conta", 999)

    listed = client.get("/accounts/", headers=auth).json()[0]
    assert listed["balance"] == 1150 and listed["income"] == 200 and listed["expense"] == 50
    assert listed["transaction_count"] == 2

    r = client.get("/transactions/", headers=auth, params={"account_id": acc["id"]})
    assert {t["description"] for t in r.json()} == {"Salario", "Mercado"}

    assert client.put(f"/accounts/{acc['id']}", headers=auth, json={"name": "Nubank PF"}).json()["name"] == "Nubank PF"

    assert client.delete(f"/accounts/{acc['id']}", headers=auth).status_code == 204
    txs = client.get("/transactions/", headers=auth).json()
    assert len(txs) == 3 and all(t["account_id"] is None for t in txs)


def test_account_isolation_between_users(client, auth):
    acc = client.post("/accounts/", headers=auth, json={"name": "Minha"}).json()
    other = register_and_login(client, "intruso")
    assert client.get("/accounts/", headers=other).json() == []
    assert client.delete(f"/accounts/{acc['id']}", headers=other).status_code == 404
    r = client.post("/transactions/", headers=other, json={"description": "x", "amount": 1, "account_id": acc["id"]})
    assert r.status_code == 422


# ---------------------------------------------------------------- metas
def test_goal_progress_required_monthly_and_status(client, auth):
    deadline = (_today() + timedelta(days=91)).isoformat()
    goal = client.post(
        "/goals/", headers=auth, json={"name": "Viagem", "target_amount": 1000, "deadline": deadline}
    ).json()
    assert goal["status"] == "active" and goal["days_left"] == 91 and goal["pct"] == 0

    g = client.post(f"/goals/{goal['id']}/contribute", headers=auth, json={"amount": 250}).json()
    assert g["pct"] == 25 and g["remaining"] == 750 and g["required_monthly"] == 250  # 750 / 3 meses

    g = client.post(f"/goals/{goal['id']}/contribute", headers=auth, json={"amount": -99999}).json()
    assert g["saved_amount"] == 0  # nunca negativo

    g = client.post(f"/goals/{goal['id']}/contribute", headers=auth, json={"amount": 1000}).json()
    assert g["status"] == "completed" and g["pct"] == 100 and g["required_monthly"] is None

    assert client.post(f"/goals/{goal['id']}/contribute", headers=auth, json={"amount": 0}).status_code == 422

    late = client.post(
        "/goals/", headers=auth,
        json={"name": "Atrasada", "target_amount": 100, "deadline": (_today() - timedelta(days=1)).isoformat()},
    ).json()
    assert late["status"] == "overdue" and late["required_monthly"] is None

    g = client.put(f"/goals/{late['id']}", headers=auth, json={"deadline": None}).json()
    assert g["deadline"] is None and g["status"] == "active"

    assert client.delete(f"/goals/{goal['id']}", headers=auth).status_code == 204
    assert [x["name"] for x in client.get("/goals/", headers=auth).json()] == ["Atrasada"]


def test_goals_are_private(client, auth):
    goal = client.post("/goals/", headers=auth, json={"name": "G", "target_amount": 10}).json()
    other = register_and_login(client, "intruso")
    assert client.get("/goals/", headers=other).json() == []
    assert client.post(f"/goals/{goal['id']}/contribute", headers=other, json={"amount": 1}).status_code == 404


# ---------------------------------------------------------------- recorrentes
def test_recurring_rule_generates_backlog_once_and_advances(client, auth):
    start = (_today() - timedelta(days=65)).isoformat()
    acc = client.post("/accounts/", headers=auth, json={"name": "Cartao", "type": "credit"}).json()
    rule = client.post(
        "/recurring/", headers=auth,
        json={"description": "Netflix", "amount": 39.9, "category": "Assinaturas", "frequency": "monthly",
              "start_date": start, "account_id": acc["id"]},
    )
    assert rule.status_code == 201 and rule.json()["category"] == "assinaturas"

    txs = client.get("/transactions/", headers=auth).json()  # a listagem gera as vencidas
    assert len(txs) == 3 and {t["description"] for t in txs} == {"Netflix"}
    assert all(t["account_id"] == acc["id"] for t in txs)

    assert len(client.get("/transactions/", headers=auth).json()) == 3  # idempotente
    assert client.post("/recurring/run", headers=auth).json() == {"created": 0}
    rules = client.get("/recurring/", headers=auth).json()
    assert rules[0]["active"] is True and rules[0]["next_date"] > _today().isoformat()

    # o orcamento/analytics enxergam as geradas
    overview = client.get("/analytics/overview?days=90", headers=auth).json()
    assert overview["summary"]["total_expense"] == round(39.9 * 3, 2)


def test_recurring_with_end_date_deactivates_and_delete_keeps_history(client, auth):
    start = (_today() - timedelta(days=14)).isoformat()
    end = (_today() - timedelta(days=7)).isoformat()
    rule = client.post(
        "/recurring/", headers=auth,
        json={"description": "Aula", "amount": 80, "frequency": "weekly", "start_date": start, "end_date": end},
    ).json()
    assert client.post("/recurring/run", headers=auth).json() == {"created": 2}
    assert client.get("/recurring/", headers=auth).json()[0]["active"] is False

    assert client.delete(f"/recurring/{rule['id']}", headers=auth).status_code == 204
    assert len(client.get("/transactions/", headers=auth).json()) == 2


def test_recurring_validation_and_pause(client, auth):
    bad = client.post(
        "/recurring/", headers=auth,
        json={"description": "x", "amount": 1, "start_date": "2026-10-10", "end_date": "2026-10-01"},
    )
    assert bad.status_code == 422

    future = (_today() + timedelta(days=10)).isoformat()
    rule = client.post(
        "/recurring/", headers=auth, json={"description": "Futura", "amount": 10, "start_date": future}
    ).json()
    assert client.get("/transactions/", headers=auth).json() == []  # ainda nao venceu

    paused = client.put(f"/recurring/{rule['id']}", headers=auth, json={"active": False}).json()
    assert paused["active"] is False


def test_detected_recurring_is_flagged_once_automated(client, auth):
    now = datetime.utcnow()
    for months in (3, 2, 1):
        add(client, auth, "Academia", 100, "saude", date=now - timedelta(days=30 * months))
    detected = client.get("/analytics/recurring", headers=auth).json()
    assert detected and detected[0]["automated"] is False

    client.post(
        "/recurring/", headers=auth,
        json={"description": "Academia", "amount": 100, "category": "saude",
              "start_date": (_today() + timedelta(days=5)).isoformat()},
    )
    assert client.get("/analytics/recurring", headers=auth).json()[0]["automated"] is True


# ---------------------------------------------------------------- alertas
def _budget_mails():
    return [m for m in mailer.outbox if m["subject"].startswith("Orcamento de")]


def test_budget_alert_email_is_sent_once_per_month(client, auth):
    assert client.put("/alerts/settings", headers=auth, json={"email_enabled": True, "threshold_pct": 100}).status_code == 200
    client.put("/budgets/lazer", headers=auth, json={"monthly_limit": 100})

    add(client, auth, "Cinema", 60, "lazer")
    assert _budget_mails() == []  # 60% < 100%
    add(client, auth, "Show", 90, "lazer")  # 150%
    mails = _budget_mails()
    assert len(mails) == 1 and mails[0]["to"] == "tester@example.com" and "lazer" in mails[0]["subject"]

    add(client, auth, "Outro", 10, "lazer")
    assert len(_budget_mails()) == 1  # mesmo mes e limiar: nao repete
    assert client.post("/alerts/check", headers=auth).json() == {"sent": []}


def test_alert_check_endpoint_reports_what_was_sent(client, auth):
    client.put("/budgets/lazer", headers=auth, json={"monthly_limit": 100})
    add(client, auth, "Show", 90, "lazer")  # sem alertas configurados: nada enviado
    assert client.post("/alerts/check", headers=auth).json() == {"sent": []}

    client.put("/alerts/settings", headers=auth, json={"email_enabled": True, "threshold_pct": 80})
    sent = client.post("/alerts/check", headers=auth).json()["sent"]
    assert sent == [{"category": "lazer", "pct_used": 90.0, "channels": ["email"]}]


def test_webhook_url_is_validated_and_called(client, auth, monkeypatch):
    for bad in ("ftp://exemplo.com/x", "http://127.0.0.1/hook", "http://user:pw@exemplo.com/x", "nao-e-url"):
        r = client.put("/alerts/settings", headers=auth, json={"webhook_url": bad})
        assert r.status_code == 422, bad

    monkeypatch.setattr(alerts.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    ok = client.put(
        "/alerts/settings", headers=auth,
        json={"webhook_url": "https://hooks.exemplo.com/abc", "threshold_pct": 100},
    )
    assert ok.status_code == 200 and ok.json()["webhook_url"] == "https://hooks.exemplo.com/abc"

    calls = []
    monkeypatch.setattr(alerts, "_post_webhook", lambda url, payload: calls.append((url, payload)) or True)
    client.put("/budgets/lazer", headers=auth, json={"monthly_limit": 100})
    add(client, auth, "Show", 150, "lazer")
    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "https://hooks.exemplo.com/abc"
    assert payload["event"] == "budget_alert" and payload["category"] == "lazer" and payload["pct_used"] == 150.0


def test_failed_delivery_is_retried_on_next_check(client, auth, monkeypatch):
    monkeypatch.setattr(alerts, "_post_webhook", lambda url, payload: False)
    monkeypatch.setattr(alerts.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    client.put("/alerts/settings", headers=auth, json={"webhook_url": "https://hooks.exemplo.com/abc"})
    client.put("/budgets/lazer", headers=auth, json={"monthly_limit": 100})
    add(client, auth, "Show", 150, "lazer")
    assert client.post("/alerts/check", headers=auth).json() == {"sent": []}  # falhou, mas nao foi "queimado"

    monkeypatch.setattr(alerts, "_post_webhook", lambda url, payload: True)
    assert client.post("/alerts/check", headers=auth).json()["sent"][0]["channels"] == ["webhook"]


# ---------------------------------------------------------------- LGPD
def test_export_my_data_has_everything_and_no_password_hash(client, auth):
    add(client, auth, "Mercado", 10, "alimentacao")
    client.put("/budgets/alimentacao", headers=auth, json={"monthly_limit": 100})
    client.post("/accounts/", headers=auth, json={"name": "Conta"})
    client.post("/goals/", headers=auth, json={"name": "Meta", "target_amount": 10})

    r = client.get("/auth/me/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["user"]["username"] == "tester" and data["user"]["email"] == "tester@example.com"
    assert [t["description"] for t in data["transactions"]] == ["Mercado"]
    assert len(data["budgets"]) == 1 and len(data["accounts"]) == 1 and len(data["goals"]) == 1
    assert "hashed_password" not in r.text and "password" not in data["user"]


def test_export_contains_only_my_data(client, auth):
    add(client, auth, "Meu", 10)
    other = register_and_login(client, "outro")
    add(client, other, "Dele", 20)
    assert [t["description"] for t in client.get("/auth/me/export", headers=other).json()["transactions"]] == ["Dele"]


def test_delete_account_removes_everything_and_requires_password(client, auth):
    add(client, auth, "Mercado", 10)
    client.put("/budgets/alimentacao", headers=auth, json={"monthly_limit": 100})
    acc = client.post("/accounts/", headers=auth, json={"name": "Conta"}).json()
    client.post("/goals/", headers=auth, json={"name": "Meta", "target_amount": 10})
    client.post("/recurring/", headers=auth, json={"description": "R", "amount": 1, "account_id": acc["id"]})
    client.put("/alerts/settings", headers=auth, json={"email_enabled": True})
    other = register_and_login(client, "outro")
    add(client, other, "Dele", 20)

    assert client.request("DELETE", "/auth/me", headers=auth, json={"password": "errada123"}).status_code == 400
    assert client.get("/auth/me", headers=auth).status_code == 200

    assert client.request("DELETE", "/auth/me", headers=auth, json={"password": "secret123"}).status_code == 204
    assert client.get("/auth/me", headers=auth).status_code == 401
    assert client.post("/auth/login", data={"username": "tester", "password": "secret123"}).status_code == 401

    from app import models
    from app.database import SessionLocal

    with SessionLocal() as db:
        for model in (models.Transaction, models.Budget, models.Account, models.Goal,
                      models.RecurringRule, models.AlertSettings):
            assert db.query(model).filter(model.owner_id != db.query(models.User.id).filter(
                models.User.username == "outro").scalar()).count() == 0
    assert [t["description"] for t in client.get("/transactions/", headers=other).json()] == ["Dele"]


def test_last_admin_cannot_delete_account(client):
    admin = register_admin(client, "chefe")
    r = client.request("DELETE", "/auth/me", headers=admin, json={"password": "secret123"})
    assert r.status_code == 400 and client.get("/auth/me", headers=admin).status_code == 200


# --------------------------------------------------- reset de senha e e-mail
def _token_from_mail(query: str, subject: str):
    mail = next(m for m in mailer.outbox if m["subject"] == subject)
    return re.search(query + r"=(\S+)", mail["body"]).group(1)


def test_password_reset_flow_is_single_use_and_revokes_sessions(client, auth):
    mailer.outbox.clear()
    r = client.post("/auth/forgot-password", json={"email": "tester@example.com"})
    assert r.status_code == 202
    token = _token_from_mail("reset_token", "Redefinicao de senha")

    # o token de reset nunca funciona como token de acesso
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401

    assert client.post("/auth/reset-password", json={"token": token, "new_password": "novasenha123"}).status_code == 204
    assert client.post("/auth/login", data={"username": "tester", "password": "secret123"}).status_code == 401
    assert client.post("/auth/login", data={"username": "tester", "password": "novasenha123"}).status_code == 200
    assert client.get("/auth/me", headers=auth).status_code == 401  # sessao antiga derrubada

    again = client.post("/auth/reset-password", json={"token": token, "new_password": "outrasenha123"})
    assert again.status_code == 400  # uso unico


def test_forgot_password_does_not_reveal_unknown_emails(client, auth):
    mailer.outbox.clear()
    known = client.post("/auth/forgot-password", json={"email": "tester@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "ninguem@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert [m["to"] for m in mailer.outbox] == ["tester@example.com"]


def test_reset_rejects_garbage_expired_and_wrong_purpose_tokens(client, auth):
    from datetime import timedelta as td

    from app.auth import create_access_token

    body = {"new_password": "novasenha123"}
    assert client.post("/auth/reset-password", json={"token": "lixo" * 5, **body}).status_code == 400
    expired = create_access_token({"sub": "tester", "purpose": "reset", "tv": 0, "pw": "x"}, expires_delta=td(seconds=-5))
    assert client.post("/auth/reset-password", json={"token": expired, **body}).status_code == 400
    verify_token = _token_from_mail("verify_token", "Confirme seu e-mail")
    assert client.post("/auth/reset-password", json={"token": verify_token, **body}).status_code == 400


def test_email_verification_flow(client):
    client.post("/auth/register", json={"username": "novo", "email": "novo@example.com", "password": "secret123"})
    token = _token_from_mail("verify_token", "Confirme seu e-mail")
    login = client.post("/auth/login", data={"username": "novo", "password": "secret123"})
    h = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/auth/me", headers=h).json()["email_verified"] is False

    assert client.post("/auth/verify-email", json={"token": token}).json() == {"verified": True}
    assert client.get("/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/auth/resend-verification", headers=h).json()["detail"].startswith("E-mail ja verificado")


def test_resend_verification_sends_a_new_link(client, auth):
    mailer.outbox.clear()
    assert client.post("/auth/resend-verification", headers=auth).status_code == 202
    assert [m["subject"] for m in mailer.outbox] == ["Confirme seu e-mail"]


def test_login_can_require_verified_email(client, monkeypatch):
    client.post("/auth/register", json={"username": "novo", "email": "novo@example.com", "password": "secret123"})
    token = _token_from_mail("verify_token", "Confirme seu e-mail")
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    assert client.post("/auth/login", data={"username": "novo", "password": "secret123"}).status_code == 403
    client.post("/auth/verify-email", json={"token": token})
    assert client.post("/auth/login", data={"username": "novo", "password": "secret123"}).status_code == 200


def test_cli_run_recurring_generates_for_all_users(client, auth):
    from app import cli
    from app.database import SessionLocal

    client.post(
        "/recurring/", headers=auth,
        json={"description": "Aluguel", "amount": 1000, "start_date": (_today() - timedelta(days=1)).isoformat()},
    )
    with SessionLocal() as db:
        assert cli.run_recurring(db) == {"tester": 1}
        assert cli.run_recurring(db) == {}
