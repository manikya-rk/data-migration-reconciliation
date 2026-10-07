import csv
import shutil
from pathlib import Path

from migrate.run import migrate, reconcile

LEGACY = Path(__file__).resolve().parents[1] / "data" / "legacy"


def test_sample_migration_passes_all_checks(tmp_path):
    db = migrate(str(LEGACY), str(tmp_path / "t.db"))
    res = reconcile(db)
    assert all(res["checks"].values()), res["checks"]
    counts = {r["entity"]: r for r in res["record_counts"]}
    assert counts["vendor"]["exceptions"] == 5
    assert res["duplicate_vendor_gstin"]


def test_reconciliation_detects_a_silently_dropped_record(tmp_path):
    db = migrate(str(LEGACY), str(tmp_path / "t.db"))
    # simulate a bug in the load step: an invoice vanishes without an exception being logged
    db.execute("DELETE FROM open_invoice WHERE invoice_id = (SELECT MIN(invoice_id) FROM open_invoice)")
    res = reconcile(db)
    assert res["missing_in_target"]
    assert not res["checks"]["Invoice control totals match per vendor"]
    assert not res["checks"]["Grand total balances (legacy = target + excluded)"]


def test_reconciliation_detects_amount_drift(tmp_path):
    db = migrate(str(LEGACY), str(tmp_path / "t.db"))
    db.execute("UPDATE open_invoice SET amount_inr = amount_inr + 1 WHERE rowid = 1")
    res = reconcile(db)
    assert len(res["control_totals_by_vendor"]) == 1
    assert res["control_totals_by_vendor"][0]["difference"] == -1.0


def test_clean_extract_has_no_exceptions(tmp_path):
    src = tmp_path / "legacy"
    src.mkdir()
    for name, rows in {
        "VENDOR_MASTER.csv": [{"VEND_CD": "VN1", "VEND_NM": "A", "GST_NO": "", "CITY": "Pune", "PAY_TERM": "NET30",
                               "STATUS": "A", "CRT_DT": "01/01/2020"}],
        "OPEN_INVOICES.csv": [{"INV_NO": "I1", "VEND_CD": "VN1", "INV_DT": "01/01/2026", "DUE_DAYS": "30", "AMT": "1,000.00"}],
    }.items():
        with open(src / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    res = reconcile(migrate(str(src), str(tmp_path / "t.db")))
    assert all(res["checks"].values()) and not res["exceptions_by_reason"]
