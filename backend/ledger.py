"""
SmartStock AI — Authoritative Append-Only Inventory Movement Journal and Balance Reconciliation.
Provides atomic postings, idempotency, compensating reversals, and projection reconciliation.
"""
import uuid
from datetime import datetime
from decimal import Decimal
import db

VALID_TRANSACTION_TYPES = (
    "STOCK_IN",
    "TRANSFER",
    "CONSUMPTION",
    "WASTAGE",
    "STOCK_COUNT",
    "ADJUSTMENT",
    "REVERSAL",
    "REFILL",
    "RECLASSIFICATION",
)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_book_balance(ingredient_id, con=None):
    """
    Returns the current projected book balance for an ingredient.
    Reads from inventory_balances or derives from the transaction journal sum.
    """
    own_connection = con is None
    if own_connection:
        con = db.connect()
    try:
        row = con.execute(
            "SELECT book_balance FROM inventory_balances WHERE ingredient_id=?",
            (ingredient_id,)
        ).fetchone()
        if row is not None:
            return round(float(row[0]), 4)

        # Fallback to direct journal sum if projection record is missing
        sum_row = con.execute(
            "SELECT COALESCE(SUM(delta_qty), 0.0) FROM inventory_transactions WHERE ingredient_id=?",
            (ingredient_id,)
        ).fetchone()
        return round(float(sum_row[0]), 4)
    finally:
        if own_connection:
            con.close()


def post_transaction(
    ingredient_id: str,
    transaction_type: str,
    quantity: float,
    delta_qty: float,
    unit: str,
    actor: str,
    source_channel: str,
    reference_id: str = None,
    batch_no: str = None,
    expiry_date: str = None,
    timestamp: str = None,
    idempotency_key: str = None,
    reversal_ref_id: str = None,
    notes: str = None,
    allow_negative: bool = False,
    con=None,
):
    """
    Atomically posts an immutable inventory transaction.
    Enforces idempotency, non-negative quantity parameter, balance constraints, and projection update.
    """
    if transaction_type not in VALID_TRANSACTION_TYPES:
        raise ValueError(f"Invalid transaction type '{transaction_type}'. Must be one of {VALID_TRANSACTION_TYPES}")

    if quantity < 0:
        raise ValueError(f"Transaction quantity must be non-negative (received {quantity})")

    # Round deltas to 4 decimal places for precision
    qty_val = round(float(quantity), 4)
    delta_val = round(float(delta_qty), 4)

    own_connection = con is None
    if own_connection:
        tx_context = db.tx()
        con = tx_context.__enter__()
    else:
        tx_context = None

    try:
        # 1. Idempotency Check
        if idempotency_key:
            existing = con.execute(
                "SELECT * FROM inventory_transactions WHERE idempotency_key=?",
                (idempotency_key,)
            ).fetchone()
            if existing is not None:
                tx_dict = dict(existing)
                return {"status": "duplicate", "transaction": tx_dict, "idempotent": True}

        # 2. Ingredient validation
        ing = con.execute(
            "SELECT ingredient_id, name, unit FROM ingredients WHERE ingredient_id=?",
            (ingredient_id,)
        ).fetchone()
        if not ing:
            raise ValueError(f"Unknown ingredient_id '{ingredient_id}'")

        unit = unit or ing["unit"]

        # 3. Balance verification (prevent unauthorized negative stock)
        current_balance = get_book_balance(ingredient_id, con=con)
        new_balance = round(current_balance + delta_val, 4)

        if not allow_negative and transaction_type not in ("STOCK_COUNT", "ADJUSTMENT"):
            if new_balance < -0.0001:
                raise ValueError(
                    f"Insufficient stock for {ingredient_id} ({ing['name']}): current balance is "
                    f"{current_balance} {unit}, cannot apply delta {delta_val} {unit} (would result in {new_balance} {unit})"
                )

        # 4. Generate unique transaction ID
        tx_id = f"TX{datetime.now():%y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
        ts = timestamp or now_str()

        # 5. Insert into immutable journal
        con.execute(
            """
            INSERT INTO inventory_transactions (
                transaction_id, ingredient_id, quantity, delta_qty, unit,
                transaction_type, source_channel, reference_id, batch_no,
                expiry_date, timestamp, actor, idempotency_key, reversal_ref_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_id, ingredient_id, qty_val, delta_val, unit,
                transaction_type, source_channel, reference_id, batch_no,
                expiry_date, ts, actor, idempotency_key, reversal_ref_id, notes
            )
        )

        # 6. Update balance projection inside the same transaction
        con.execute(
            """
            INSERT INTO inventory_balances (
                ingredient_id, book_balance, last_transaction_id, last_updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(ingredient_id) DO UPDATE SET
                book_balance = excluded.book_balance,
                last_transaction_id = excluded.last_transaction_id,
                last_updated_at = excluded.last_updated_at
            """,
            (ingredient_id, new_balance, tx_id, now_str())
        )

        # 7. Audit log event
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_str(), actor, f"INVENTORY_{transaction_type}", f"{tx_id} {ingredient_id} delta={delta_val} new_bal={new_balance}")
        )

        created_tx = {
            "transaction_id": tx_id,
            "ingredient_id": ingredient_id,
            "quantity": qty_val,
            "delta_qty": delta_val,
            "unit": unit,
            "transaction_type": transaction_type,
            "source_channel": source_channel,
            "reference_id": reference_id,
            "batch_no": batch_no,
            "expiry_date": expiry_date,
            "timestamp": ts,
            "actor": actor,
            "idempotency_key": idempotency_key,
            "reversal_ref_id": reversal_ref_id,
            "new_balance": new_balance,
            "status": "posted"
        }

        if tx_context:
            tx_context.__exit__(None, None, None)

        return created_tx
    except Exception as e:
        if tx_context:
            tx_context.__exit__(type(e), e, None)
        raise


def reverse_transaction(
    original_tx_id: str,
    actor: str,
    reason: str,
    idempotency_key: str = None,
    con=None,
):
    """
    Compensates an existing transaction by posting an equal and opposite REVERSAL.
    Does not delete or mutate the original record.
    """
    own_connection = con is None
    if own_connection:
        tx_context = db.tx()
        con = tx_context.__enter__()
    else:
        tx_context = None

    try:
        orig = con.execute(
            "SELECT * FROM inventory_transactions WHERE transaction_id=?",
            (original_tx_id,)
        ).fetchone()
        if not orig:
            raise ValueError(f"Cannot reverse non-existent transaction '{original_tx_id}'")

        orig_dict = dict(orig)

        # Check if already reversed
        already_reversed = con.execute(
            "SELECT transaction_id FROM inventory_transactions WHERE reversal_ref_id=?",
            (original_tx_id,)
        ).fetchone()
        if already_reversed:
            raise ValueError(f"Transaction '{original_tx_id}' has already been reversed by '{already_reversed[0]}'")

        reverse_delta = -orig_dict["delta_qty"]
        rev_idemp = idempotency_key or f"REV_{original_tx_id}"

        reversal_tx = post_transaction(
            ingredient_id=orig_dict["ingredient_id"],
            transaction_type="REVERSAL",
            quantity=orig_dict["quantity"],
            delta_qty=reverse_delta,
            unit=orig_dict["unit"],
            actor=actor,
            source_channel="SYSTEM_REVERSAL",
            reference_id=orig_dict.get("reference_id"),
            batch_no=orig_dict.get("batch_no"),
            expiry_date=orig_dict.get("expiry_date"),
            idempotency_key=rev_idemp,
            reversal_ref_id=original_tx_id,
            notes=f"Reversal of {original_tx_id}: {reason}",
            allow_negative=True,
            con=con,
        )

        if tx_context:
            tx_context.__exit__(None, None, None)

        return reversal_tx
    except Exception as e:
        if tx_context:
            tx_context.__exit__(type(e), e, None)
        raise


def reconcile_balances(ingredient_id: str = None, fix: bool = False, actor: str = "system", con=None):
    """
    Reconciles inventory_balances projection against the sum of valid transactions.
    Detects discrepancies and optionally adjusts the projection to match ground-truth journal sum.
    Never deletes or alters historical transactions.
    """
    own_connection = con is None
    if own_connection:
        con = db.connect()

    try:
        sql_journal = """
            SELECT ingredient_id, ROUND(COALESCE(SUM(delta_qty), 0.0), 4) as journal_balance, COUNT(1) as tx_count
            FROM inventory_transactions
        """
        args = []
        if ingredient_id:
            sql_journal += " WHERE ingredient_id=?"
            args.append(ingredient_id)
        sql_journal += " GROUP BY ingredient_id"

        journal_rows = {r[0]: (float(r[1]), int(r[2])) for r in con.execute(sql_journal, args).fetchall()}

        sql_ings = "SELECT ingredient_id, name, unit FROM ingredients"
        if ingredient_id:
            sql_ings += " WHERE ingredient_id=?"
        all_ings = con.execute(sql_ings, args).fetchall()

        discrepancies = []
        reconciled = []

        for row in all_ings:
            iid = row["ingredient_id"]
            name = row["name"]
            unit = row["unit"]

            j_bal, tx_count = journal_rows.get(iid, (0.0, 0))

            bal_row = con.execute("SELECT book_balance FROM inventory_balances WHERE ingredient_id=?", (iid,)).fetchone()
            b_bal = float(bal_row[0]) if bal_row else 0.0

            diff = round(j_bal - b_bal, 4)
            is_match = abs(diff) <= 0.0001

            item_status = {
                "ingredient_id": iid,
                "name": name,
                "unit": unit,
                "journal_balance": j_bal,
                "projected_balance": b_bal,
                "difference": diff,
                "matched": is_match,
                "tx_count": tx_count
            }

            if not is_match:
                discrepancies.append(item_status)
                if fix:
                    con.execute(
                        """
                        INSERT INTO inventory_balances (ingredient_id, book_balance, last_transaction_id, last_updated_at)
                        VALUES (?, ?, 'RECONCILED', ?)
                        ON CONFLICT(ingredient_id) DO UPDATE SET
                            book_balance = excluded.book_balance,
                            last_updated_at = excluded.last_updated_at
                        """,
                        (iid, j_bal, now_str())
                    )
                    con.execute(
                        "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
                        (now_str(), actor, "BALANCE_RECONCILIATION_FIX", f"{iid} adjusted from {b_bal} to {j_bal} (diff: {diff})")
                    )
                    item_status["fixed"] = True
            reconciled.append(item_status)

        if fix and own_connection:
            con.commit()

        return {
            "status": "clean" if not discrepancies else ("fixed" if fix else "discrepancies_detected"),
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
            "ingredients": reconciled
        }
    finally:
        if own_connection:
            con.close()
