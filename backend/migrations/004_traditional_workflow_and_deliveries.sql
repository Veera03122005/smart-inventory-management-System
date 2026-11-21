-- 004_traditional_workflow_and_deliveries.sql: Traditional Opening/Closing, Supplier Invoices, Staged Documents, and Depletion Logs
PRAGMA foreign_keys = ON;

-- 1. Daily Physical Stock Counts (Morning Opening & Evening Closing Observations)
CREATE TABLE IF NOT EXISTS daily_stock_counts (
    count_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    count_type TEXT NOT NULL CHECK(count_type IN ('AM_OPENING', 'PM_CLOSING')),
    physical_qty REAL NOT NULL CHECK(physical_qty >= 0),
    entered_by TEXT NOT NULL,
    verified_by TEXT,
    verified_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'VERIFIED', 'POSTED', 'REJECTED')),
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(date, ingredient_id, count_type)
);
CREATE INDEX IF NOT EXISTS ix_stock_counts_date_type ON daily_stock_counts(date, count_type);

-- 2. Supplier Invoices (Header)
CREATE TABLE IF NOT EXISTS supplier_invoices (
    invoice_id TEXT PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    invoice_no TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    total_amount_rs REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'VERIFIED', 'POSTED', 'REJECTED')),
    received_by TEXT NOT NULL,
    verified_by TEXT,
    verified_at TEXT,
    document_upload_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(supplier_name, invoice_no)
);
CREATE INDEX IF NOT EXISTS ix_supplier_invoices_date ON supplier_invoices(invoice_date);

-- 3. Supplier Invoice Line Items (Multi-ingredient deliveries with strict deduplication)
CREATE TABLE IF NOT EXISTS supplier_invoice_items (
    item_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES supplier_invoices(invoice_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    invoice_no TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    billed_qty REAL NOT NULL CHECK(billed_qty > 0),
    unit TEXT NOT NULL,
    unit_price_rs REAL NOT NULL DEFAULT 0.0,
    line_total_rs REAL NOT NULL DEFAULT 0.0,
    batch_no TEXT,
    expiry_date TEXT,
    transaction_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(supplier_name, invoice_no, ingredient_id)
);
CREATE INDEX IF NOT EXISTS ix_supplier_invoice_items_ing ON supplier_invoice_items(ingredient_id);

-- 4. Document Staging and Audit Trail (Zero unreviewed auto-posting)
CREATE TABLE IF NOT EXISTS document_uploads (
    upload_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER NOT NULL,
    workflow_type TEXT NOT NULL CHECK(workflow_type IN ('OPENING_STOCK', 'DELIVERY_INVOICE', 'CLOSING_STOCK')),
    status TEXT NOT NULL CHECK(status IN ('UPLOADED', 'EXTRACTED', 'EXTRACTION_FAILED', 'NEEDS_REVIEW', 'VERIFIED', 'POSTED', 'REJECTED')),
    extracted_payload TEXT NOT NULL,
    raw_document_path TEXT,
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_document_uploads_status ON document_uploads(status);

-- 5. Daily Depletion Logs (Preserving unclassified depletion for Manager investigation)
CREATE TABLE IF NOT EXISTS depletion_logs (
    depletion_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    opening_qty REAL NOT NULL,
    deliveries_qty REAL NOT NULL,
    closing_qty REAL NOT NULL,
    calculated_depletion_kg REAL NOT NULL,
    unexplained_depletion_kg REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('UNCLASSIFIED', 'INVESTIGATING', 'CLASSIFIED')),
    reconciliation_transaction_id TEXT,
    recorded_by TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    notes TEXT,
    UNIQUE(date, ingredient_id)
);
CREATE INDEX IF NOT EXISTS ix_depletion_logs_date ON depletion_logs(date);
