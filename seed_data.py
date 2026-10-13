"""Popula o banco com dados de demonstracao realistas.

Uso:
    python seed_data.py                 # 6 meses de dados (so se o usuario demo estiver vazio)
    python seed_data.py --months 12     # historico maior
    python seed_data.py --reset         # apaga as transacoes/orcamentos do demo e recria
"""
import argparse
import random
from datetime import datetime, timedelta

from app import models
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.utils import local_now

DEMO_USER = "demo"
DEMO_PASS = "demo1234"
DEMO_EMAIL = "demo@example.com"

# (descricao, categoria, valor_medio, dia_do_mes)
RECURRING_EXPENSES = [
    ("Aluguel", "moradia", 1500.0, 10),
    ("Internet", "moradia", 110.0, 12),
    ("Streaming", "lazer", 39.9, 15),
    ("Academia", "saude", 99.0, 8),
    ("Plano de saude", "saude", 320.0, 20),
]
RECURRING_INCOME = [("Salario mensal", "salario", 5200.0, 5)]

VARIABLE_EXPENSES = {
    "alimentacao": (["Supermercado", "Restaurante", "Padaria", "Delivery"], 25, 220, 0.55),
    "transporte": (["Uber", "Combustivel", "Onibus"], 8, 160, 0.30),
    "lazer": (["Cinema", "Bar", "Show", "Jogo"], 20, 250, 0.12),
    "saude": (["Farmacia"], 15, 120, 0.06),
    "educacao": (["Curso online", "Livro"], 30, 200, 0.04),
}
FREELANCE = ["Projeto freelance", "Venda usada", "Dividendos"]


def _clamp_day(year: int, month: int, day: int) -> int:
    return min(day, 28)  # evita problemas com fevereiro


def build_transactions(rng: random.Random, months: int, now: datetime):
    start = (now - timedelta(days=30 * months)).replace(hour=12, minute=0, second=0, microsecond=0)
    rows = []

    # recorrentes (um por mes, com leve variacao)
    cursor = start.replace(day=1)
    while cursor <= now:
        for desc, cat, value, day in RECURRING_EXPENSES:
            d = cursor.replace(day=_clamp_day(cursor.year, cursor.month, day))
            if start <= d <= now:
                rows.append((desc, cat, round(value * rng.uniform(0.98, 1.03), 2), "expense", d))
        for desc, cat, value, day in RECURRING_INCOME:
            d = cursor.replace(day=_clamp_day(cursor.year, cursor.month, day))
            if start <= d <= now:
                rows.append((desc, cat, value, "income", d))
        cursor = (cursor.replace(day=28) + timedelta(days=5)).replace(day=1)

    # variaveis (alguns por dia, com peso por categoria)
    categories = list(VARIABLE_EXPENSES)
    weights = [VARIABLE_EXPENSES[c][3] for c in categories]
    day = start
    while day <= now:
        weekend_boost = 1.4 if day.weekday() >= 4 else 1.0  # sexta a domingo gasta mais
        for _ in range(int(rng.random() * 2.2 * weekend_boost)):
            cat = rng.choices(categories, weights)[0]
            names, lo, hi, _w = VARIABLE_EXPENSES[cat]
            rows.append((rng.choice(names), cat, round(rng.uniform(lo, hi), 2), "expense", day))
        if rng.random() < 0.03:
            rows.append((rng.choice(FREELANCE), "freelance", round(rng.uniform(300, 1800), 2), "income", day))
        day += timedelta(days=1)

    # alguns gastos atipicos para a deteccao de anomalias
    for _ in range(max(1, months // 3)):
        d = start + timedelta(days=rng.randint(0, (now - start).days))
        rows.append(("Compra grande", "lazer", round(rng.uniform(1200, 2500), 2), "expense", d))
    return rows


def run(months: int = 6, reset: bool = False, seed: int = 42):
    Base.metadata.create_all(bind=engine)
    rng = random.Random(seed)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == DEMO_USER).first()
        if not user:
            user = models.User(username=DEMO_USER, email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASS))
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Usuario demo criado: {DEMO_USER} / {DEMO_PASS}")
        else:
            print(f"Usuario demo ja existe: {DEMO_USER}")

        if reset:
            db.query(models.Transaction).filter(models.Transaction.owner_id == user.id).delete()
            db.query(models.Budget).filter(models.Budget.owner_id == user.id).delete()
            db.commit()

        existing = db.query(models.Transaction).filter(models.Transaction.owner_id == user.id).count()
        if existing:
            print(f"Ja existem {existing} transacoes. Use --reset para recriar.")
            return

        rows = build_transactions(rng, months, local_now())
        db.add_all(
            models.Transaction(description=d, category=c, amount=a, type=t, date=dt, owner_id=user.id)
            for d, c, a, t, dt in rows
        )
        for cat, limit in {"alimentacao": 1200.0, "transporte": 500.0, "lazer": 600.0, "saude": 500.0}.items():
            db.add(models.Budget(category=cat, monthly_limit=limit, owner_id=user.id))
        db.commit()
        print(f"{len(rows)} transacoes e 4 orcamentos criados ({months} meses).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(months=args.months, reset=args.reset, seed=args.seed)
