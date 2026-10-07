"""Transformation rules: legacy formats -> target formats. Each function raises ValueError with a readable reason."""
import re
from datetime import date, datetime, timedelta

DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%b-%Y", "%d%m%Y")
TERMS = {"IMMEDIATE": 0, "NET15": 15, "NET30": 30, "NET45": 45, "NET60": 60, "NET90": 90}
STATUS = {"A": 1, "ACTIVE": 1, "Y": 1, "I": 0, "INACTIVE": 0, "N": 0, "BLOCKED": 0}
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def parse_date(raw: str) -> date:
    s = (raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if not (date(1990, 1, 1) <= d <= date(2030, 12, 31)):
            raise ValueError(f"date '{raw}' is out of range")
        return d
    raise ValueError(f"unrecognised date '{raw}'")


def parse_amount(raw: str) -> float:
    s = (raw or "").replace(",", "").replace("Rs.", "").replace("INR", "").strip()
    try:
        v = round(float(s), 2)
    except ValueError:
        raise ValueError(f"amount '{raw}' is not numeric")
    if v <= 0:
        raise ValueError(f"amount '{raw}' must be positive")
    return v


def parse_terms(raw: str) -> int:
    s = (raw or "").upper().replace(" ", "").replace("DAYS", "")
    if s.isdigit() and int(s) in TERMS.values():
        return int(s)
    if s in TERMS:
        return TERMS[s]
    raise ValueError(f"unknown payment term '{raw}'")


def parse_status(raw: str) -> int:
    s = (raw or "").strip().upper()
    if s not in STATUS:
        raise ValueError(f"unknown status '{raw}'")
    return STATUS[s]


def clean_gstin(raw: str) -> str | None:
    s = (raw or "").strip().upper().replace(" ", "")
    if s in ("", "NA", "N/A", "-"):
        return None
    if not GSTIN_RE.match(s):
        raise ValueError(f"gstin '{raw}' is invalid")
    return s


def vendor_row(src: dict, seq: int) -> dict:
    name = " ".join((src["VEND_NM"] or "").split())
    if not name:
        raise ValueError("vendor name is empty")
    return {
        "vendor_id": f"V-{seq:06d}",
        "legacy_code": src["VEND_CD"].strip().upper(),
        "vendor_name": name.title() if name.isupper() else name,
        "gstin": clean_gstin(src["GST_NO"]),
        "city": (src["CITY"] or "").strip().title() or "Unknown",
        "payment_terms": parse_terms(src["PAY_TERM"]),
        "is_active": parse_status(src["STATUS"]),
        "created_on": parse_date(src["CRT_DT"]).isoformat(),
    }


def invoice_row(src: dict, vendor_ids: dict) -> dict:
    code = src["VEND_CD"].strip().upper()
    if code not in vendor_ids:
        raise ValueError(f"vendor '{code}' was not migrated")
    inv_date = parse_date(src["INV_DT"])
    days = int(src["DUE_DAYS"]) if (src["DUE_DAYS"] or "").strip().isdigit() else 30
    return {
        "invoice_id": src["INV_NO"].strip().upper(),
        "vendor_id": vendor_ids[code],
        "invoice_date": inv_date.isoformat(),
        "due_date": (inv_date + timedelta(days=days)).isoformat(),
        "amount_inr": parse_amount(src["AMT"]),
    }
