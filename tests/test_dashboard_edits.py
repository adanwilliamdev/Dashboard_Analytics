import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from tx_edits import diff_rows  # noqa: E402

OLD = [
    {"id": 1, "date": date(2026, 10, 9), "description": "Mercado", "category": "alimentacao",
     "type": "expense", "amount": 150.5},
    {"id": 2, "date": date(2026, 10, 5), "description": "Salario", "category": "salario",
     "type": "income", "amount": 5000.0},
]


def _edited(**changes_by_id):
    rows = [dict(r) for r in OLD]
    for row in rows:
        row.update(changes_by_id.get(row["id"], {}))
    return rows


def test_no_changes():
    assert diff_rows(OLD, _edited()) == ({}, [])


def test_only_changed_fields_are_sent():
    edited = _edited()
    edited[0].update(description="  Mercado Central ", amount=151.0, category=" Mercado ")
    edited[1].update(date=datetime(2026, 10, 6, 13, 30), type="expense")
    changes, invalid = diff_rows(OLD, edited)
    assert invalid == []
    assert changes[1] == {"description": "Mercado Central", "category": "mercado", "amount": 151.0}
    assert changes[2] == {"type": "expense", "date": "2026-10-06T00:00:00"}


def test_amount_rounding_noise_is_not_a_change():
    edited = _edited()
    edited[0]["amount"] = 150.50000001
    assert diff_rows(OLD, edited) == ({}, [])


def test_date_given_as_string_or_same_day_timestamp():
    edited = _edited()
    edited[0]["date"] = "2026-10-09"
    edited[1]["date"] = datetime(2026, 10, 5, 23, 59)  # mesmo dia: nao altera
    assert diff_rows(OLD, edited) == ({}, [])


def test_invalid_rows_are_reported_and_not_sent():
    edited = _edited()
    edited[0]["description"] = "   "
    edited[1]["amount"] = float("nan")
    assert diff_rows(OLD, edited) == ({}, [1, 2])

    edited = _edited()
    edited[0]["amount"] = -3
    edited[1]["type"] = "transfer"
    assert diff_rows(OLD, edited) == ({}, [1, 2])

    edited = _edited()
    edited[0]["category"] = None
    assert diff_rows(OLD, edited) == ({}, [1])


def test_unknown_ids_are_ignored():
    edited = _edited() + [{"id": 99, "date": date(2026, 1, 1), "description": "x", "category": "y",
                           "type": "expense", "amount": 1}]
    assert diff_rows(OLD, edited) == ({}, [])
