"""Diferenca entre a tabela de transacoes original e a editada no dashboard (funcao pura, testavel)."""
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, List, Tuple

VALID_TYPES = ("expense", "income")


def _as_date(value: Any) -> date:
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    if hasattr(value, "date") and callable(value.date):  # datetime / pandas.Timestamp
        return value.date()
    return value


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and value != value)  # None ou NaN


def diff_rows(
    original: Iterable[Dict[str, Any]], edited: Iterable[Dict[str, Any]]
) -> Tuple[Dict[int, Dict[str, Any]], List[int]]:
    """Retorna ({id: campos_alterados_para_o_PUT}, [ids_com_valor_invalido]).

    A data so e enviada se o DIA mudou (assim a hora gravada de transacoes antigas nao e zerada).
    Linhas com campo apagado ou valor invalido (descricao vazia, valor <= 0, tipo desconhecido)
    vao para a lista de invalidos e nao geram alteracao.
    """
    old_by_id = {int(r["id"]): r for r in original}
    changes: Dict[int, Dict[str, Any]] = {}
    invalid: List[int] = []
    for row in edited:
        row_id = int(row["id"])
        old = old_by_id.get(row_id)
        if old is None:
            continue
        if any(_is_blank(row.get(k)) for k in ("description", "category", "type", "amount", "date")):
            invalid.append(row_id)
            continue
        description = str(row["description"]).strip()
        category = str(row["category"]).strip().lower()
        tx_type = str(row["type"])
        try:
            amount = round(float(row["amount"]), 2)
            new_day = _as_date(row["date"])
        except (TypeError, ValueError):
            invalid.append(row_id)
            continue
        if not description or not category or tx_type not in VALID_TYPES or amount <= 0:
            invalid.append(row_id)
            continue

        payload: Dict[str, Any] = {}
        if description != str(old["description"]):
            payload["description"] = description
        if category != str(old["category"]).strip().lower():
            payload["category"] = category
        if tx_type != old["type"]:
            payload["type"] = tx_type
        if amount != round(float(old["amount"]), 2):
            payload["amount"] = amount
        if new_day != _as_date(old["date"]):
            payload["date"] = datetime.combine(new_day, time.min).isoformat()
        if payload:
            changes[row_id] = payload
    return changes, invalid
