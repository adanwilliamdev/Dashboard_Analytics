"""Calendario das transacoes recorrentes (funcoes puras, sem banco).

Todas as datas sao ``datetime`` naive a meia-noite (horario de parede de APP_TIMEZONE), como no banco.
"""
import calendar
from datetime import datetime, timedelta
from typing import List, Optional

FREQUENCIES = ("weekly", "monthly", "yearly")
MAX_PER_RUN = 366  # teto de ocorrencias geradas por regra a cada execucao (limita retroativos enormes)


def _add_months(base: datetime, months: int, anchor_day: int) -> datetime:
    """Soma meses mantendo o dia-ancora; em meses curtos usa o ultimo dia (31/01 -> 28/02 -> 31/03)."""
    index = base.year * 12 + (base.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    day = min(anchor_day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def next_occurrence(current: datetime, frequency: str, anchor_day: int) -> datetime:
    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "monthly":
        return _add_months(current, 1, anchor_day)
    if frequency == "yearly":
        return _add_months(current, 12, anchor_day)
    raise ValueError(f"frequencia invalida: {frequency!r}")


def due_dates(
    next_date: datetime,
    today: datetime,
    frequency: str,
    anchor_day: int,
    end_date: Optional[datetime] = None,
    limit: int = MAX_PER_RUN,
) -> List[datetime]:
    """Ocorrencias com data <= hoje (e <= end_date), a partir de next_date. Ate ``limit`` por chamada."""
    out: List[datetime] = []
    current = next_date
    while current <= today and len(out) < limit:
        if end_date is not None and current > end_date:
            break
        out.append(current)
        current = next_occurrence(current, frequency, anchor_day)
    return out
