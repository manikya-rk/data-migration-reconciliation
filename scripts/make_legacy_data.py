"""Generate messy synthetic legacy extracts (the kind of data an old system really exports)."""
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
random.seed(11)
OUT = Path(__file__).resolve().parents[1] / "data" / "legacy"
CITIES = ["BANGALORE", "Mumbai", "pune", "Chennai ", "HYDERABAD", "New Delhi", "Kolkata", "ahmedabad"]
TERMS = ["NET30", "30", "Net 45", "NET60", "IMMEDIATE", "15 days", "NET90"]
STATUS = ["A", "Active", "Y", "I", "A", "A"]
FMTS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%b-%Y"]
C = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin():
    body = random.choice(["29", "27", "33", "36", "07"]) + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5)) \
        + f"{random.randint(1000, 9999)}" + random.choice("ABCDEFG") + "1Z"
    s = 0
    for i, ch in enumerate(body):
        p = C.index(ch) * (1 if i % 2 == 0 else 2)
        s += p // 36 + p % 36
    return body + C[(36 - s % 36) % 36]


def d(day: date) -> str:
    return day.strftime(random.choice(FMTS))


vendors = []
for i in range(1, 61):
    vendors.append({
        "VEND_CD": f"VN{i:04d}" if i % 7 else f" vn{i:04d} ",   # some padded / lowercase codes
        "VEND_NM": random.choice(["SHREE BALAJI SUPPLIERS", "Kaveri Packaging Pvt Ltd", "NORTHWIND ENGINEERING",
                                  "Lotus Office Solutions", "DECCAN FREIGHT CARRIERS", "Sahyadri Agro Inputs"]) + f" {i}",
        "GST_NO": gstin() if i % 5 else random.choice(["NA", "", gstin().lower()]),
        "CITY": random.choice(CITIES),
        "PAY_TERM": random.choice(TERMS),
        "STATUS": random.choice(STATUS),
        "CRT_DT": d(date(2012, 1, 1) + timedelta(days=random.randint(0, 4000))),
    })
# problems
vendors[8]["PAY_TERM"] = "NET 75"                 # unsupported term
vendors[17]["VEND_NM"] = "   "                    # blank name
vendors[23]["CRT_DT"] = "31/02/2019"              # impossible date
vendors[31]["GST_NO"] = "29ABCDE1234"             # truncated GSTIN
vendors[41]["GST_NO"] = vendors[42]["GST_NO"]     # same GSTIN on two vendors -> warning only
vendors.append(dict(vendors[5]))                  # duplicate row in extract

invoices = []
n = 0
for v in vendors[:60]:
    for _ in range(random.randint(1, 5)):
        n += 1
        amt = round(random.uniform(1500, 950000), 2)
        invoices.append({
            "INV_NO": f"INV/{2026}/{n:05d}",
            "VEND_CD": v["VEND_CD"],
            "INV_DT": d(date(2026, 1, 1) + timedelta(days=random.randint(0, 240))),
            "DUE_DAYS": random.choice(["30", "45", "60", ""]),
            "AMT": random.choice([f"{amt:,.2f}", f"{amt:.2f}", f"Rs.{amt:,.2f}"]),
        })
invoices[4]["AMT"] = "0.00"                       # zero amount
invoices[12]["AMT"] = "12,45O.00"                 # letter O typed for zero
invoices[20]["INV_DT"] = "2026-13-05"             # bad month
invoices.append(dict(invoices[30]))               # duplicate invoice
invoices.append({"INV_NO": "INV/2026/99999", "VEND_CD": "VN9999", "INV_DT": "01/04/2026", "DUE_DAYS": "30",
                 "AMT": "45,000.00"})             # vendor that doesn't exist

OUT.mkdir(parents=True, exist_ok=True)
for name, rows in (("VENDOR_MASTER.csv", vendors), ("OPEN_INVOICES.csv", invoices)):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
print(f"{len(vendors)} vendors, {len(invoices)} invoices written to {OUT}")
