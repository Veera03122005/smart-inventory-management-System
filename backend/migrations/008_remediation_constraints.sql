-- SmartStock AI — Migration 008: Database Constraints for Refill Sessions and Supplier Invoices
PRAGMA foreign_keys = ON;

-- 1. Prevent multiple simultaneously open refill sessions for the same physical device
CREATE UNIQUE INDEX IF NOT EXISTS uq_refill_open_device
ON refill_sessions(device_id) WHERE status = 'OPEN';

-- 2. Prevent duplicate delivery line items for the same supplier, invoice, and ingredient
-- Treats NULL and empty strings identically for batch_no and expiry_date
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_items_dedup
ON supplier_invoice_items(
    supplier_name,
    invoice_no,
    ingredient_id,
    COALESCE(batch_no, ''),
    COALESCE(expiry_date, '')
);
