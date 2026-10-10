from datetime import datetime, timedelta

from tests.conftest import register_and_login


def add(client, h, description="Cafe", amount=10, category="alimentacao", type="expense", date=None):
    body = {"description": description, "amount": amount, "category": category, "type": type}
    if date:
        body["date"] = date.isoformat()
    r = client.post("/transactions/", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_normalizes_category(client, auth):
    tx = add(client, auth, category="  Alimentacao ")
    assert tx["category"] == "alimentacao"


def test_validation(client, auth):
    bad = {"description": "x", "amount": -5, "type": "expense"}
    assert client.post("/transactions/", headers=auth, json=bad).status_code == 422
    bad = {"description": "x", "amount": 5, "type": "transfer"}
    assert client.post("/transactions/", headers=auth, json=bad).status_code == 422


def test_timezone_aware_date_is_accepted(client, auth):
    r = client.post(
        "/transactions/",
        headers=auth,
        json={"description": "tz", "amount": 1, "date": "2026-10-09T10:00:00-03:00"},
    )
    assert r.status_code == 201 and r.json()["date"].startswith("2026-10-09T13:00")


def test_filters_search_sort_pagination_and_total_header(client, auth):
    now = datetime.utcnow()
    add(client, auth, "Mercado Central", 120, "alimentacao", date=now - timedelta(days=1))
    add(client, auth, "Uber", 30, "transporte", date=now - timedelta(days=2))
    add(client, auth, "Salario", 5000, "salario", "income", date=now - timedelta(days=3))
    add(client, auth, "Mercado Extra", 80, "alimentacao", date=now - timedelta(days=4))

    r = client.get("/transactions/?q=mercado", headers=auth)
    assert {t["description"] for t in r.json()} == {"Mercado Central", "Mercado Extra"}
    assert r.headers["X-Total-Count"] == "2"

    r = client.get("/transactions/?type=income", headers=auth)
    assert [t["description"] for t in r.json()] == ["Salario"]

    r = client.get("/transactions/?sort_by=amount&order=asc&limit=2", headers=auth)
    assert [t["amount"] for t in r.json()] == [30, 80]
    assert r.headers["X-Total-Count"] == "4"  # total filtrado, nao o da pagina

    r = client.get("/transactions/?min_amount=100&max_amount=200", headers=auth)
    assert [t["description"] for t in r.json()] == ["Mercado Central"]

    start = (now - timedelta(days=2, hours=1)).isoformat()
    r = client.get("/transactions/", headers=auth, params={"start_date": start})
    assert len(r.json()) == 2


def test_like_wildcards_are_literal(client, auth):
    add(client, auth, "100% suco")
    add(client, auth, "Outra coisa")
    r = client.get("/transactions/", headers=auth, params={"q": "%"})
    assert [t["description"] for t in r.json()] == ["100% suco"]


def test_update_delete_and_isolation_between_users(client, auth):
    tx = add(client, auth, "Cinema", 40, "lazer")
    r = client.put(f"/transactions/{tx['id']}", headers=auth, json={"amount": 55, "category": "Lazer "})
    assert r.status_code == 200 and r.json()["amount"] == 55 and r.json()["category"] == "lazer"

    other = register_and_login(client, "intruso")
    assert client.get(f"/transactions/{tx['id']}", headers=other).status_code == 404
    assert client.put(f"/transactions/{tx['id']}", headers=other, json={"amount": 1}).status_code == 404
    assert client.delete(f"/transactions/{tx['id']}", headers=other).status_code == 404
    assert client.get("/transactions/", headers=other).json() == []

    assert client.delete(f"/transactions/{tx['id']}", headers=auth).status_code == 204
    assert client.get(f"/transactions/{tx['id']}", headers=auth).status_code == 404


def test_categories_endpoint(client, auth):
    add(client, auth, "a", 1, "b-cat")
    add(client, auth, "b", 1, "a-cat")
    assert client.get("/transactions/categories", headers=auth).json() == ["a-cat", "b-cat"]


def test_export_csv_and_formula_injection_guard(client, auth):
    add(client, auth, "=HYPERLINK(\"http://x\")", 10, "lazer")
    add(client, auth, "Normal", 20, "lazer")
    r = client.get("/transactions/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    body = r.text
    assert "id,date,description,category,type,amount" in body
    assert "'=HYPERLINK" in body and ",=HYPERLINK" not in body
    assert "20.00" in body


def test_import_csv(client, auth):
    csv_text = (
        "descricao;valor;categoria;tipo;data\n"
        "Mercado;150,50;Alimentacao;despesa;09/10/2026\n"
        "Salario;5.000,00;salario;receita;05/10/2026\n"
        "Quebrado;abc;x;despesa;01/10/2026\n"
    )
    r = client.post("/transactions/import", headers=auth, files={"file": ("t.csv", csv_text.encode(), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 2 and data["skipped"] == 1 and data["errors"][0]["row"] == 4
    listed = client.get("/transactions/", headers=auth).json()
    assert {t["description"] for t in listed} == {"Mercado", "Salario"}


def test_import_rejects_huge_file(client, auth):
    big = b"description,amount\n" + b"a,1\n" * 600_000
    r = client.post("/transactions/import", headers=auth, files={"file": ("big.csv", big, "text/csv")})
    assert r.status_code == 413
