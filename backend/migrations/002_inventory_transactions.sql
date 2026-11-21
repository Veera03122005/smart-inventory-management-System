-- 002_inventory_transactions.sql: Append-only transaction journal and balance projection
CREATE TABLE IF NOT EXISTS inventory_transactions (
    transaction_id TEXT PRIMARY KEY,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    quantity REAL NOT NULL CHECK (quantity >= 0),
    delta_qty REAL NOT NULL,
    unit TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN (
        'STOCK_IN', 'TRANSFER', 'CONSUMPTION', 'WASTAGE',
        'STOCK_COUNT', 'ADJUSTMENT', 'REVERSAL', 'REFILL'
    )),
    source_channel TEXT NOT NULL,
    reference_id TEXT,
    batch_no TEXT,
    expiry_date TEXT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    reversal_ref_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS ix_tx_ing_ts ON inventory_transactions(ingredient_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_tx_ref ON inventory_transactions(reference_id);
CREATE INDEX IF NOT EXISTS ix_tx_idemp ON inventory_transactions(idempotency_key);

-- Immutability triggers: prevent any application-level UPDATE or DELETE on posted records
CREATE TRIGGER IF NOT EXISTS trg_prevent_tx_update
BEFORE UPDATE ON inventory_transactions
BEGIN
    SELECT RAISE(FAIL, 'Posted inventory transactions are immutable and cannot be updated.');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_tx_delete
BEFORE DELETE ON inventory_transactions
BEGIN
    SELECT RAISE(FAIL, 'Posted inventory transactions are immutable and cannot be deleted.');
END;

-- Balance projection table for fast querying with transactional consistency
CREATE TABLE IF NOT EXISTS inventory_balances (
    ingredient_id TEXT PRIMARY KEY REFERENCES ingredients(ingredient_id),
    book_balance REAL NOT NULL DEFAULT 0,
    last_transaction_id TEXT,
    last_updated_at TEXT NOT NULL
);
