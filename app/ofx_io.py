"""Leitura tolerante de extratos OFX (SGML da v1.x e XML da v2.x).

Le apenas os blocos <STMTTRN> (conta corrente e cartao), que e o que importa para o dashboard.
Valores negativos viram despesa; positivos, receita. A data usa so o dia (a hora/fuso do OFX e
ignorada para o lancamento nao "pular" de dia na conversao de fuso).
"""
import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.csv_io import MAX_ROWS

_BLOCK = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>|\Z)", re.I | re.S)


def looks_like_ofx(filename: Optional[str], text: str) -> bool:
    """Extensao .ofx/.qfx ou cabecalho/tag tipicos no inicio do arquivo."""
    if filename and filename.lower().endswith((".ofx", ".qfx")):
        return True
    head = text[:2000].upper()
    return "OFXHEADER" in head or "<OFX>" in head


def _field(block: str, tag: str) -> Optional[str]:
    # SGML (sem tag de fechamento): o valor vai ate a proxima "<" ou quebra de linha
    m = re.search(r"<" + tag + r">\s*([^<\r\n]*)", block, re.I)
    if not m:
        return None
    value = html.unescape(m.group(1)).strip()
    return value or None


def _parse_date(raw: str) -> datetime:
    digits = re.match(r"(\d{8})", raw.strip())
    if not digits:
        raise ValueError(f"data invalida: {raw!r}")
    return datetime.strptime(digits.group(1), "%Y%m%d")


def _parse_amount(raw: str) -> float:
    s = raw.strip().replace(" ", "")
    if "," in s and "." not in s:  # alguns bancos exportam "-10,50"
        s = s.replace(",", ".")
    elif "," in s:  # "1,234.56"
        s = s.replace(",", "")
    return float(s)


def parse_ofx(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retorna (linhas_validas, erros) no mesmo formato de csv_io.parse_transactions_csv."""
    blocks = _BLOCK.findall(text)
    if not blocks:
        return [], [{"row": 1, "error": "Nenhuma transacao (STMTTRN) encontrada no arquivo OFX"}]

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for n, block in enumerate(blocks, start=1):
        if n > MAX_ROWS:
            errors.append({"row": n, "error": f"Limite de {MAX_ROWS} transacoes excedido"})
            break
        try:
            raw_amount = _field(block, "TRNAMT")
            raw_date = _field(block, "DTPOSTED") or _field(block, "DTUSER")
            if raw_amount is None:
                raise ValueError("TRNAMT ausente")
            if raw_date is None:
                raise ValueError("DTPOSTED ausente")
            amount = _parse_amount(raw_amount)
            if amount == 0:
                raise ValueError("valor deve ser maior que zero")

            name, memo = _field(block, "NAME"), _field(block, "MEMO")
            if name and memo and memo.casefold() != name.casefold():
                description = f"{name} - {memo}"
            else:
                description = name or memo or _field(block, "TRNTYPE") or "Transacao OFX"
            rows.append(
                {
                    "description": description[:200],
                    "amount": abs(amount),
                    "category": "geral",
                    "type": "income" if amount > 0 else "expense",
                    "date": _parse_date(raw_date),
                }
            )
        except ValueError as exc:
            errors.append({"row": n, "error": str(exc)})
    return rows, errors
