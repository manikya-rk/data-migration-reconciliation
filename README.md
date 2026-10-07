# Data Migration & Reconciliation Toolkit

An extract → stage → transform → load → **reconcile** toolkit for moving master and transactional data from a legacy system to a new platform. Its focus is proving that the migration is complete and that the money balances, so that go-live sign-off rests on evidence instead of spot checks.

> Personal demo project using **synthetic legacy data** (vendor master + open invoices). It shows how I approach data migration for client go-lives. It contains no client code or data.

## The problem

Legacy exports are messy:

- five different date formats
- amounts like `Rs.1,25,000.00`
- payment terms typed as `NET30`, `30`, `Net 45` or `15 days`
- padded or lower-case codes
- duplicate rows

A migration that silently drops a few rows, or changes an invoice amount, can pass a quick visual check and still break finance on day one.

## Approach

1. **Stage raw.** Legacy CSVs are loaded as-is into `stg_*` tables (all TEXT), so nothing is lost before transformation.
2. **Transform.** Rule-based conversions handle dates, amounts, payment terms, status flags, GSTIN clean-up and name/city formatting, and the due date is derived from the invoice date. Any row that can't be converted becomes a **logged exception** with the exact staging row and reason; nothing is dropped silently.
3. **Load.** Rows go into the target schema, which enforces keys, foreign keys and CHECK constraints.
4. **Reconcile in SQL** (`sql/03_reconciliation.sql`):

| Check | What it proves |
|---|---|
| Source = migrated + exceptions | Record counts balance per entity |
| No unaccounted source keys | Every legacy row either arrived or has a logged reason |
| Invoice control totals per vendor | Count and ₹ total match vendor-by-vendor |
| Grand total | Legacy ₹ = migrated ₹ + held-back ₹ |
| No orphan invoices | Referential integrity in the target |
| Shared GSTINs (warning) | Possible duplicate vendors for the business to review |

## Run it

```bash
python -m migrate
```

```
vendor        source   61 | migrated   56 | exceptions   5
open_invoice  source  197 | migrated  177 | exceptions  20
  [PASS] Every source record is migrated or logged as an exception
  [PASS] Record counts balance (source = target + exceptions)
  [PASS] Invoice control totals match per vendor
  [PASS] Grand total balances (legacy = target + excluded)
  [PASS] No orphan invoices
```

The exit code is non-zero if any check fails, so it can gate a cutover script or a CI job.

Outputs in `out/`:

- `reconciliation_report.md`: the sign-off report (checks, counts, ₹ control totals, warnings, exceptions by reason)
- `exceptions.csv`: every rejected row with its staging row number and reason, ready to send to the client for correction
- `target.db`: the migrated SQLite database

From the sample report:

| Legacy total | Migrated | Held back (exceptions) |
|---|---|---|
| ₹83,144,220.09 | ₹76,233,304.91 | ₹6,910,915.18 |

## Tests

```bash
python -m pytest -q      # 26 passed
```

Besides the transformation rules, the tests deliberately **break** the migration and check that reconciliation catches it:

- a silently deleted invoice
- an amount changed by ₹1

## Project structure

```
sql/
  01_target_schema.sql      target tables with PK / FK / CHECK constraints + exception log
  02_staging.sql            raw staging tables
  03_reconciliation.sql     named reconciliation queries
migrate/
  transform.py              legacy → target conversion rules
  run.py                    stage, transform, load, reconcile, report
scripts/make_legacy_data.py synthetic messy legacy extracts
data/legacy/                VENDOR_MASTER.csv, OPEN_INVOICES.csv
tests/
```

## Tech

Python 3.10+ (standard library) · SQL (SQLite; the schema and queries port to PostgreSQL/MySQL) · pytest
