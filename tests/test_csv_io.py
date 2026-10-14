from datetime import datetime

import pytest

from app import csv_io


def test_parse_amount_formats():
    assert csv_io.parse_amount("1234.56") == 1234.56
    assert csv_io.parse_amount("1.234,56") == 1234.56
    assert csv_io.parse_amount("R$ 99,90") == 99.90
    assert csv_io.parse_amount("-50") == 50
    with pytest.raises(ValueError):
        csv_io.parse_amount("0")
    with pytest.raises(ValueError):
        csv_io.parse_amount("abc")


def test_parse_date_formats():
    assert csv_io.parse_date("2026-10-09") == datetime(2026, 10, 9)
    assert csv_io.parse_date("09/10/2026") == datetime(2026, 10, 9)
    with pytest.raises(ValueError):
        csv_io.parse_date("ontem")


def test_parse_csv_portuguese_semicolon():
    text = "descricao;valor;categoria;tipo;data\nMercado;150,50;Alimentacao;despesa;09/10/2026\nSalario;5.000,00;salario;receita;05/10/2026\n"
    rows, errors = csv_io.parse_transactions_csv(text)
    assert errors == []
    assert rows[0]["amount"] == 150.5 and rows[0]["type"] == "expense"
    assert rows[1]["amount"] == 5000 and rows[1]["type"] == "income"
    assert rows[1]["date"] == datetime(2026, 10, 5)


def test_parse_csv_reports_bad_rows_and_continues():
    text = "description,amount,type\nOk,10,expense\nRuim,xx,expense\nTipoErrado,5,foo\n"
    rows, errors = csv_io.parse_transactions_csv(text)
    assert len(rows) == 1
    assert [e["row"] for e in errors] == [3, 4]


def test_parse_csv_missing_columns():
    rows, errors = csv_io.parse_transactions_csv("foo,bar\n1,2\n")
    assert rows == [] and "obrigatorias" in errors[0]["error"]


def test_parse_csv_bom_and_blank_lines():
    rows, errors = csv_io.parse_transactions_csv("\ufeffdescription,amount\nA,1\n,\n\nB,2\n")
    assert [r["description"] for r in rows] == ["A", "B"] and errors == []


def test_row_fingerprint_ignores_time_case_and_spaces_but_not_type():
    a = csv_io.row_fingerprint(datetime(2026, 10, 9, 18, 30), 150.5, "Mercado  Central", "expense")
    b = csv_io.row_fingerprint(datetime(2026, 10, 9), 150.50, " mercado central ", "expense")
    assert a == b
    assert a != csv_io.row_fingerprint(datetime(2026, 10, 10), 150.5, "Mercado Central", "expense")  # outro dia
    assert a != csv_io.row_fingerprint(datetime(2026, 10, 9), 150.51, "Mercado Central", "expense")  # outro valor
    assert a != csv_io.row_fingerprint(datetime(2026, 10, 9), 150.5, "Mercado Central", "income")  # estorno
