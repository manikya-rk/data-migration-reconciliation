import pytest
from migrate.transform import clean_gstin, invoice_row, parse_amount, parse_date, parse_status, parse_terms


@pytest.mark.parametrize("raw", ["05/03/2024", "05-03-2024", "2024-03-05", "05.03.2024", "05-Mar-2024"])
def test_date_formats(raw):
    assert parse_date(raw).isoformat() == "2024-03-05"


@pytest.mark.parametrize("raw", ["31/02/2019", "2026-13-05", "", "1985-01-01"])
def test_bad_dates(raw):
    with pytest.raises(ValueError):
        parse_date(raw)


@pytest.mark.parametrize("raw,val", [("1,25,000.50", 125000.5), ("Rs.4,500.00", 4500.0), ("99.999", 100.0)])
def test_amounts(raw, val):
    assert parse_amount(raw) == val


@pytest.mark.parametrize("raw", ["0.00", "12,45O.00", "-10"])
def test_bad_amounts(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


@pytest.mark.parametrize("raw,days", [("NET30", 30), ("30", 30), ("Net 45", 45), ("15 days", 15), ("IMMEDIATE", 0)])
def test_terms(raw, days):
    assert parse_terms(raw) == days


def test_bad_term_status_gstin():
    with pytest.raises(ValueError):
        parse_terms("NET 75")
    with pytest.raises(ValueError):
        parse_status("X")
    with pytest.raises(ValueError):
        clean_gstin("29ABCDE1234")
    assert clean_gstin("NA") is None and clean_gstin("27aapfu0939f1zv") == "27AAPFU0939F1ZV"


def test_invoice_due_date_default_and_unknown_vendor():
    row = invoice_row({"INV_NO": " inv/1 ", "VEND_CD": "vn1", "INV_DT": "01/01/2026", "DUE_DAYS": "", "AMT": "100"},
                      {"VN1": "V-000001"})
    assert row["invoice_id"] == "INV/1" and row["due_date"] == "2026-01-31"
    with pytest.raises(ValueError):
        invoice_row({"INV_NO": "x", "VEND_CD": "VN2", "INV_DT": "01/01/2026", "DUE_DAYS": "", "AMT": "1"}, {})
