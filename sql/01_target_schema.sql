-- Target (new platform) schema
CREATE TABLE IF NOT EXISTS vendor (
    vendor_id      TEXT PRIMARY KEY,           -- V-000123
    legacy_code    TEXT NOT NULL UNIQUE,
    vendor_name    TEXT NOT NULL,
    gstin          TEXT,
    city           TEXT NOT NULL,
    payment_terms  INTEGER NOT NULL CHECK (payment_terms IN (0, 15, 30, 45, 60, 90)),
    is_active      INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    created_on     DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS open_invoice (
    invoice_id     TEXT PRIMARY KEY,
    vendor_id      TEXT NOT NULL REFERENCES vendor(vendor_id),
    invoice_date   DATE NOT NULL,
    due_date       DATE NOT NULL,
    amount_inr     NUMERIC(14, 2) NOT NULL CHECK (amount_inr > 0),
    currency       TEXT NOT NULL DEFAULT 'INR'
);

CREATE TABLE IF NOT EXISTS migration_exception (
    entity       TEXT NOT NULL,
    source_row   INTEGER NOT NULL,  -- rowid in the staging table
    source_key   TEXT NOT NULL,
    stage        TEXT NOT NULL,   -- transform | load
    reason       TEXT NOT NULL
);
