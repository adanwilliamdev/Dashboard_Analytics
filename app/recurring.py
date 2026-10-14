"""Gera as transacoes das regras recorrentes vencidas.

Chamado de forma preguicosa (ao abrir o dashboard/listar transacoes) e pelo comando
``python -m app.cli run-recurring`` (cron, para quem quer gerar mesmo sem ninguem logar).
E idempotente e seguro contra execucoes concorrentes: antes de criar as transacoes, a regra
"avanca" o proprio ``next_date`` com um UPDATE condicional; so quem ganhou a corrida cria.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models, recurrence
from app.cache import get_cache, user_ns
from app.utils import local_now


def _today_midnight() -> datetime:
    return local_now().replace(hour=0, minute=0, second=0, microsecond=0)


def materialize_due(db: Session, owner_id: int, today: Optional[datetime] = None) -> int:
    """Cria as transacoes vencidas das regras ativas do usuario. Retorna quantas foram criadas."""
    today = today or _today_midnight()
    R = models.RecurringRule
    rules = db.query(R).filter(R.owner_id == owner_id, R.active.is_(True), R.next_date <= today).all()

    created = 0
    for rule in rules:
        dates = recurrence.due_dates(rule.next_date, today, rule.frequency, rule.anchor_day, rule.end_date)
        if not dates:
            # nada a gerar: so desativa se a regra ja passou do fim (ex.: end_date editado para o passado)
            if rule.end_date is not None and rule.next_date > rule.end_date:
                rule.active = False
            continue
        new_next = recurrence.next_occurrence(dates[-1], rule.frequency, rule.anchor_day)
        finished = rule.end_date is not None and new_next > rule.end_date
        won = (
            db.query(R)
            .filter(R.id == rule.id, R.next_date == rule.next_date, R.active.is_(True))
            .update({"next_date": new_next, "active": not finished}, synchronize_session=False)
        )
        if won != 1:  # outra requisicao ja processou esta regra
            continue
        db.add_all(
            [
                models.Transaction(
                    description=rule.description,
                    amount=rule.amount,
                    category=rule.category,
                    type=rule.type,
                    date=d,
                    owner_id=owner_id,
                    account_id=rule.account_id,
                    recurring_rule_id=rule.id,
                )
                for d in dates
            ]
        )
        created += len(dates)

    db.commit()
    if created:
        get_cache().invalidate(user_ns(owner_id))
    return created
