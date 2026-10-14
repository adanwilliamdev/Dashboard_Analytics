"""Leitura tolerante de CSV de transacoes (pt-BR e en)."""
import csv
import hashlib
import io
from datetime import datetime
from typing import Any, Dict, List, Tuple

MAX_ROWS = 5000
MAX_BYTES = 2 * 1024 * 1024

_ALIASES = {
    "description": {"description", "descricao", "descrição", "historico", "histórico", "nome"},
    "amount": {"amount", "valor", "value"},
    "category": {"category", "categoria"},
    "type": {"type", "tipo"},
    "date": {"date", "data"},
}
_TYPE_MAP = {
    "income": "income", "receita": "income", "entrada": "income", "credito": "income",
    "crédito": "income", "c": "income",
    "expense": "expense", "despesa": "expense", "saida": "expense", "saída": "expense",
    "debito": "expense", "débito": "expense", "d": "expense",
}
_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d/%m/%Y %H:%M", "%d-%m-%Y")


def row_fingerprint(when: datetime, amount: float, description: str, tx_type: str) -> str:
    """Hash estavel de (dia + valor + descricao + tipo), usado para nao importar a mesma linha duas vezes.

    Ignora a hora, caixa e espacos repetidos: o mesmo lancamento exportado duas vezes pelo banco
    (ou um CSV reimportado) gera o mesmo hash. O tipo entra para que um estorno (mesmo valor e
    descricao, sentido oposto) nao seja confundido com o lancamento original.
    """
    key = "|".join(
        [
            when.strftime("%Y-%m-%d"),
            f"{float(amount):.2f}",
            " ".join(description.casefold().split()),
            tx_type,
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_amount(raw: str) -> float:
    """Aceita '1234.56', '1.234,56', 'R$ 1.234,56' e '-50' (sinal e ignorado)."""
    s = raw.strip().replace("R$", "").replace(" ", "")
    if not s:
        raise ValueError("valor vazio")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    value = abs(float(s))
    if value <= 0:
        raise ValueError("valor deve ser maior que zero")
    return value


def parse_date(raw: str) -> datetime:
    s = raw.strip()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"data invalida: {raw!r}")


def _canonical_headers(fieldnames: List[str]) -> Dict[str, str]:
    mapping = {}
    for original in fieldnames or []:
        key = (original or "").strip().lower()
        for canonical, names in _ALIASES.items():
            if key in names:
                mapping[original] = canonical
    return mapping


def parse_transactions_csv(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retorna (linhas_validas, erros). Cada erro: {'row': n, 'error': msg}."""
    text = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = _canonical_headers(reader.fieldnames or [])
    missing = {"description", "amount"} - set(headers.values())
    if missing:
        return [], [{"row": 1, "error": "Colunas obrigatorias ausentes: " + ", ".join(sorted(missing))}]

    rows, errors = [], []
    for n, raw in enumerate(reader, start=2):  # linha 1 = cabecalho
        if n - 1 > MAX_ROWS:
            errors.append({"row": n, "error": f"Limite de {MAX_ROWS} linhas excedido"})
            break
        row = {headers[k]: (v or "").strip() for k, v in raw.items() if k in headers}
        if not any(row.values()):
            continue
        try:
            tx_type = _TYPE_MAP.get(row.get("type", "").lower(), None) if row.get("type") else None
            if row.get("type") and tx_type is None:
                raise ValueError(f"tipo invalido: {row['type']!r}")
            amount_raw = row.get("amount", "")
            if tx_type is None:  # sem coluna tipo: usa o sinal do valor
                tx_type = "income" if amount_raw.strip().startswith("+") else "expense"
            rows.append(
                {
                    "description": row.get("description", ""),
                    "amount": parse_amount(amount_raw),
                    "category": row.get("category") or "geral",
                    "type": tx_type,
                    "date": parse_date(row["date"]) if row.get("date") else None,
                }
            )
        except ValueError as exc:
            errors.append({"row": n, "error": str(exc)})
    return rows, errors
