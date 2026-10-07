"""Extract -> stage -> transform -> load -> reconcile."""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .transform import invoice_row, vendor_row

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"


def read_queries(path: Path) -> dict[str, str]:
    queries, name, buf = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf)
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf)
    return queries


def stage(db, table: str, csv_path: Path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0])
    db.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                   [tuple(r[c] for c in cols) for r in rows])
    return rows


def migrate(legacy_dir: str, db_path: str) -> sqlite3.Connection:
    Path(db_path).unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys = ON")
    for f in ("01_target_schema.sql", "02_staging.sql"):
        db.executescript((SQL / f).read_text())

    legacy = Path(legacy_dir)
    vendors = stage(db, "stg_vendor", legacy / "VENDOR_MASTER.csv")
    invoices = stage(db, "stg_invoice", legacy / "OPEN_INVOICES.csv")

    def exception(entity, row_no, key, stage_, reason):
        db.execute("INSERT INTO migration_exception VALUES (?,?,?,?,?)", (entity, row_no, key, stage_, reason))

    vendor_ids, seq = {}, 0
    for row_no, src in enumerate(vendors, start=1):  # row_no == staging rowid
        try:
            if src["VEND_CD"].strip().upper() in vendor_ids:
                raise ValueError("duplicate vendor code in legacy extract")
            seq += 1
            row = vendor_row(src, seq)
            db.execute("INSERT INTO vendor VALUES (:vendor_id,:legacy_code,:vendor_name,:gstin,:city,"
                       ":payment_terms,:is_active,:created_on)", row)
            vendor_ids[row["legacy_code"]] = row["vendor_id"]
        except (ValueError, sqlite3.IntegrityError) as e:
            exception("vendor", row_no, src["VEND_CD"], "transform" if isinstance(e, ValueError) else "load", str(e))

    seen = set()
    for row_no, src in enumerate(invoices, start=1):
        try:
            key = src["INV_NO"].strip().upper()
            if key in seen:
                raise ValueError("duplicate invoice number in legacy extract")
            row = invoice_row(src, vendor_ids)
            db.execute("INSERT INTO open_invoice(invoice_id,vendor_id,invoice_date,due_date,amount_inr) "
                       "VALUES (:invoice_id,:vendor_id,:invoice_date,:due_date,:amount_inr)", row)
            seen.add(key)
        except (ValueError, sqlite3.IntegrityError) as e:
            exception("open_invoice", row_no, src["INV_NO"], "transform" if isinstance(e, ValueError) else "load", str(e))
    db.commit()
    return db


def reconcile(db) -> dict:
    q = read_queries(SQL / "03_reconciliation.sql")
    def run(name):
        cur = db.execute(q[name])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    res = {name: run(name) for name in q}
    g = res["grand_totals"][0]
    res["checks"] = {
        "Every source record is migrated or logged as an exception": not res["missing_in_target"],
        "Record counts balance (source = target + exceptions)":
            all(r["source_rows"] == r["target_rows"] + r["exceptions"] for r in res["record_counts"]),
        "Invoice control totals match per vendor": not res["control_totals_by_vendor"],
        "Grand total balances (legacy = target + excluded)":
            abs(g["legacy_total"] - g["target_total"] - (g["excluded_total"] or 0)) < 0.01,
        "No orphan invoices": not res["orphan_invoices"],
    }
    return res


def write_report(res: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = all(res["checks"].values())
    g = res["grand_totals"][0]
    inr = lambda v: f"₹{v:,.2f}"
    L = ["# Migration reconciliation report", "",
         f"_Generated {datetime.now():%d %b %Y %H:%M}_ · **Result: {'PASS ✅' if ok else 'FAIL ❌'}**", "",
         "## Checks", "", "| Check | Result |", "|---|---|"]
    L += [f"| {k} | {'✅' if v else '❌'} |" for k, v in res["checks"].items()]
    L += ["", "## Record counts", "", "| Entity | Source | Migrated | Exceptions |", "|---|---|---|---|"]
    L += [f"| {r['entity']} | {r['source_rows']} | {r['target_rows']} | {r['exceptions']} |" for r in res["record_counts"]]
    L += ["", "## Financial control totals", "", "| Legacy total | Migrated | Held back (exceptions) |", "|---|---|---|",
          f"| {inr(g['legacy_total'])} | {inr(g['target_total'])} | {inr(g['excluded_total'] or 0)} |"]
    if res["duplicate_vendor_gstin"]:
        L += ["", "## Warnings", "", "Vendors sharing a GSTIN (possible duplicates to review):", ""]
        L += [f"- `{r['gstin']}`: {r['vendor_ids']}" for r in res["duplicate_vendor_gstin"]]
    L += ["", "## Exceptions by reason", "", "| Entity | Reason | Count |", "|---|---|---|"]
    L += [f"| {r['entity']} | {r['reason']} | {r['n']} |" for r in res["exceptions_by_reason"]]
    (out_dir / "reconciliation_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return ok


def export_exceptions(db, out_dir: Path):
    rows = db.execute("SELECT entity, source_row, source_key, stage, reason FROM migration_exception ORDER BY entity, source_row").fetchall()
    with open(out_dir / "exceptions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity", "source_row", "source_key", "stage", "reason"])
        w.writerows(rows)
