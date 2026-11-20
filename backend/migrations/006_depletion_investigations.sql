-- SmartStock AI — Migration 006: Manager Depletion Investigation & Zero-Sum Wastage Classification
PRAGMA foreign_keys = OFF;

-- 1. Extend inventory_transactions CHECK constraint to include 'RECLASSIFICATION'
CREATE TABLE IF NOT EXISTS inventory_transactions_new (
    transaction_id TEXT PRIMARY KEY,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    quantity REAL NOT NULL CHECK (quantity >= 0),
    delta_qty REAL NOT NULL,
    unit TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN (
        'STOCK_IN', 'TRANSFER', 'CONSUMPTION', 'WASTAGE',
        'STOCK_COUNT', 'ADJUSTMENT', 'REVERSAL', 'REFILL', 'RECLASSIFICATION'
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

INSERT INTO inventory_transactions_new (
    transaction_id, ingredient_id, quantity, delta_qty, unit,
    transaction_type, source_channel, reference_id, batch_no,
    expiry_date, timestamp, actor, idempotency_key, reversal_ref_id, notes, created_at
)
SELECT transaction_id, ingredient_id, quantity, delta_qty, unit,
       transaction_type, source_channel, reference_id, batch_no,
       expiry_date, timestamp, actor, idempotency_key, reversal_ref_id, notes, created_at
FROM inventory_transactions;

DROP TRIGGER IF EXISTS trg_prevent_tx_update;
DROP TRIGGER IF EXISTS trg_prevent_tx_delete;
DROP TABLE inventory_transactions;
ALTER TABLE inventory_transactions_new RENAME TO inventory_transactions;

CREATE INDEX IF NOT EXISTS ix_tx_ing_ts ON inventory_transactions(ingredient_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_tx_ref ON inventory_transactions(reference_id);
CREATE INDEX IF NOT EXISTS ix_tx_idemp ON inventory_transactions(idempotency_key);

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

-- 2. Extend depletion_logs with resolution fields and flexible status
CREATE TABLE IF NOT EXISTS depletion_logs_new (
    depletion_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    opening_qty REAL NOT NULL,
    deliveries_qty REAL NOT NULL,
    closing_qty REAL NOT NULL,
    calculated_depletion_kg REAL NOT NULL,
    unexplained_depletion_kg REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'UNCLASSIFIED' CHECK(status IN ('UNCLASSIFIED', 'INVESTIGATING', 'INVESTIGATED', 'CLASSIFIED', 'RESOLVED')),
    reconciliation_transaction_id TEXT,
    recorded_by TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    notes TEXT,
    resolution_notes TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    UNIQUE(date, ingredient_id)
);

INSERT INTO depletion_logs_new (
    depletion_id, date, ingredient_id, opening_qty, deliveries_qty,
    closing_qty, calculated_depletion_kg, unexplained_depletion_kg,
    status, reconciliation_transaction_id, recorded_by, recorded_at, notes
)
SELECT depletion_id, date, ingredient_id, opening_qty, deliveries_qty,
       closing_qty, calculated_depletion_kg, unexplained_depletion_kg,
       status, reconciliation_transaction_id, recorded_by, recorded_at, notes
FROM depletion_logs;

DROP TABLE depletion_logs;
ALTER TABLE depletion_logs_new RENAME TO depletion_logs;
CREATE INDEX IF NOT EXISTS ix_depletion_logs_date ON depletion_logs(date);
CREATE INDEX IF NOT EXISTS ix_depletion_logs_status ON depletion_logs(status);

-- 3. Depletion Classifications (Zero-sum categorization events)
CREATE TABLE IF NOT EXISTS depletion_classifications (
    classification_id TEXT PRIMARY KEY,
    depletion_id TEXT NOT NULL REFERENCES depletion_logs(depletion_id) ON DELETE RESTRICT,
    category TEXT NOT NULL CHECK(category IN (
        'SPOILAGE', 'EXPIRED', 'PREPARATION_LOSS', 'SPILLAGE',
        'DAMAGE', 'THEFT', 'MEASUREMENT_ERROR', 'NORMAL_CONSUMPTION',
        'OTHER_UNEXPLAINED'
    )),
    classified_qty REAL NOT NULL CHECK(classified_qty > 0),
    unit TEXT NOT NULL DEFAULT 'kg',
    reclassification_transaction_id TEXT,
    classified_by TEXT NOT NULL REFERENCES users(username),
    classified_at TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'REVERSED')),
    reversal_id TEXT,
    reversal_reason TEXT,
    reversed_by TEXT,
    reversed_at TEXT,
    idempotency_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_dep_class_dep_id ON depletion_classifications(depletion_id);
CREATE INDEX IF NOT EXISTS ix_dep_class_cat ON depletion_classifications(category);
CREATE INDEX IF NOT EXISTS ix_dep_class_status ON depletion_classifications(status);

-- 4. Manager Investigation Notes
CREATE TABLE IF NOT EXISTS depletion_investigation_notes (
    note_id TEXT PRIMARY KEY,
    depletion_id TEXT NOT NULL REFERENCES depletion_logs(depletion_id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dep_notes_dep_id ON depletion_investigation_notes(depletion_id);

PRAGMA foreign_keys = ON;
