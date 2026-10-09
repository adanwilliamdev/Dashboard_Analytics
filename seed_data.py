"""Popula o banco com dados de exemplo (usuario demo + transacoes)."""
import random
from datetime import datetime, timedelta

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app import models

Base.metadata.create_all(bind=engine)

DEMO_USER = "demo"
DEMO_PASS = "demo123"
DEMO_EMAIL = "demo@example.com"

CATEGORIES_EXPENSE = ["alimentacao", "transporte", "moradia", "lazer", "saude", "educacao"]
CATEGORIES_INCOME = ["salario", "freelance", "investimentos", "vendas"]

DESCRIPTIONS_EXPENSE = [
    "Supermercado", "Restaurante", "Uber", "Onibus", "Aluguel", "Cinema",
    "Academia", "Farmacia", "Curso online", "Combustivel", "Streaming",
]
DESCRIPTIONS_INCOME = ["Salario mensal", "Projeto freelance", "Dividendos", "Venda OLX"]


def run():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == DEMO_USER).first()
        if not user:
            user = models.User(
                username=DEMO_USER,
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASS),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print("Usuario demo criado: " + DEMO_USER + " / " + DEMO_PASS)
        else:
            print("Usuario demo ja existe: " + DEMO_USER)

        existing = db.query(models.Transaction).filter(models.Transaction.owner_id == user.id).count()
        if existing > 0:
            print("Ja existem " + str(existing) + " transacoes. Pulando seed.")
            return

        now = datetime.utcnow()
        total = 0
        for i in range(180):
            days_ago = random.randint(0, 180)
            date = now - timedelta(days=days_ago)

            is_income = random.random() < 0.25
            if is_income:
                desc = random.choice(DESCRIPTIONS_INCOME)
                cat = random.choice(CATEGORIES_INCOME)
                amount = round(random.uniform(500, 8000), 2)
                tx_type = "income"
            else:
                desc = random.choice(DESCRIPTIONS_EXPENSE)
                cat = random.choice(CATEGORIES_EXPENSE)
                amount = round(random.uniform(10, 800), 2)
                tx_type = "expense"

            tx = models.Transaction(
                description=desc,
                amount=amount,
                category=cat,
                type=tx_type,
                date=date,
                owner_id=user.id,
            )
            db.add(tx)
            total += 1

        db.commit()
        print(str(total) + " transacoes de exemplo inseridas.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
