from datetime import datetime

from app import ofx_io

SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
CHARSET:1252

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261009120000[-3:BRT]
<TRNAMT>-150.50
<FITID>1
<MEMO>MERCADO CENTRAL
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261005
<TRNAMT>5000.00
<FITID>2
<NAME>SALARIO
<MEMO>EMPRESA X
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""

XML = """<?xml version="1.0"?><OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20261001</DTPOSTED><TRNAMT>-10,50</TRNAMT><NAME>Caf&amp;e</NAME><MEMO>Caf&amp;e</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


def test_parse_sgml_sign_decides_type_and_description_joins_name_and_memo():
    rows, errors = ofx_io.parse_ofx(SGML)
    assert errors == []
    assert rows[0] == {
        "description": "MERCADO CENTRAL", "amount": 150.5, "category": "geral",
        "type": "expense", "date": datetime(2026, 10, 9),
    }
    assert rows[1]["type"] == "income" and rows[1]["amount"] == 5000
    assert rows[1]["description"] == "SALARIO - EMPRESA X"
    assert rows[1]["date"] == datetime(2026, 10, 5)


def test_parse_xml_decimal_comma_entities_and_same_name_memo():
    rows, errors = ofx_io.parse_ofx(XML)
    assert errors == []
    assert rows[0]["amount"] == 10.5 and rows[0]["description"] == "Caf&e"


def test_parse_reports_bad_blocks_and_continues():
    text = (
        "<OFX><STMTTRN><DTPOSTED>20261001<TRNAMT>abc<NAME>x</STMTTRN>"
        "<STMTTRN><DTPOSTED>20261001<TRNAMT>0<NAME>zero</STMTTRN>"
        "<STMTTRN><TRNAMT>-5<NAME>sem data</STMTTRN>"
        "<STMTTRN><DTPOSTED>20261002<TRNAMT>-5<NAME>ok</STMTTRN></OFX>"
    )
    rows, errors = ofx_io.parse_ofx(text)
    assert [r["description"] for r in rows] == ["ok"]
    assert [e["row"] for e in errors] == [1, 2, 3]


def test_parse_without_transactions():
    rows, errors = ofx_io.parse_ofx("<OFX></OFX>")
    assert rows == [] and "STMTTRN" in errors[0]["error"]


def test_looks_like_ofx():
    assert ofx_io.looks_like_ofx("extrato.OFX", "qualquer coisa")
    assert ofx_io.looks_like_ofx("dados.txt", SGML)
    assert not ofx_io.looks_like_ofx("dados.csv", "descricao,valor\nA,1\n")
