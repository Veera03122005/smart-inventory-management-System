-- SmartStock AI — Migration 005: Multi-Batch Deliveries Support
-- Rebuilds supplier_invoice_items to allow distinct batches of the same ingredient on one invoice
-- Replaces UNIQUE(supplier_name, invoice_no, ingredient_id) with UNIQUE(supplier_name, invoice_no, ingredient_id, batch_no, expiry_date)

CREATE TABLE IF NOT EXISTS supplier_invoice_items_new (
    item_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES supplier_invoices(invoice_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    invoice_no TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    billed_qty REAL NOT NULL CHECK(billed_qty > 0),
    unit TEXT NOT NULL,
    inventory_qty REAL,
    unit_price_rs REAL NOT NULL DEFAULT 0.0,
    line_total_rs REAL NOT NULL DEFAULT 0.0,
    batch_no TEXT,
    expiry_date TEXT,
    transaction_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(supplier_name, invoice_no, ingredient_id, batch_no, expiry_date)
);

INSERT INTO supplier_invoice_items_new (
    item_id, invoice_id, supplier_name, invoice_no, ingredient_id,
    billed_qty, unit, unit_price_rs, line_total_rs, batch_no, expiry_date, transaction_id, created_at
)
SELECT item_id, invoice_id, supplier_name, invoice_no, ingredient_id,
       billed_qty, unit, unit_price_rs, line_total_rs, batch_no, expiry_date, transaction_id, created_at
FROM supplier_invoice_items;

DROP TABLE supplier_invoice_items;
ALTER TABLE supplier_invoice_items_new RENAME TO supplier_invoice_items;
CREATE INDEX IF NOT EXISTS ix_supplier_invoice_items_ing ON supplier_invoice_items(ingredient_id);
