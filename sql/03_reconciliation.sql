-- name: record_counts
SELECT 'vendor' AS entity,
       (SELECT COUNT(*) FROM stg_vendor) AS source_rows,
       (SELECT COUNT(*) FROM vendor) AS target_rows,
       (SELECT COUNT(*) FROM migration_exception WHERE entity = 'vendor') AS exceptions
UNION ALL
SELECT 'open_invoice',
       (SELECT COUNT(*) FROM stg_invoice),
       (SELECT COUNT(*) FROM open_invoice),
       (SELECT COUNT(*) FROM migration_exception WHERE entity = 'open_invoice');

-- name: missing_in_target
-- source keys that neither reached the target nor were logged as an exception
SELECT 'vendor' AS entity, s.VEND_CD AS source_key
FROM stg_vendor s
LEFT JOIN vendor v ON v.legacy_code = UPPER(TRIM(s.VEND_CD))
LEFT JOIN migration_exception e ON e.entity = 'vendor' AND e.source_row = s.rowid
WHERE v.vendor_id IS NULL AND e.source_key IS NULL
UNION ALL
SELECT 'open_invoice', s.INV_NO
FROM stg_invoice s
LEFT JOIN open_invoice i ON i.invoice_id = UPPER(TRIM(s.INV_NO))
LEFT JOIN migration_exception e ON e.entity = 'open_invoice' AND e.source_row = s.rowid
WHERE i.invoice_id IS NULL AND e.source_key IS NULL;

-- name: control_totals_by_vendor
-- invoice amount totals per vendor must match between legacy and target (excluding exceptions)
WITH src AS (
    SELECT UPPER(TRIM(s.VEND_CD)) AS legacy_code,
           ROUND(SUM(CAST(REPLACE(REPLACE(s.AMT, ',', ''), 'Rs.', '') AS REAL)), 2) AS src_total,
           COUNT(*) AS src_count
    FROM stg_invoice s
    WHERE s.rowid NOT IN (SELECT source_row FROM migration_exception WHERE entity = 'open_invoice')
    GROUP BY 1
), tgt AS (
    SELECT v.legacy_code, ROUND(SUM(i.amount_inr), 2) AS tgt_total, COUNT(*) AS tgt_count
    FROM open_invoice i JOIN vendor v ON v.vendor_id = i.vendor_id
    GROUP BY 1
)
SELECT src.legacy_code, src_count, COALESCE(tgt_count, 0) AS tgt_count,
       src_total, COALESCE(tgt_total, 0) AS tgt_total,
       ROUND(src_total - COALESCE(tgt_total, 0), 2) AS difference
FROM src LEFT JOIN tgt USING (legacy_code)
WHERE ABS(src_total - COALESCE(tgt_total, 0)) > 0.005 OR src_count <> COALESCE(tgt_count, 0);

-- name: grand_totals
SELECT ROUND(SUM(CAST(REPLACE(REPLACE(AMT, ',', ''), 'Rs.', '') AS REAL)), 2) AS legacy_total,
       (SELECT ROUND(SUM(amount_inr), 2) FROM open_invoice) AS target_total,
       (SELECT ROUND(SUM(CAST(REPLACE(REPLACE(s.AMT, ',', ''), 'Rs.', '') AS REAL)), 2)
          FROM stg_invoice s JOIN migration_exception e
            ON e.entity = 'open_invoice' AND e.source_row = s.rowid) AS excluded_total
FROM stg_invoice;

-- name: orphan_invoices
SELECT i.invoice_id FROM open_invoice i LEFT JOIN vendor v ON v.vendor_id = i.vendor_id WHERE v.vendor_id IS NULL;

-- name: duplicate_vendor_gstin
SELECT gstin, COUNT(*) AS vendors, GROUP_CONCAT(vendor_id, ', ') AS vendor_ids
FROM vendor WHERE gstin IS NOT NULL GROUP BY gstin HAVING COUNT(*) > 1;

-- name: exceptions_by_reason
SELECT entity, reason, COUNT(*) AS n FROM migration_exception GROUP BY 1, 2 ORDER BY 1, 3 DESC;
