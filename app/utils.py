"""Utilitarios compartilhados."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Datetime UTC *naive* (compativel com as colunas DateTime do banco)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
