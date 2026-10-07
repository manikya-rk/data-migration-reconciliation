import argparse
import sys
from pathlib import Path

from .run import export_exceptions, migrate, reconcile, write_report

p = argparse.ArgumentParser(description="Migrate legacy vendor + invoice data and reconcile")
p.add_argument("--legacy", default="data/legacy")
p.add_argument("--db", default="out/target.db")
p.add_argument("--out", default="out")
a = p.parse_args()
Path(a.out).mkdir(parents=True, exist_ok=True)
db = migrate(a.legacy, a.db)
res = reconcile(db)
ok = write_report(res, Path(a.out))
export_exceptions(db, Path(a.out))
for r in res["record_counts"]:
    print(f"{r['entity']:<13} source {r['source_rows']:>4} | migrated {r['target_rows']:>4} | exceptions {r['exceptions']:>3}")
for k, v in res["checks"].items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print(f"Report: {a.out}/reconciliation_report.md  Exceptions: {a.out}/exceptions.csv")
sys.exit(0 if ok else 1)
