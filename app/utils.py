"""Utilitarios compartilhados.

Convencao de datas
------------------
O banco guarda datetimes *naive* que representam o horario de parede em ``APP_TIMEZONE``
(padrao ``America/Sao_Paulo``). Assim, "hoje", a janela de dias, o mes do orcamento e a previsao
seguem o dia do usuario, e nao o do servidor (UTC). Datetimes recebidos *com* fuso sao convertidos
para ``APP_TIMEZONE`` antes de gravar/filtrar (ver ``to_local_naive``).

Campos de auditoria (``created_at``) continuam em UTC naive (``utcnow``).
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Datetime UTC *naive* (compativel com as colunas DateTime do banco)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def app_timezone() -> ZoneInfo:
    from app.config import settings  # import tardio: utils continua importavel sem a stack web

    return ZoneInfo(settings.APP_TIMEZONE)


def local_now() -> datetime:
    """Agora no fuso da aplicacao, como datetime naive (horario de parede)."""
    return datetime.now(app_timezone()).replace(tzinfo=None)


def to_local_naive(value: Optional[datetime]) -> Optional[datetime]:
    """Datetime com fuso -> horario de parede de APP_TIMEZONE (naive). Naive passa direto."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(app_timezone()).replace(tzinfo=None)
    return value
