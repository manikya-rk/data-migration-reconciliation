-- Raw legacy extracts are loaded as-is (all TEXT) so nothing is lost before transformation
CREATE TABLE IF NOT EXISTS stg_vendor (
    VEND_CD TEXT, VEND_NM TEXT, GST_NO TEXT, CITY TEXT, PAY_TERM TEXT, STATUS TEXT, CRT_DT TEXT);
CREATE TABLE IF NOT EXISTS stg_invoice (
    INV_NO TEXT, VEND_CD TEXT, INV_DT TEXT, DUE_DAYS TEXT, AMT TEXT);
