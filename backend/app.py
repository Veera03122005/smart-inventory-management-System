"""SmartStock AI - Flask REST API.  Run:  python app.py   (http://localhost:5000)"""
import csv, io, json, os, uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, Response, send_from_directory, send_file
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash
import db, iot, ledger, ml, simulator, document_parser, units

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "..", "frontend", "dist")
app = Flask(__name__, static_folder=None)

# Production security: restrict CORS origins
ENV = os.environ.get("SMARTSTOCK_ENV", "development").lower()
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("SMARTSTOCK_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",") if o.strip()]
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Production security: fail startup if secret is missing or insecure in production mode
SECRET = os.environ.get("SMARTSTOCK_SECRET")
if ENV == "production":
    if not SECRET or SECRET == "change-me-in-production" or len(SECRET) < 32:
        raise RuntimeError(
            "FATAL CONFIGURATION ERROR: In production mode (SMARTSTOCK_ENV=production), "
            "SMARTSTOCK_SECRET must be explicitly set to a cryptographically secure key of at least 32 characters."
        )
else:
    SECRET = SECRET or "change-me-in-production-dev-only"

signer = URLSafeTimedSerializer(SECRET)
TOKEN_HOURS = 12
db.init_schema()


# ------------------------------------------------------------------ auth
def auth(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            # Security Hardening: tokens in URL query strings are explicitly prohibited
            if not request.headers.get("Authorization") and request.args.get("token"):
                return jsonify(error="Query string token authentication is disabled. Provide token via Authorization Bearer header."), 401

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify(error="not authenticated"), 401

            tok = auth_header[7:].strip()
            try:
                payload = signer.loads(tok, max_age=TOKEN_HOURS * 3600)
            except (BadSignature, SignatureExpired):
                return jsonify(error="not authenticated"), 401

            # Active user verification: revalidate user existence and current role from DB
            u = db.query("SELECT id, username, role, full_name, COALESCE(is_active, 1) as is_active FROM users WHERE username=?", (payload.get("username", ""),))
            if not u:
                return jsonify(error="user no longer exists or has been deactivated"), 401

            user = u[0]
            if user.get("is_active", 1) == 0:
                return jsonify(error="account has been deactivated"), 401

            if roles and user["role"] not in roles:
                return jsonify(error="not authorised for this action"), 403

            request.user = {"username": user["username"], "role": user["role"], "full_name": user["full_name"], "is_active": user.get("is_active", 1)}
            return fn(*a, **k)
        return wrapper
    return deco


@app.post("/api/auth/login")
def login():
    b = request.get_json(force=True, silent=True) or {}
    u = db.query("SELECT id, username, password_hash, role, full_name, COALESCE(is_active, 1) as is_active FROM users WHERE username=?", (b.get("username", ""),))
    if not u or not check_password_hash(u[0]["password_hash"], b.get("password", "")):
        return jsonify(error="invalid username or password"), 401
    if u[0].get("is_active", 1) == 0:
        return jsonify(error="account is deactivated, contact management"), 401
    user = {"username": u[0]["username"], "role": u[0]["role"], "full_name": u[0]["full_name"], "is_active": u[0].get("is_active", 1)}
    return jsonify(token=signer.dumps(user), user=user)


@app.get("/api/me")
@auth()
def me():
    return jsonify(request.user)


@app.get("/api/users")
@auth("owner", "manager")
def users():
    role = request.user["role"]
    sql = """
        SELECT u.id, u.username, u.role, u.full_name, COALESCE(u.is_active, 1) as is_active,
               MAX(a.ts) as last_active,
               COUNT(a.id) as action_count
        FROM users u
        LEFT JOIN audit_log a ON a.actor = u.username
    """
    if role == "manager":
        sql += " WHERE u.role = 'staff' GROUP BY u.id, u.username, u.role, u.full_name, u.is_active ORDER BY u.id"
    else:
        sql += " GROUP BY u.id, u.username, u.role, u.full_name, u.is_active ORDER BY u.id"
    return jsonify(db.query(sql))


@app.post("/api/users")
@auth("owner", "manager")
def add_user():
    caller_role = request.user["role"]
    b = request.get_json(force=True, silent=True) or {}
    target_role = b.get("role")
    username = (b.get("username") or "").strip()
    password = b.get("password", "")
    full_name = (b.get("full_name") or "").strip()

    if not username or not target_role or len(password) < 6:
        return jsonify(error="username, role and a password of 6+ characters are required"), 422
    if target_role not in ("owner", "manager", "staff"):
        return jsonify(error="invalid role specified"), 422

    if caller_role == "manager":
        if target_role != "staff":
            return jsonify(error="Managers can only create staff accounts"), 403

    try:
        with db.tx() as con:
            con.execute("INSERT INTO users(username, password_hash, role, full_name, is_active) VALUES (?,?,?,?,1)",
                        (username, generate_password_hash(password), target_role, full_name))
            con.execute("INSERT INTO audit_log(ts, actor, action, detail) VALUES (?,?,?,?)",
                        (iot.now_str(), request.user["username"], "CREATE_USER", f"Created user {username} ({target_role})"))
    except Exception:
        return jsonify(error="username already exists"), 409
    return jsonify(status="created", username=username, role=target_role), 201


@app.post("/api/users/<int:user_id>/toggle-status")
@auth("owner", "manager")
def toggle_user_status(user_id):
    caller_role = request.user["role"]
    caller_name = request.user["username"]
    target_list = db.query("SELECT * FROM users WHERE id=?", (user_id,))
    if not target_list:
        return jsonify(error="user not found"), 404
    target = target_list[0]

    if caller_role == "manager":
        if target["role"] != "staff":
            return jsonify(error="Managers can only manage staff accounts"), 403
        if target["username"] == caller_name:
            return jsonify(error="Managers cannot modify their own account"), 403

    if caller_role == "owner":
        if target["username"] == caller_name:
            return jsonify(error="Owners cannot deactivate their own account"), 400

    cur_active = target.get("is_active", 1)
    new_active = 0 if cur_active == 1 else 1
    with db.tx() as con:
        con.execute("UPDATE users SET is_active=? WHERE id=?", (new_active, user_id))
        con.execute("INSERT INTO audit_log(ts, actor, action, detail) VALUES (?,?,?,?)",
                    (iot.now_str(), caller_name, "USER_STATUS_TOGGLE", f"User {target['username']} active set to {new_active}"))
    return jsonify(status="updated", user_id=user_id, username=target["username"], is_active=new_active), 200


@app.patch("/api/users/<int:user_id>")
@auth("owner", "manager")
def update_user(user_id):
    caller_role = request.user["role"]
    caller_name = request.user["username"]
    b = request.get_json(force=True, silent=True) or {}
    target_list = db.query("SELECT * FROM users WHERE id=?", (user_id,))
    if not target_list:
        return jsonify(error="user not found"), 404
    target = target_list[0]

    if caller_role == "manager":
        if target["role"] != "staff":
            return jsonify(error="Managers can only manage staff accounts"), 403
        if b.get("role") and b.get("role") != "staff":
            return jsonify(error="Managers cannot change account role or promote accounts"), 403
        if target["username"] == caller_name:
            return jsonify(error="Managers cannot modify their own account"), 403

    if caller_role == "owner":
        if target["username"] == caller_name and b.get("is_active") == 0:
            return jsonify(error="Owners cannot deactivate their own account"), 400

    updates, args = [], []
    if "full_name" in b:
        updates.append("full_name=?")
        args.append(b["full_name"])
    if "is_active" in b:
        updates.append("is_active=?")
        args.append(1 if b["is_active"] else 0)
    if "role" in b:
        if caller_role != "owner":
            return jsonify(error="Only owners can change account roles"), 403
        if b["role"] in ("owner", "manager", "staff"):
            updates.append("role=?")
            args.append(b["role"])
    if "password" in b and len(b["password"]) >= 6:
        updates.append("password_hash=?")
        args.append(generate_password_hash(b["password"]))

    if not updates:
        return jsonify(error="no valid fields to update"), 400

    args.append(user_id)
    with db.tx() as con:
        con.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", args)
        con.execute("INSERT INTO audit_log(ts, actor, action, detail) VALUES (?,?,?,?)",
                    (iot.now_str(), caller_name, "USER_UPDATE", f"Updated user {target['username']}"))
    return jsonify(status="updated", user_id=user_id), 200


# ------------------------------------------------------------------ master data
@app.get("/api/health")
def health():
    return jsonify(status="ok", time=datetime.now().isoformat(timespec="seconds"))


@app.get("/api/ingredients")
@auth()
def ingredients():
    rows = db.query("SELECT * FROM ingredients ORDER BY ingredient_id")
    if request.user["role"] in ("staff", "manager"):
        for r in rows:
            r["unit_cost_rs"] = None
    return jsonify(rows)


@app.get("/api/barcode/<code>")
@auth()
def barcode(code):
    ing = iot.resolve_barcode(code)
    if not ing:
        return jsonify(error="barcode not found"), 404
    if request.user["role"] in ("staff", "manager"):
        ing["unit_cost_rs"] = None
    return jsonify(ing), 200


# ------------------------------------------------------------------ alerts
def build_alerts():
    res = ml.get_results()["results"]
    acks = {a["alert_key"]: a for a in db.query("SELECT * FROM alert_acks")}
    out = []

    def add(kind, sev, ing, title, detail, date, action):
        key = f"{kind}|{ing}|{date}"
        out.append({"key": key, "type": kind, "severity": sev, "ingredient": ing, "title": title, "detail": detail,
                    "date": date, "action": action, "acknowledged": key in acks,
                    "acked_by": acks.get(key, {}).get("acked_by")})

    for r in res.values():
        u, name = r["unit"], r["name"]
        if r["order_qty"] > 0 and (r["stock"] < r["reorder_point"]):
            sev = "high" if r["stock"] < r["prep_qty"] else "medium"
            add("LOW_STOCK", sev, name, f"{name}: stock below reorder point",
                f"Stock {r['stock']} {u}, reorder point {r['reorder_point']} {u}, forecast for {r['target_date']} is "
                f"{r['prep_qty']} {u}.", r["target_date"], f"Order {r['order_qty']} {u}")
        for b in r["batches"]:
            if b["at_risk_qty"] > 0.5:
                add("EXPIRY_RISK", "high" if b["days_to_expiry"] <= 1 else "medium", name,
                    f"{name}: {b['at_risk_qty']} {u} may expire unused",
                    f"Batch {b['batch_no']} expires {b['expiry_date']} ({b['days_to_expiry']} day(s) left), "
                    f"{b['qty_remaining']} {u} remaining.", b["expiry_date"] + "|" + b["batch_no"],
                    "Use this batch first or reduce the next order")
        for a in r["anomalies"][-5:]:
            more = a["actual"] > a["expected"]
            add("USAGE_ANOMALY", "medium", name, f"{name}: usage {'above' if more else 'below'} normal on {a['date']}",
                f"Recorded {a['actual']} {u}, expected about {a['expected']} {u} (z = {a['z']}).", a["date"],
                "Check for wastage, a bulk order or a wrong entry")
    names = {i["ingredient_id"]: i for i in db.query("SELECT * FROM ingredients")}
    for s in iot.spill_events()[-10:]:
        n = names[s["ingredient_id"]]["name"]
        add("SUDDEN_DROP", "high", n, f"{n}: sudden weight drop of {s['drop_kg']} kg",
            f"Device {s['device_id']} recorded the drop at {s['ts']} with no refill session open.", s["ts"],
            "Check for spillage or unrecorded removal")
    last = db.query("SELECT MAX(date) d FROM manual_entries")[0]["d"]
    for m in db.query("SELECT m.date, i.name FROM manual_entries m JOIN ingredients i USING (ingredient_id) "
                      "WHERE m.entry_status='MISSED' AND m.date=?", (last,)):
        add("MISSED_ENTRY", "low", m["name"], f"{m['name']}: stock sheet not filled for {m['date']}",
            "The forecast is using a reconstructed value for this day.", m["date"], "Enter the stock sheet")
    if simulator.status()["running"]:
        for dev, w in simulator.status()["weights"].items():
            d = db.query("SELECT i.name FROM devices d JOIN ingredients i USING (ingredient_id) WHERE d.device_id=?", (dev,))
            if w < 3.0 and not db.query("SELECT 1 FROM refill_sessions WHERE device_id=? AND status='OPEN'", (dev,)):
                add("REFILL_NEEDED", "medium", d[0]["name"], f"{d[0]['name']} bin is low ({w:.1f} kg)",
                    f"Device {dev} live weight is below 3 kg.", datetime.now().strftime("%Y-%m-%d %H"),
                    "Scan the barcode and refill the bin")
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: (a["acknowledged"], order[a["severity"]], a["date"]), reverse=False)
    return out


@app.get("/api/alerts")
@auth()
def alerts():
    return jsonify(build_alerts())


@app.post("/api/alerts/ack")
@auth("owner", "manager")
def ack():
    key = (request.get_json(force=True, silent=True) or {}).get("key")
    if not key or not isinstance(key, str):
        return jsonify(error="valid 'key' string is required"), 400
    with db.tx() as con:
        con.execute("INSERT OR REPLACE INTO alert_acks VALUES (?,?,?)", (key, request.user["username"], iot.now_str()))
    return jsonify(status="acknowledged")


# ------------------------------------------------------------------ dashboard & forecast
def get_sales_metrics():
    """
    Retrieves authoritative sales data if recorded in the database.
    Strictly does NOT fabricate sales metrics from ingredient usage, food costs, or fixed fallbacks.
    Returns status 'DATA_UNAVAILABLE' if no actual sales stream exists in the database.
    """
    try:
        tables = [r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('daily_sales', 'sales_records')")]
        if not tables:
            return {"status": "DATA_UNAVAILABLE", "error": "DATA_UNAVAILABLE", "message": "Actual sales data is unavailable"}
        tbl = tables[0]
        rows = db.query(f"SELECT date, gross_sales_rs, orders_count FROM {tbl} ORDER BY date DESC LIMIT 30")
        if not rows:
            return {"status": "DATA_UNAVAILABLE", "error": "DATA_UNAVAILABLE", "message": "Actual sales data is unavailable"}

        today = datetime.now().strftime("%Y-%m-%d")
        today_row = next((r for r in rows if r["date"] == today), rows[0])
        sales_7d = sum(r["gross_sales_rs"] for r in rows[:7])
        orders_7d = sum(r["orders_count"] for r in rows[:7])
        return {
            "status": "AVAILABLE",
            "today_sales_rs": today_row["gross_sales_rs"],
            "sales_7d_rs": sales_7d,
            "orders_today": today_row["orders_count"],
            "orders_7d": orders_7d,
            "daily": [{"date": r["date"], "orders_count": r["orders_count"], "gross_sales_rs": r["gross_sales_rs"]} for r in rows]
        }
    except Exception:
        return {"status": "DATA_UNAVAILABLE", "error": "DATA_UNAVAILABLE", "message": "Actual sales data is unavailable"}


@app.get("/api/sales")
@auth("owner", "manager")
def sales():
    data = get_sales_metrics()
    if not data or data.get("status") == "DATA_UNAVAILABLE":
        return jsonify({
            "status": "DATA_UNAVAILABLE",
            "error": "DATA_UNAVAILABLE",
            "message": "Actual sales data is unavailable. Real sales are not derived from ingredient costs."
        }), 200

    res = {
        "status": "AVAILABLE",
        "today_sales_rs": data["today_sales_rs"],
        "sales_7d_rs": data["sales_7d_rs"],
        "orders_today": data["orders_today"],
        "orders_7d": data["orders_7d"],
        "daily": data["daily"]
    }
    # Owner gets profit metrics, Manager does NOT get costs or profit margins
    if request.user["role"] == "owner":
        cost_rows = db.query("SELECT * FROM ingredients")
        res["cost_of_food_rs"] = None
        res["gross_profit_rs"] = None
        res["food_cost_pct"] = None
    return jsonify(res)


@app.get("/api/dashboard")
@auth()
def dashboard():
    role = request.user["role"]
    c = ml.get_results()
    res = c["results"]
    al = [a for a in build_alerts() if not a["acknowledged"]]
    rows = []
    for r in res.values():
        status = "OK"
        if any(a["ingredient"] == r["name"] and a["type"] == "LOW_STOCK" for a in al): status = "Low stock"
        elif any(a["ingredient"] == r["name"] and a["type"] == "EXPIRY_RISK" for a in al): status = "Expiry risk"
        rows.append({k: r[k] for k in ("ingredient_id", "name", "unit", "stock", "stock_date", "days_of_cover",
                                       "prep_qty", "target_date", "order_qty", "reorder_point", "model")} | {"status": status})
    cost = {i["ingredient_id"]: i["unit_cost_rs"] for i in db.query("SELECT * FROM ingredients")}
    week = (datetime.strptime(next(iter(res.values()))["stock_date"], "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
    w = db.query("SELECT ingredient_id, SUM(wastage_qty) q, SUM(used_qty) u FROM manual_entries WHERE date>=? GROUP BY 1", (week,))

    sales_data = get_sales_metrics()
    has_sales = bool(sales_data and sales_data.get("status") != "DATA_UNAVAILABLE")
    sales_today = sales_data["today_sales_rs"] if has_sales else None
    sales_7d = sales_data["sales_7d_rs"] if has_sales else None

    if role == "staff":
        # Strictly zero sales, revenue, purchase costs, stock valuation, or profit for staff
        cards = {
            "ingredients": len(rows),
            "low_stock": sum(r["status"] == "Low stock" for r in rows),
            "expiry_risk": sum(a["type"] == "EXPIRY_RISK" for a in al),
            "open_alerts": len(al),
            "stock_value_rs": None,
            "order_value_rs": None,
            "wastage_7d_rs": None,
            "usage_7d_rs": None,
            "sales_today_rs": None,
            "sales_7d_rs": None,
        }
    elif role == "manager":
        # Manager: access to real sales figures if available; NO purchase costs, unit costs, valuation, or profit
        cards = {
            "ingredients": len(rows),
            "low_stock": sum(r["status"] == "Low stock" for r in rows),
            "expiry_risk": sum(a["type"] == "EXPIRY_RISK" for a in al),
            "open_alerts": len(al),
            "stock_value_rs": None,
            "order_value_rs": None,
            "wastage_7d_rs": None,
            "usage_7d_rs": None,
            "sales_today_rs": sales_today,
            "sales_7d_rs": sales_7d,
        }
    else:  # owner: full financial and operational view
        cards = {
            "ingredients": len(rows),
            "low_stock": sum(r["status"] == "Low stock" for r in rows),
            "expiry_risk": sum(a["type"] == "EXPIRY_RISK" for a in al),
            "open_alerts": len(al),
            "stock_value_rs": round(sum(r["stock"] * cost[r["ingredient_id"]] for r in rows)),
            "order_value_rs": round(sum(r["order_qty"] * cost[r["ingredient_id"]] for r in rows)),
            "wastage_7d_rs": round(sum((x["q"] or 0) * cost[x["ingredient_id"]] for x in w)),
            "usage_7d_rs": round(sum((x["u"] or 0) * cost[x["ingredient_id"]] for x in w)),
            "sales_today_rs": sales_today,
            "sales_7d_rs": sales_7d,
        }

    return jsonify({
        "run_at": c["run_at"], "target_date": next(iter(res.values()))["target_date"],
        "cards": cards,
        "rows": rows, "alerts": al[:6]})


@app.get("/api/forecast")
@auth()
def forecast():
    c = ml.get_results()
    return jsonify({"run_at": c["run_at"], "seconds": c.get("seconds"), "results": list(c["results"].values())})


@app.post("/api/forecast/retrain")
@auth("owner", "manager")
def retrain():
    c = ml.train_all()
    return jsonify(run_at=c["run_at"], seconds=c["seconds"])


# ------------------------------------------------------------------ manual stock sheet
@app.get("/api/manual-entries")
@auth()
def manual_list():
    ing = request.args.get("ingredient_id"); limit = int(request.args.get("limit", 60))
    sql = "SELECT m.*, i.name, i.unit FROM manual_entries m JOIN ingredients i USING (ingredient_id)"
    args = []
    if ing:
        sql += " WHERE m.ingredient_id=?"; args.append(ing)
    return jsonify(db.query(sql + " ORDER BY m.date DESC, m.ingredient_id LIMIT ?", args + [limit]))


@app.get("/api/manual-entries/prefill")
@auth()
def manual_prefill():
    ing = request.args["ingredient_id"]
    stock, d = ml.current_stock(ing)
    nxt = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if d else datetime.now().strftime("%Y-%m-%d")
    r = ml.get_results()["results"].get(ing, {})
    return jsonify(date=nxt, opening_stock=stock, suggested_used=r.get("prep_qty"))


@app.post("/api/manual-entries")
@auth()
def manual_save():
    b = request.get_json(force=True, silent=True) or {}
    try:
        opening, received = float(b["opening_stock"]), float(b.get("received_qty") or 0)
        used, waste = float(b["used_qty"]), float(b.get("wastage_qty") or 0)
        date, ing = b["date"], b["ingredient_id"]
        datetime.strptime(date, "%Y-%m-%d")
    except (KeyError, ValueError, TypeError):
        return jsonify(error="date, ingredient, opening stock and used quantity are required"), 422
    if min(opening, received, used, waste) < 0:
        return jsonify(error="quantities cannot be negative"), 422
    closing = opening + received - used - waste
    if closing < -0.01:
        return jsonify(error=f"used + wastage ({used + waste}) is more than opening + received ({opening + received})"), 422
    if received > 0 and not b.get("expiry_date"):
        return jsonify(error="expiry date is required when stock is received"), 422
    # days covered: count immediately preceding MISSED days
    prev = db.query("SELECT date, entry_status FROM manual_entries WHERE ingredient_id=? AND date<? ORDER BY date DESC LIMIT 10", (ing, date))
    gap = 0
    for p in prev:
        if p["entry_status"] == "MISSED": gap += 1
        else: break
    batch = b.get("batch_no") or (f"{ing}-M{date.replace('-', '')}" if received > 0 else None)
    ref_id = f"MANUAL:{date}:{ing}"
    idemp_base = b.get("idempotency_key") or f"MANUAL_{date}_{ing}"
    user_name = request.user["username"]

    with db.tx() as con:
        # Check if an entry already exists for this (date, ing) to detect duplicates vs corrections
        prev_entry = con.execute(
            "SELECT * FROM manual_entries WHERE date=? AND ingredient_id=?", (date, ing)
        ).fetchone()

        if prev_entry is not None:
            prev_open = float(prev_entry["opening_stock"]) if prev_entry["opening_stock"] is not None else 0.0
            prev_rec = float(prev_entry["received_qty"]) if prev_entry["received_qty"] is not None else 0.0
            prev_used = float(prev_entry["used_qty"]) if prev_entry["used_qty"] is not None else 0.0
            prev_waste = float(prev_entry["wastage_qty"]) if prev_entry["wastage_qty"] is not None else 0.0
            prev_batch = str(prev_entry["batch_no"] or "")
            prev_expiry = str(prev_entry["expiry_date"] or "")

            is_identical = (
                abs(prev_open - opening) < 1e-4 and
                abs(prev_rec - received) < 1e-4 and
                abs(prev_used - used) < 1e-4 and
                abs(prev_waste - waste) < 1e-4 and
                prev_batch == str(batch or "") and
                prev_expiry == str(b.get("expiry_date") or "")
            )
            if is_identical:
                # Idempotent retry: return existing saved status without generating secondary ledger rows or reversals
                return jsonify(status="saved", closing_stock=round(closing, 2), days_covered=gap + 1, duplicate=True), 200

            # Active correction: locate and reverse only currently active, unreversed transactions for this entry
            unreversed_txs = con.execute(
                """
                SELECT t.transaction_id FROM inventory_transactions t
                WHERE t.reference_id = ?
                  AND t.transaction_type != 'REVERSAL'
                  AND NOT EXISTS (
                      SELECT 1 FROM inventory_transactions r
                      WHERE r.reversal_ref_id = t.transaction_id
                  )
                """,
                (ref_id,)
            ).fetchall()
            for ptx in unreversed_txs:
                try:
                    ledger.reverse_transaction(
                        original_tx_id=ptx[0],
                        actor=user_name,
                        reason=f"Corrected daily stock sheet for {date}",
                        con=con
                    )
                except ValueError:
                    pass

            # Determine revision count so replacement movements receive unique idempotency keys
            rev_count = con.execute(
                "SELECT COUNT(*) FROM inventory_transactions WHERE reference_id=? AND transaction_type='REVERSAL'",
                (ref_id,)
            ).fetchone()[0]
            if not b.get("idempotency_key"):
                idemp_base = f"MANUAL_{date}_{ing}_rev{rev_count}"
            else:
                idemp_base = f"{b['idempotency_key']}_rev{rev_count}"

        ing_row = con.execute("SELECT unit FROM ingredients WHERE ingredient_id=?", (ing,)).fetchone()
        canonical_unit = ing_row["unit"] if ing_row else "kg"
        item_unit = b.get("unit") or canonical_unit

        # Post new transactions to the immutable journal
        if received > 0:
            ledger.post_transaction(
                ingredient_id=ing, transaction_type="STOCK_IN", quantity=received, delta_qty=+received,
                unit=item_unit, actor=user_name, source_channel="MANUAL_FORM", reference_id=ref_id,
                batch_no=batch, expiry_date=b.get("expiry_date"), idempotency_key=f"{idemp_base}_IN",
                notes=f"Stock receipt on {date}", allow_negative=True, con=con
            )
        if used > 0:
            ledger.post_transaction(
                ingredient_id=ing, transaction_type="CONSUMPTION", quantity=used, delta_qty=-used,
                unit=item_unit, actor=user_name, source_channel="MANUAL_FORM", reference_id=ref_id,
                idempotency_key=f"{idemp_base}_USE", notes=f"Daily kitchen usage on {date}",
                allow_negative=True, con=con
            )
        if waste > 0:
            ledger.post_transaction(
                ingredient_id=ing, transaction_type="WASTAGE", quantity=waste, delta_qty=-waste,
                unit=item_unit, actor=user_name, source_channel="MANUAL_FORM", reference_id=ref_id,
                idempotency_key=f"{idemp_base}_WASTE", notes=b.get("wastage_reason") or f"Kitchen wastage on {date}",
                allow_negative=True, con=con
            )

        # Update manual_entries table for full backward compatibility
        con.execute(
            "INSERT INTO manual_entries(date,ingredient_id,opening_stock,received_qty,batch_no,expiry_date,used_qty,"
            "wastage_qty,wastage_reason,closing_stock,days_covered,entered_by,entry_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'ENTERED') ON CONFLICT(date,ingredient_id) DO UPDATE SET "
            "opening_stock=excluded.opening_stock, received_qty=excluded.received_qty, batch_no=excluded.batch_no,"
            "expiry_date=excluded.expiry_date, used_qty=excluded.used_qty, wastage_qty=excluded.wastage_qty,"
            "wastage_reason=excluded.wastage_reason, closing_stock=excluded.closing_stock,"
            "days_covered=excluded.days_covered, entered_by=excluded.entered_by, entry_status='ENTERED'",
            (date, ing, opening, received, batch, b.get("expiry_date") or None, used, waste,
             b.get("wastage_reason") or None, round(closing, 2), gap + 1, user_name)
        )
        con.execute(
            "INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
            (iot.now_str(), user_name, "MANUAL_ENTRY", f"{date} {ing} used={used} closing={closing}")
        )

    ml.invalidate()
    return jsonify(status="saved", closing_stock=round(closing, 2), days_covered=gap + 1), 201


# ------------------------------------------------------------------ traditional staff workflows & document staging
@app.post("/api/traditional/upload")
@auth("staff", "manager", "owner")
def traditional_upload():
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify(error="Empty filename"), 400

    workflow_type = request.form.get("workflow_type", "OPENING_STOCK")
    if workflow_type not in ("OPENING_STOCK", "DELIVERY_INVOICE", "CLOSING_STOCK"):
        return jsonify(error=f"Invalid workflow_type '{workflow_type}'"), 422

    data = file.read()
    if len(data) == 0:
        return jsonify(error="File is empty"), 400
    if len(data) > document_parser.MAX_FILE_SIZE:
        return jsonify(error="File exceeds maximum allowed size of 10 MB"), 413

    file_hash = document_parser.calculate_sha256(data)
    existing = db.query("SELECT * FROM document_uploads WHERE file_hash=?", (file_hash,))
    if existing:
        return jsonify(
            error=f"This document was already uploaded (ID: {existing[0]['upload_id']})",
            upload_id=existing[0]["upload_id"],
            status=existing[0]["status"]
        ), 409

    ingredients = db.query("SELECT * FROM ingredients")
    try:
        extracted = document_parser.extract_document(data, file.filename, workflow_type, ingredients)
    except ValueError as e:
        return jsonify(error=str(e)), 422
    except Exception as e:
        return jsonify(error=f"Extraction failed: {str(e)}"), 500

    upload_id = f"DOC_{datetime.now():%y%m%d%H%M%S}_{uuid.uuid4().hex[:6]}"
    actor = request.user["username"]
    now_ts = iot.now_str()

    with db.tx() as con:
        con.execute(
            """
            INSERT INTO document_uploads (
                upload_id, filename, file_type, file_hash, file_size_bytes,
                workflow_type, status, extracted_payload, raw_document_path,
                uploaded_by, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id, file.filename, extracted["file_type"], file_hash,
                extracted["file_size_bytes"], workflow_type, extracted["status"],
                json.dumps(extracted["rows"]), extracted["raw_document_path"],
                actor, now_ts
            )
        )
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "DOCUMENT_UPLOAD", f"{upload_id} {file.filename} type={workflow_type} status={extracted['status']}")
        )

    role = request.user["role"]
    out_rows = [dict(r) for r in extracted["rows"]]
    if role in ("staff", "manager"):
        for r in out_rows:
            r.pop("unit_price_rs", None)
            r.pop("line_total_rs", None)

    return jsonify({
        "upload_id": upload_id,
        "filename": file.filename,
        "file_type": extracted["file_type"],
        "workflow_type": workflow_type,
        "status": extracted["status"],
        "rows": out_rows,
        "notes": extracted.get("notes", "")
    }), 201


@app.get("/api/traditional/uploads")
@auth("staff", "manager", "owner")
def list_document_uploads():
    role = request.user["role"]
    username = request.user["username"]
    limit = int(request.args.get("limit", 50))
    if role == "staff":
        docs = db.query(
            "SELECT upload_id, filename, file_type, workflow_type, status, uploaded_by, uploaded_at, reviewed_by, reviewed_at "
            "FROM document_uploads WHERE uploaded_by=? ORDER BY uploaded_at DESC LIMIT ?",
            (username, limit)
        )
    else:
        docs = db.query(
            "SELECT upload_id, filename, file_type, workflow_type, status, uploaded_by, uploaded_at, reviewed_by, reviewed_at "
            "FROM document_uploads ORDER BY uploaded_at DESC LIMIT ?",
            (limit,)
        )
    return jsonify(docs)


@app.get("/api/traditional/staged/<upload_id>")
@auth("staff", "manager", "owner")
def get_staged_document(upload_id):
    role = request.user["role"]
    username = request.user["username"]
    docs = db.query("SELECT * FROM document_uploads WHERE upload_id=?", (upload_id,))
    if not docs:
        return jsonify(error="Document not found"), 404
    doc = docs[0]
    if doc["uploaded_by"] != username:
        return jsonify(error="Forbidden: Only the uploader may view their staged document contents"), 403

    rows = json.loads(doc["extracted_payload"])
    if role in ("staff", "manager"):
        for r in rows:
            if "unit_price_rs" in r:
                r["unit_price_rs"] = None
            if "line_total_rs" in r:
                r["line_total_rs"] = None
    return jsonify({
        "upload_id": doc["upload_id"],
        "filename": doc["filename"],
        "file_type": doc["file_type"],
        "workflow_type": doc["workflow_type"],
        "status": doc["status"],
        "uploaded_by": doc["uploaded_by"],
        "uploaded_at": doc["uploaded_at"],
        "rows": rows
    }), 200


@app.put("/api/traditional/staged/<upload_id>")
@auth("staff", "manager", "owner")
def update_staged_document(upload_id):
    role = request.user["role"]
    username = request.user["username"]
    docs = db.query("SELECT * FROM document_uploads WHERE upload_id=?", (upload_id,))
    if not docs:
        return jsonify(error="Document not found"), 404
    doc = docs[0]
    if doc["uploaded_by"] != username:
        return jsonify(error="Forbidden: Only the uploader may edit their staged document"), 403
    if doc["status"] == "POSTED":
        return jsonify(error="Cannot edit a staged document that has already been verified and posted"), 409

    body = request.get_json(force=True, silent=True) or {}
    rows = body.get("rows")
    if not isinstance(rows, list):
        return jsonify(error="'rows' list is required"), 422

    ings = {r["ingredient_id"]: r for r in db.query("SELECT ingredient_id, name, unit FROM ingredients")}
    validated_rows = []
    for r in rows:
        iid = r.get("ingredient_id")
        if iid and iid not in ings:
            return jsonify(error=f"Invalid ingredient_id '{iid}'"), 422

        def to_num(val):
            try:
                v = float(val) if val is not None and val != "" else 0.0
                if v < 0:
                    raise ValueError()
                return v
            except (ValueError, TypeError):
                raise ValueError(f"Invalid non-negative quantity '{val}'")

        try:
            op_q = to_num(r.get("opening_qty"))
            rec_q = to_num(r.get("received_qty"))
            cl_q = to_num(r.get("closing_qty"))
            pr_val = to_num(r.get("unit_price_rs"))
        except ValueError as e:
            return jsonify(error=str(e)), 422

        unit = r.get("unit") or (ings[iid]["unit"] if iid else "kg")
        validated_rows.append({
            "ingredient_id": iid,
            "raw_name": r.get("raw_name") or (ings[iid]["name"] if iid else ""),
            "name": ings[iid]["name"] if iid else r.get("name", ""),
            "opening_qty": op_q,
            "received_qty": rec_q,
            "closing_qty": cl_q,
            "unit": unit,
            "supplier_name": (r.get("supplier_name") or "").strip(),
            "invoice_no": (r.get("invoice_no") or "").strip(),
            "unit_price_rs": pr_val,
            "batch_no": (r.get("batch_no") or "").strip(),
            "expiry_date": (r.get("expiry_date") or "").strip(),
            "confidence": float(r.get("confidence") or 1.0),
            "flags": r.get("flags") or []
        })

    now_ts = iot.now_str()
    with db.tx() as con:
        con.execute(
            """
            UPDATE document_uploads
            SET extracted_payload = ?, reviewed_by = ?, reviewed_at = ?, status = 'NEEDS_REVIEW'
            WHERE upload_id = ?
            """,
            (json.dumps(validated_rows), username, now_ts, upload_id)
        )
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, username, "DOCUMENT_EDIT", f"Updated staged rows for {upload_id} ({len(validated_rows)} rows)")
        )

    out_rows = [dict(r) for r in validated_rows]
    if role in ("staff", "manager"):
        for r in out_rows:
            r["unit_price_rs"] = None
            r["line_total_rs"] = None

    return jsonify({
        "status": "updated",
        "upload_id": upload_id,
        "reviewed_by": username,
        "reviewed_at": now_ts,
        "rows": out_rows
    }), 200


@app.get("/api/traditional/uploads/<upload_id>/file")
@auth("staff", "manager", "owner")
def download_staged_document_file(upload_id):
    role = request.user["role"]
    username = request.user["username"]
    docs = db.query("SELECT * FROM document_uploads WHERE upload_id=?", (upload_id,))
    if not docs:
        return jsonify(error="Document not found"), 404
    doc = docs[0]
    if doc["uploaded_by"] != username:
        return jsonify(error="Forbidden: Only the uploader may download their staged document file"), 403

    raw_path = doc.get("raw_document_path")
    if not raw_path:
        return jsonify(error="Document file record has no stored file path"), 404

    upload_dir_real = os.path.realpath(document_parser.UPLOAD_DIR)
    file_real = os.path.realpath(raw_path)
    if not file_real.startswith(upload_dir_real) or not os.path.isfile(file_real):
        return jsonify(error="File not found on server"), 404

    # Redact financial columns from downloaded CSV files for Staff and Manager
    if role in ("staff", "manager") and (doc["file_type"] == "csv" or file_real.lower().endswith(".csv")):
        import csv
        with open(file_real, "r", encoding="utf-8", errors="ignore") as f_in:
            reader = csv.reader(f_in)
            csv_rows = list(reader)
        if csv_rows:
            header = [h.strip().lower() for h in csv_rows[0]]
            redact_indices = {
                i for i, h in enumerate(header)
                if h in ("unit_price_rs", "line_total_rs", "unit_price", "price", "line_total", "total_amount_rs")
            }
            if redact_indices:
                clean_rows = []
                for row in csv_rows:
                    clean_row = [val for i, val in enumerate(row) if i not in redact_indices]
                    clean_rows.append(clean_row)
                out_io = io.StringIO()
                writer = csv.writer(out_io)
                writer.writerows(clean_rows)
                mem = io.BytesIO(out_io.getvalue().encode("utf-8"))
                return send_file(
                    mem,
                    mimetype="text/csv",
                    as_attachment=True,
                    download_name=doc.get("filename") or os.path.basename(file_real)
                )

    return send_file(
        file_real,
        as_attachment=True,
        download_name=doc.get("filename") or os.path.basename(file_real)
    )


@app.get("/api/traditional/opening")
@auth("staff", "manager", "owner")
def traditional_get_opening():
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    ings = db.query("SELECT ingredient_id, name, unit FROM ingredients ORDER BY ingredient_id")
    counts = {r["ingredient_id"]: r for r in db.query("SELECT * FROM daily_stock_counts WHERE date=? AND count_type='AM_OPENING'", (date,))}

    prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_closings = {r["ingredient_id"]: r["physical_qty"] for r in db.query("SELECT ingredient_id, physical_qty FROM daily_stock_counts WHERE date=? AND count_type='PM_CLOSING'", (prev_date,))}

    rows = []
    for ing in ings:
        iid = ing["ingredient_id"]
        c_rec = counts.get(iid)
        suggested = prev_closings.get(iid, ledger.get_book_balance(iid))
        rows.append({
            "ingredient_id": iid,
            "name": ing["name"],
            "unit": ing["unit"],
            "physical_qty": c_rec["physical_qty"] if c_rec else suggested,
            "recorded": c_rec is not None,
            "status": c_rec["status"] if c_rec else "PENDING",
            "verified_by": c_rec.get("verified_by") if c_rec else None,
            "verified_at": c_rec.get("verified_at") if c_rec else None,
        })
    return jsonify({"date": date, "rows": rows, "posted": all(r["recorded"] for r in rows) if rows else False})


@app.post("/api/traditional/opening")
@auth("staff", "manager", "owner")
def traditional_post_opening():
    role = request.user["role"]
    b = request.get_json(force=True, silent=True) or {}
    date = b.get("date")
    counts = b.get("counts") or []
    doc_id = b.get("document_upload_id")
    actor = request.user["username"]
    now_ts = iot.now_str()

    if not date or not counts:
        return jsonify(error="Date and non-empty counts list are required"), 422
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="Invalid date format, expected YYYY-MM-DD"), 422

    for item in counts:
        try:
            qty = float(item["physical_qty"])
        except (KeyError, ValueError, TypeError):
            return jsonify(error=f"Invalid physical quantity for {item.get('ingredient_id')}"), 422
        if qty < 0:
            return jsonify(error=f"Physical opening stock cannot be negative (got {qty})"), 422

    with db.tx() as con:
        # Check document ownership if doc_id provided
        if doc_id:
            doc_row = con.execute("SELECT upload_id, uploaded_by, status FROM document_uploads WHERE upload_id=?", (doc_id,)).fetchone()
            if not doc_row:
                return jsonify(error="Document upload not found"), 404
            if doc_row[1] != actor:
                return jsonify(error="Forbidden: Only the uploader may verify and post their staged document"), 403

        existing = con.execute("SELECT ingredient_id, physical_qty FROM daily_stock_counts WHERE date=? AND count_type='AM_OPENING'", (date,)).fetchall()
        existing_map = {r[0]: float(r[1]) for r in existing}

        all_identical = len(existing_map) == len(counts) and len(counts) > 0 and all(
            abs(existing_map.get(c["ingredient_id"], -999) - float(c["physical_qty"])) < 1e-4
            for c in counts
        )
        if all_identical:
            return jsonify(status="posted", date=date, duplicate=True, counts_recorded=len(counts)), 200

        ing_rows = con.execute("SELECT ingredient_id, name, unit FROM ingredients").fetchall()
        ing_recs = {r[0]: {"name": r[1], "unit": r[2]} for r in ing_rows}

        adjustments_posted = []
        for item in counts:
            iid = item["ingredient_id"]
            if iid not in ing_recs:
                return jsonify(error=f"Unknown ingredient_id '{iid}'"), 422
            canonical_unit = ing_recs[iid]["unit"]
            item_unit = (item.get("unit") or canonical_unit).strip()

            try:
                raw_qty = float(item["physical_qty"])
            except (KeyError, ValueError, TypeError):
                return jsonify(error=f"Invalid physical quantity for {iid}"), 422
            if raw_qty < 0:
                return jsonify(error=f"Opening physical stock cannot be negative (got {raw_qty})"), 422

            if not units.is_compatible_unit(item_unit, canonical_unit):
                return jsonify(error=f"Incompatible unit '{item_unit}' for {iid} (expected '{canonical_unit}')"), 422

            qty = units.convert_quantity(raw_qty, from_unit=item_unit, to_unit=canonical_unit)
            notes = item.get("notes") or ""
            ref_id = f"OPENING_DISCREPANCY:{date}:{iid}"

            # Controlled reversal of any existing unreversed opening adjustment for this date/ingredient
            unreversed = con.execute(
                """
                SELECT t.transaction_id FROM inventory_transactions t
                WHERE t.reference_id = ?
                  AND t.transaction_type = 'ADJUSTMENT'
                  AND NOT EXISTS (SELECT 1 FROM inventory_transactions r WHERE r.reversal_ref_id = t.transaction_id)
                """,
                (ref_id,)
            ).fetchall()
            for utx in unreversed:
                try:
                    ledger.reverse_transaction(
                        original_tx_id=utx[0],
                        actor=actor,
                        reason=f"Corrected morning opening physical stock for {date}",
                        con=con
                    )
                except ValueError:
                    pass

            # Calculate opening discrepancy against authoritative current book balance
            current_book = ledger.get_book_balance(iid, con=con)
            opening_adj = round(qty - current_book, 4)

            adj_tx_id = None
            if opening_adj != 0.0:
                idemp_key = f"OPENING_DISC_{date}_{iid}_{uuid.uuid4().hex[:8]}"
                tx = ledger.post_transaction(
                    ingredient_id=iid,
                    transaction_type="ADJUSTMENT",
                    quantity=abs(opening_adj),
                    delta_qty=opening_adj,
                    unit=ing_recs.get(iid, {}).get("unit", "kg"),
                    actor=actor,
                    source_channel="OPENING_COUNT",
                    reference_id=ref_id,
                    idempotency_key=idemp_key,
                    notes=f"Morning physical opening stock discrepancy adjustment on {date} ({'+' if opening_adj > 0 else ''}{opening_adj})",
                    allow_negative=True,
                    con=con
                )
                adj_tx_id = tx.get("transaction_id")
                adjustments_posted.append({
                    "ingredient_id": iid,
                    "previous_book_balance": current_book,
                    "physical_opening_qty": qty,
                    "opening_adjustment": opening_adj,
                    "transaction_id": adj_tx_id
                })

            cid = f"CNT_AM_{date}_{iid}"
            con.execute(
                """
                INSERT INTO daily_stock_counts (
                    count_id, date, ingredient_id, count_type, physical_qty,
                    entered_by, verified_by, verified_at, status, notes, created_at
                ) VALUES (?, ?, ?, 'AM_OPENING', ?, ?, ?, ?, 'POSTED', ?, ?)
                ON CONFLICT(date, ingredient_id, count_type) DO UPDATE SET
                    physical_qty = excluded.physical_qty,
                    entered_by = excluded.entered_by,
                    verified_by = excluded.verified_by,
                    verified_at = excluded.verified_at,
                    status = 'POSTED',
                    notes = excluded.notes
                """,
                (cid, date, iid, qty, actor, actor, now_ts, notes, now_ts)
            )

        if doc_id:
            con.execute(
                "UPDATE document_uploads SET status='POSTED', reviewed_by=?, reviewed_at=? WHERE upload_id=?",
                (actor, now_ts, doc_id)
            )

        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "TRADITIONAL_AM_OPENING", f"Recorded opening stock for {date} ({len(counts)} items, {len(adjustments_posted)} adjustments)")
        )

    ml.invalidate()
    return jsonify(
        status="posted",
        date=date,
        count_type="AM_OPENING",
        counts_recorded=len(counts),
        adjustments=adjustments_posted
    ), 201


@app.get("/api/traditional/deliveries")
@auth("staff", "manager", "owner")
def traditional_get_deliveries():
    role = request.user["role"]
    date = request.args.get("date")
    sql = """
        SELECT i.item_id, i.invoice_id, i.supplier_name, i.invoice_no, i.ingredient_id,
               ing.name as ingredient_name, i.billed_qty, i.unit, i.inventory_qty,
               i.unit_price_rs, i.line_total_rs, i.batch_no, i.expiry_date,
               i.transaction_id, i.created_at, inv.invoice_date, inv.received_by
        FROM supplier_invoice_items i
        JOIN supplier_invoices inv USING (invoice_id)
        JOIN ingredients ing ON ing.ingredient_id = i.ingredient_id
    """
    args = []
    if date:
        sql += " WHERE inv.invoice_date = ?"
        args.append(date)
    sql += " ORDER BY i.created_at DESC"
    rows = db.query(sql, args)
    if role in ("staff", "manager"):
        for r in rows:
            r["unit_price_rs"] = None
            r["line_total_rs"] = None
    return jsonify(rows)


@app.post("/api/traditional/delivery")
@app.post("/api/traditional/deliveries")
@auth("staff", "manager", "owner")
def traditional_post_delivery():
    role = request.user["role"]
    b = request.get_json(force=True, silent=True) or {}
    supplier = (b.get("supplier_name") or "").strip()
    inv_no = (b.get("invoice_no") or "").strip()
    inv_date = (b.get("invoice_date") or "").strip()
    items = b.get("items") or []
    doc_id = b.get("document_upload_id")
    actor = request.user["username"]
    now_ts = iot.now_str()

    if not supplier or not inv_no or not inv_date or not items:
        return jsonify(error="supplier_name, invoice_no, invoice_date, and non-empty items are required"), 422
    try:
        datetime.strptime(inv_date, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="Invalid invoice_date format, expected YYYY-MM-DD"), 422

    for item in items:
        if not item.get("ingredient_id"):
            return jsonify(error="ingredient_id is required for every line item"), 422
        try:
            qty = float(item["billed_qty"])
        except (KeyError, ValueError, TypeError):
            return jsonify(error=f"Invalid billed_qty for {item.get('ingredient_id')}"), 422
        if qty <= 0:
            return jsonify(error=f"Billed quantity must be strictly greater than 0 (got {qty})"), 422

    inv_id = f"INV_{datetime.now():%y%m%d%H%M%S}_{uuid.uuid4().hex[:6]}"

    with db.tx() as con:
        # Check document ownership if doc_id provided
        if doc_id:
            doc_row = con.execute("SELECT upload_id, uploaded_by, status FROM document_uploads WHERE upload_id=?", (doc_id,)).fetchone()
            if not doc_row:
                return jsonify(error="Document upload not found"), 404
            if doc_row[1] != actor:
                return jsonify(error="Forbidden: Only the uploader may verify and post their staged document"), 403

        # Check existing invoice items for exact retry vs collision
        existing_items = con.execute(
            "SELECT item_id, ingredient_id, billed_qty, unit, batch_no, expiry_date FROM supplier_invoice_items WHERE supplier_name=? AND invoice_no=?",
            (supplier, inv_no)
        ).fetchall()
        if existing_items:
            def item_signature(it):
                iid = it.get("ingredient_id")
                b = (it.get("batch_no") or "").strip() or f"{iid}-D{inv_date.replace('-', '')}"
                e = (it.get("expiry_date") or "").strip() or None
                return (
                    iid,
                    round(float(it.get("billed_qty") or 0.0), 4),
                    b,
                    e or ""
                )

            existing_sigs = sorted([
                (r[1], round(float(r[2]), 4), (r[4] or "").strip(), (r[5] or "").strip())
                for r in existing_items
            ])
            incoming_sigs = sorted([item_signature(it) for it in items])

            if existing_sigs == incoming_sigs:
                return jsonify(status="posted", supplier_name=supplier, invoice_no=inv_no, duplicate=True), 200

            return jsonify(
                error=f"Invoice '{inv_no}' from '{supplier}' has already been posted with different line items or quantities. Deliveries cannot be posted twice."
            ), 409

        # Fetch authoritative ingredient information
        ing_rows = con.execute("SELECT ingredient_id, name, unit FROM ingredients").fetchall()
        ing_map = {r[0]: {"name": r[1], "unit": r[2]} for r in ing_rows}

        # Validate units and calculate totals
        total_amt = 0.0
        normalized_items = []
        for idx, item in enumerate(items):
            iid = item["ingredient_id"]
            if iid not in ing_map:
                return jsonify(error=f"Unknown ingredient_id '{iid}'"), 422

            auth_unit = ing_map[iid]["unit"]
            billed_unit = (item.get("unit") or auth_unit).strip()
            billed_qty = round(float(item["billed_qty"]), 4)

            try:
                inventory_qty = units.convert_quantity(billed_qty, from_unit=billed_unit, to_unit=auth_unit)
            except ValueError as e:
                return jsonify(error=f"Unit conversion error for {iid}: {str(e)}"), 422

            unit_price = round(float(item.get("unit_price_rs") or 0.0), 2)
            line_total = round(billed_qty * unit_price, 2)
            total_amt += line_total

            batch = (item.get("batch_no") or "").strip() or f"{iid}-D{inv_date.replace('-', '')}"
            expiry = (item.get("expiry_date") or "").strip() or None

            normalized_items.append({
                "idx": idx,
                "ingredient_id": iid,
                "billed_qty": billed_qty,
                "billed_unit": billed_unit,
                "inventory_qty": inventory_qty,
                "auth_unit": auth_unit,
                "unit_price_rs": unit_price,
                "line_total_rs": line_total,
                "batch_no": batch,
                "expiry_date": expiry
            })

        try:
            con.execute(
                """
                INSERT INTO supplier_invoices (
                    invoice_id, supplier_name, invoice_no, invoice_date, total_amount_rs,
                    status, received_by, verified_by, verified_at, document_upload_id, created_at
                ) VALUES (?, ?, ?, ?, ?, 'POSTED', ?, ?, ?, ?, ?)
                """,
                (inv_id, supplier, inv_no, inv_date, round(total_amt, 2), actor, actor, now_ts, doc_id, now_ts)
            )
        except sqlite3.IntegrityError:
            return jsonify(
                error=f"Invoice '{inv_no}' from '{supplier}' has already been posted. Deliveries cannot be posted twice."
            ), 409

        posted_items = []
        for nit in normalized_items:
            iid = nit["ingredient_id"]
            batch = nit["batch_no"]
            expiry = nit["expiry_date"]
            idx = nit["idx"]

            idemp = f"INV_{supplier}_{inv_no}_{iid}_{batch}_{idx}"
            ref_id = f"INVOICE:{inv_no}:{iid}:{batch}"

            tx = ledger.post_transaction(
                ingredient_id=iid,
                transaction_type="STOCK_IN",
                quantity=nit["inventory_qty"],
                delta_qty=+nit["inventory_qty"],
                unit=nit["auth_unit"],
                actor=actor,
                source_channel="DELIVERY_INVOICE",
                reference_id=ref_id,
                batch_no=batch,
                expiry_date=expiry,
                idempotency_key=idemp,
                notes=f"Supplier delivery: {supplier} Inv #{inv_no} ({nit['billed_qty']} {nit['billed_unit']})",
                allow_negative=True,
                con=con
            )

            item_id = f"ITM_{uuid.uuid4().hex[:10]}"
            try:
                con.execute(
                    """
                    INSERT INTO supplier_invoice_items (
                        item_id, invoice_id, supplier_name, invoice_no, ingredient_id,
                        billed_qty, unit, inventory_qty, unit_price_rs, line_total_rs, batch_no,
                        expiry_date, transaction_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id, inv_id, supplier, inv_no, iid, nit["billed_qty"], nit["billed_unit"],
                        nit["inventory_qty"], nit["unit_price_rs"], nit["line_total_rs"], batch,
                        expiry, tx.get("transaction_id"), now_ts
                    )
                )
            except sqlite3.IntegrityError:
                return jsonify(
                    error=f"Duplicate line item detected on invoice '{inv_no}' for ingredient '{iid}' batch '{batch}'"
                ), 409
            item_resp = {
                "item_id": item_id,
                "ingredient_id": iid,
                "billed_qty": nit["billed_qty"],
                "unit": nit["billed_unit"],
                "inventory_qty": nit["inventory_qty"],
                "batch_no": batch,
                "expiry_date": expiry,
                "transaction_id": tx.get("transaction_id")
            }
            if role == "owner":
                item_resp["unit_price_rs"] = nit["unit_price_rs"]
                item_resp["line_total_rs"] = nit["line_total_rs"]
            posted_items.append(item_resp)

        if doc_id:
            con.execute(
                "UPDATE document_uploads SET status='POSTED', reviewed_by=?, reviewed_at=? WHERE upload_id=?",
                (actor, now_ts, doc_id)
            )

        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "SUPPLIER_DELIVERY", f"{supplier} Inv #{inv_no} ({len(items)} items)")
        )

    ml.invalidate()
    res_obj = {
        "status": "posted",
        "invoice_id": inv_id,
        "supplier_name": supplier,
        "invoice_no": inv_no,
        "items_posted": len(posted_items),
        "items": posted_items
    }
    if role == "owner":
        res_obj["total_amount_rs"] = round(total_amt, 2)
    return jsonify(res_obj), 201


@app.get("/api/traditional/closing")
@auth("staff", "manager", "owner")
def traditional_get_closing():
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    ings = db.query("SELECT ingredient_id, name, unit FROM ingredients ORDER BY ingredient_id")

    openings = {r["ingredient_id"]: r["physical_qty"] for r in db.query(
        "SELECT ingredient_id, physical_qty FROM daily_stock_counts WHERE date=? AND count_type='AM_OPENING'", (date,)
    )}

    deliveries = {r["ingredient_id"]: r["total_qty"] for r in db.query(
        """
        SELECT i.ingredient_id, SUM(COALESCE(i.inventory_qty, i.billed_qty)) as total_qty
        FROM supplier_invoice_items i
        JOIN supplier_invoices inv USING (invoice_id)
        WHERE inv.invoice_date = ?
        GROUP BY i.ingredient_id
        """,
        (date,)
    )}

    closings = {r["ingredient_id"]: r for r in db.query(
        "SELECT * FROM daily_stock_counts WHERE date=? AND count_type='PM_CLOSING'", (date,)
    )}

    depletions = {r["ingredient_id"]: r for r in db.query("SELECT * FROM depletion_logs WHERE date=?", (date,))}

    rows = []
    for ing in ings:
        iid = ing["ingredient_id"]
        op_qty = openings.get(iid, 0.0)
        del_qty = deliveries.get(iid, 0.0)
        avail = round(op_qty + del_qty, 4)
        cl_rec = closings.get(iid)
        cl_qty = cl_rec["physical_qty"] if cl_rec else avail
        dep_rec = depletions.get(iid)
        dep_qty = dep_rec["calculated_depletion_kg"] if dep_rec else round(avail - cl_qty, 4)

        rows.append({
            "ingredient_id": iid,
            "name": ing["name"],
            "unit": ing["unit"],
            "opening_qty": op_qty,
            "has_opening": iid in openings,
            "deliveries_qty": del_qty,
            "available_qty": avail,
            "physical_closing_qty": cl_qty,
            "calculated_depletion_kg": dep_qty,
            "closing_recorded": cl_rec is not None,
            "verified_by": cl_rec.get("verified_by") if cl_rec else None,
            "verified_at": cl_rec.get("verified_at") if cl_rec else None,
        })

    return jsonify({"date": date, "rows": rows, "posted": all(r["closing_recorded"] for r in rows) if rows else False})


@app.post("/api/traditional/closing")
@auth("staff", "manager", "owner")
def traditional_post_closing():
    role = request.user["role"]
    b = request.get_json(force=True, silent=True) or {}
    date = b.get("date")
    counts = b.get("counts") or []
    doc_id = b.get("document_upload_id")
    actor = request.user["username"]
    now_ts = iot.now_str()

    if not date or not counts:
        return jsonify(error="Date and non-empty counts list are required"), 422
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="Invalid date format, expected YYYY-MM-DD"), 422

    for item in counts:
        try:
            qty = float(item["physical_qty"])
        except (KeyError, ValueError, TypeError):
            return jsonify(error=f"Invalid physical quantity for {item.get('ingredient_id')}"), 422
        if qty < 0:
            return jsonify(error=f"Closing physical stock cannot be negative (got {qty})"), 422

    depletions_summary = []
    with db.tx() as con:
        # Check document ownership if doc_id provided
        if doc_id:
            doc_row = con.execute("SELECT upload_id, uploaded_by, status FROM document_uploads WHERE upload_id=?", (doc_id,)).fetchone()
            if not doc_row:
                return jsonify(error="Document upload not found"), 404
            if doc_row[1] != actor:
                return jsonify(error="Forbidden: Only the uploader may verify and post their staged document"), 403

        existing_closings = con.execute(
            "SELECT ingredient_id, physical_qty FROM daily_stock_counts WHERE date=? AND count_type='PM_CLOSING'",
            (date,)
        ).fetchall()
        existing_map = {r[0]: float(r[1]) for r in existing_closings}

        all_identical = len(existing_map) == len(counts) and len(counts) > 0 and all(
            abs(existing_map.get(c["ingredient_id"], -999) - float(c["physical_qty"])) < 1e-4
            for c in counts
        )
        if all_identical:
            return jsonify(status="posted", date=date, duplicate=True, items_reconciled=len(counts)), 200

        openings_rows = con.execute(
            "SELECT ingredient_id, physical_qty FROM daily_stock_counts WHERE date=? AND count_type='AM_OPENING'",
            (date,)
        ).fetchall()
        openings_map = {r[0]: float(r[1]) for r in openings_rows}

        deliveries_rows = con.execute(
            """
            SELECT i.ingredient_id, COALESCE(SUM(COALESCE(i.inventory_qty, i.billed_qty)), 0.0)
            FROM supplier_invoice_items i
            JOIN supplier_invoices inv USING (invoice_id)
            WHERE inv.invoice_date = ?
            GROUP BY i.ingredient_id
            """,
            (date,)
        ).fetchall()
        deliveries_map = {r[0]: float(r[1]) for r in deliveries_rows}

        ing_rows = con.execute("SELECT ingredient_id, name, unit FROM ingredients").fetchall()
        ing_map = {r[0]: {"name": r[1], "unit": r[2]} for r in ing_rows}

        for item in counts:
            iid = item["ingredient_id"]
            if iid not in ing_map:
                return jsonify(error=f"Unknown ingredient_id '{iid}'"), 422

            canonical_unit = ing_map[iid]["unit"]
            item_unit = (item.get("unit") or canonical_unit).strip()

            try:
                raw_closing = float(item["physical_qty"])
            except (KeyError, ValueError, TypeError):
                return jsonify(error=f"Invalid physical quantity for {iid}"), 422
            if raw_closing < 0:
                return jsonify(error=f"Closing physical stock cannot be negative (got {raw_closing})"), 422

            if not units.is_compatible_unit(item_unit, canonical_unit):
                return jsonify(error=f"Incompatible unit '{item_unit}' for {iid} (expected '{canonical_unit}')"), 422

            closing_qty = units.convert_quantity(raw_closing, from_unit=item_unit, to_unit=canonical_unit)
            notes = item.get("notes") or ""

            opening_qty = openings_map.get(iid, ledger.get_book_balance(iid, con=con))
            deliv_qty = deliveries_map.get(iid, 0.0)
            depletion = round(opening_qty + deliv_qty - closing_qty, 4)

            ref_id = f"CLOSING:{date}:{iid}"
            idemp_key = f"CLOSING_{date}_{iid}"

            unreversed = con.execute(
                """
                SELECT t.transaction_id FROM inventory_transactions t
                WHERE t.reference_id = ?
                  AND t.transaction_type IN ('CONSUMPTION', 'ADJUSTMENT')
                  AND NOT EXISTS (SELECT 1 FROM inventory_transactions r WHERE r.reversal_ref_id = t.transaction_id)
                """,
                (ref_id,)
            ).fetchall()
            for utx in unreversed:
                try:
                    ledger.reverse_transaction(
                        original_tx_id=utx[0],
                        actor=actor,
                        reason=f"Corrected closing physical stock for {date}",
                        con=con
                    )
                except ValueError:
                    pass

            # Post closing reconciliation movement EXACTLY ONCE with canonical unit
            if depletion >= 0:
                tx = ledger.post_transaction(
                    ingredient_id=iid,
                    transaction_type="CONSUMPTION",
                    quantity=depletion,
                    delta_qty=-depletion,
                    unit=canonical_unit,
                    actor=actor,
                    source_channel="CLOSING_COUNT",
                    reference_id=ref_id,
                    idempotency_key=f"{idemp_key}_USE",
                    notes=f"Daily kitchen depletion reconciliation for {date}",
                    allow_negative=True,
                    con=con
                )
            else:
                overage = abs(depletion)
                tx = ledger.post_transaction(
                    ingredient_id=iid,
                    transaction_type="ADJUSTMENT",
                    quantity=overage,
                    delta_qty=+overage,
                    unit=canonical_unit,
                    actor=actor,
                    source_channel="CLOSING_COUNT",
                    reference_id=ref_id,
                    idempotency_key=f"{idemp_key}_ADJ",
                    notes=f"Daily physical stock overage adjustment on {date}",
                    allow_negative=True,
                    con=con
                )

            dep_id = f"DEP_{date}_{iid}"
            con.execute(
                """
                INSERT INTO depletion_logs (
                    depletion_id, date, ingredient_id, opening_qty, deliveries_qty,
                    closing_qty, calculated_depletion_kg, unexplained_depletion_kg,
                    status, reconciliation_transaction_id, recorded_by, recorded_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNCLASSIFIED', ?, ?, ?, ?)
                ON CONFLICT(date, ingredient_id) DO UPDATE SET
                    opening_qty = excluded.opening_qty,
                    deliveries_qty = excluded.deliveries_qty,
                    closing_qty = excluded.closing_qty,
                    calculated_depletion_kg = excluded.calculated_depletion_kg,
                    unexplained_depletion_kg = excluded.unexplained_depletion_kg,
                    reconciliation_transaction_id = excluded.reconciliation_transaction_id,
                    recorded_by = excluded.recorded_by,
                    recorded_at = excluded.recorded_at,
                    notes = excluded.notes
                """,
                (
                    dep_id, date, iid, opening_qty, deliv_qty, closing_qty,
                    depletion, max(0.0, depletion), tx.get("transaction_id"),
                    actor, now_ts, notes
                )
            )

            cid = f"CNT_PM_{date}_{iid}"
            con.execute(
                """
                INSERT INTO daily_stock_counts (
                    count_id, date, ingredient_id, count_type, physical_qty,
                    entered_by, verified_by, verified_at, status, notes, created_at
                ) VALUES (?, ?, ?, 'PM_CLOSING', ?, ?, ?, ?, 'POSTED', ?, ?)
                ON CONFLICT(date, ingredient_id, count_type) DO UPDATE SET
                    physical_qty = excluded.physical_qty,
                    entered_by = excluded.entered_by,
                    verified_by = excluded.verified_by,
                    verified_at = excluded.verified_at,
                    status = 'POSTED',
                    notes = excluded.notes
                """,
                (cid, date, iid, closing_qty, actor, actor, now_ts, notes, now_ts)
            )

            con.execute(
                """
                INSERT INTO manual_entries (
                    date, ingredient_id, opening_stock, received_qty, batch_no, expiry_date,
                    used_qty, wastage_qty, wastage_reason, closing_stock, days_covered, entered_by, entry_status
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, 0.0, NULL, ?, 1, ?, 'ENTERED')
                ON CONFLICT(date, ingredient_id) DO UPDATE SET
                    opening_stock = excluded.opening_stock,
                    received_qty = excluded.received_qty,
                    used_qty = excluded.used_qty,
                    closing_stock = excluded.closing_stock,
                    entered_by = excluded.entered_by,
                    entry_status = 'ENTERED'
                """,
                (date, iid, opening_qty, deliv_qty, max(0.0, depletion), closing_qty, actor)
            )

            depletions_summary.append({
                "ingredient_id": iid,
                "opening_qty": opening_qty,
                "deliveries_qty": deliv_qty,
                "closing_qty": closing_qty,
                "depletion_kg": depletion,
                "transaction_id": tx.get("transaction_id")
            })

        if doc_id:
            con.execute(
                "UPDATE document_uploads SET status='POSTED', reviewed_by=?, reviewed_at=? WHERE upload_id=?",
                (actor, now_ts, doc_id)
            )

        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "TRADITIONAL_PM_CLOSING", f"Reconciled closing stock for {date} ({len(counts)} items)")
        )

    ml.invalidate()
    return jsonify(
        status="posted",
        date=date,
        count_type="PM_CLOSING",
        items_reconciled=len(depletions_summary),
        depletions=depletions_summary
    ), 201


@app.get("/api/traditional/status")
@auth("staff", "manager", "owner")
def traditional_daily_status():
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    ings_count = db.query("SELECT COUNT(*) as c FROM ingredients")[0]["c"]

    op_counts = db.query("SELECT COUNT(*) as c FROM daily_stock_counts WHERE date=? AND count_type='AM_OPENING'", (date,))[0]["c"]
    cl_counts = db.query("SELECT COUNT(*) as c FROM daily_stock_counts WHERE date=? AND count_type='PM_CLOSING'", (date,))[0]["c"]

    deliv_summary = db.query(
        """
        SELECT COUNT(DISTINCT i.invoice_id) as inv_count, COALESCE(SUM(i.billed_qty), 0.0) as total_kg
        FROM supplier_invoice_items i
        JOIN supplier_invoices inv USING (invoice_id)
        WHERE inv.invoice_date = ?
        """,
        (date,)
    )[0]

    depletions = db.query("SELECT ingredient_id, calculated_depletion_kg, status FROM depletion_logs WHERE date=?", (date,))

    return jsonify({
        "date": date,
        "opening_status": "POSTED" if op_counts >= ings_count else "PARTIAL" if op_counts > 0 else "PENDING",
        "opening_count": op_counts,
        "deliveries_invoices_count": deliv_summary["inv_count"],
        "deliveries_total_kg": round(float(deliv_summary["total_kg"]), 2),
        "closing_status": "POSTED" if cl_counts >= ings_count else "PARTIAL" if cl_counts > 0 else "PENDING",
        "closing_count": cl_counts,
        "unexplained_depletions_count": sum(1 for d in depletions if d["status"] != "CLASSIFIED"),
        "depletions": depletions
    })


# ------------------------------------------------------------------ Manager Depletion Investigation & Zero-Sum Wastage Classification (Phase 3)
VALID_CLASSIFICATION_CATEGORIES = (
    "SPOILAGE",
    "EXPIRED",
    "PREPARATION_LOSS",
    "SPILLAGE",
    "DAMAGE",
    "THEFT",
    "MEASUREMENT_ERROR",
    "NORMAL_CONSUMPTION",
    "OTHER_UNEXPLAINED",
)


@app.get("/api/manager/depletions")
@app.get("/api/manager/depletions/dashboard")
@auth("manager", "owner")
def manager_depletions_dashboard():
    """
    Investigation dashboard metrics:
    Unclassified count, total unclassified kg by ingredient, awaiting investigation qty,
    classified qty by category, historical investigation count.
    Strictly redacts financial / rupee data for managers.
    """
    role = request.user["role"]

    # 1. Unclassified depletions count and awaiting investigation qty
    summary = db.query(
        """
        SELECT COUNT(*) as unclassified_count,
               COALESCE(SUM(unexplained_depletion_kg), 0.0) as awaiting_qty_kg
        FROM depletion_logs
        WHERE calculated_depletion_kg > 0 AND unexplained_depletion_kg > 0
        """
    )[0]

    # 2. Total unclassified kg by ingredient
    by_ingredient = db.query(
        """
        SELECT d.ingredient_id, i.name as ingredient_name, i.unit,
               ROUND(SUM(d.unexplained_depletion_kg), 4) as unclassified_kg,
               COUNT(*) as record_count
        FROM depletion_logs d
        JOIN ingredients i USING (ingredient_id)
        WHERE d.calculated_depletion_kg > 0 AND d.unexplained_depletion_kg > 0
        GROUP BY d.ingredient_id, i.name, i.unit
        ORDER BY unclassified_kg DESC
        """
    )

    # 3. Classified quantity by category
    by_category_rows = db.query(
        """
        SELECT category, ROUND(SUM(classified_qty), 4) as total_kg, COUNT(*) as count
        FROM depletion_classifications
        WHERE status = 'ACTIVE'
        GROUP BY category
        ORDER BY total_kg DESC
        """
    )
    by_category = {cat: 0.0 for cat in VALID_CLASSIFICATION_CATEGORIES}
    category_counts = {cat: 0 for cat in VALID_CLASSIFICATION_CATEGORIES}
    for r in by_category_rows:
        by_category[r["category"]] = r["total_kg"]
        category_counts[r["category"]] = r["count"]

    # 4. Total historical classifications & investigations
    hist_stats = db.query(
        """
        SELECT COUNT(*) as total_records,
               SUM(CASE WHEN status = 'CLASSIFIED' THEN 1 ELSE 0 END) as classified_count,
               SUM(CASE WHEN status = 'INVESTIGATING' THEN 1 ELSE 0 END) as investigating_count,
               SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) as resolved_count
        FROM depletion_logs
        """
    )[0]

    total_classifications_count = db.query(
        "SELECT COUNT(*) as c FROM depletion_classifications WHERE status = 'ACTIVE'"
    )[0]["c"]

    res = {
        "unclassified_count": summary["unclassified_count"],
        "awaiting_investigation_qty": round(float(summary["awaiting_qty_kg"]), 4),
        "total_unclassified_kg_by_ingredient": by_ingredient,
        "classified_by_category": by_category,
        "classified_category_counts": category_counts,
        "historical_investigation_records": hist_stats["total_records"] or 0,
        "investigating_count": hist_stats["investigating_count"] or 0,
        "classified_records_count": hist_stats["classified_count"] or 0,
        "resolved_records_count": hist_stats["resolved_count"] or 0,
        "active_classifications_count": total_classifications_count,
    }

    # Strict financial redaction: Only Owner gets monetary loss estimates
    if role == "owner":
        total_loss_rs = db.query(
            """
            SELECT COALESCE(SUM(c.classified_qty * i.unit_cost_rs), 0.0) as loss_rs
            FROM depletion_classifications c
            JOIN depletion_logs d USING (depletion_id)
            JOIN ingredients i ON d.ingredient_id = i.ingredient_id
            WHERE c.status = 'ACTIVE'
            """
        )[0]["loss_rs"]
        res["total_estimated_wastage_rs"] = round(float(total_loss_rs), 2)

    return jsonify(res)


@app.get("/api/manager/depletions/list")
@auth("manager", "owner")
def manager_depletions_list():
    """
    List depletion records for investigation.
    Filters: date, start_date, end_date, ingredient_id, status, unclassified_only.
    Redacts financial metrics for managers.
    """
    role = request.user["role"]
    date_param = request.args.get("date")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    iid_param = request.args.get("ingredient_id")
    status_param = request.args.get("status")
    unclassified_only = request.args.get("unclassified_only", "").lower() in ("true", "1")

    sql = """
        SELECT d.depletion_id, d.date, d.ingredient_id, i.name as ingredient_name, i.unit,
               d.opening_qty, d.deliveries_qty, d.closing_qty,
               d.calculated_depletion_kg, d.unexplained_depletion_kg,
               d.status, d.notes, d.resolution_notes, d.reconciliation_transaction_id,
               d.recorded_by, d.recorded_at, d.resolved_by, d.resolved_at,
               i.unit_cost_rs
        FROM depletion_logs d
        JOIN ingredients i USING (ingredient_id)
        WHERE 1=1
    """
    args = []

    if date_param:
        sql += " AND d.date = ?"
        args.append(date_param)
    if start_date:
        sql += " AND d.date >= ?"
        args.append(start_date)
    if end_date:
        sql += " AND d.date <= ?"
        args.append(end_date)
    if iid_param:
        sql += " AND d.ingredient_id = ?"
        args.append(iid_param)
    if status_param:
        sql += " AND d.status = ?"
        args.append(status_param.upper())
    if unclassified_only:
        sql += " AND d.unexplained_depletion_kg > 0 AND d.calculated_depletion_kg > 0"

    sql += " ORDER BY d.date DESC, d.ingredient_id ASC"

    rows = db.query(sql, args)

    # Fetch active classifications grouped by depletion_id
    cls_sums = {
        r["depletion_id"]: r["sum_qty"]
        for r in db.query(
            """
            SELECT depletion_id, ROUND(SUM(classified_qty), 4) as sum_qty
            FROM depletion_classifications
            WHERE status = 'ACTIVE'
            GROUP BY depletion_id
            """
        )
    }

    results = []
    for r in rows:
        dep_id = r["depletion_id"]
        total_dep = round(float(r["calculated_depletion_kg"]), 4)
        classified_qty = round(float(cls_sums.get(dep_id, 0.0)), 4)
        remaining_unclassified = max(0.0, round(total_dep - classified_qty, 4))

        item = {
            "depletion_id": dep_id,
            "date": r["date"],
            "ingredient_id": r["ingredient_id"],
            "ingredient_name": r["ingredient_name"],
            "unit": r["unit"],
            "opening_qty": round(float(r["opening_qty"]), 4),
            "deliveries_qty": round(float(r["deliveries_qty"]), 4),
            "closing_qty": round(float(r["closing_qty"]), 4),
            "calculated_depletion_kg": total_dep,
            "classified_qty": classified_qty,
            "remaining_unclassified_qty": remaining_unclassified,
            "unexplained_depletion_kg": round(float(r["unexplained_depletion_kg"]), 4),
            "status": r["status"],
            "notes": r["notes"],
            "resolution_notes": r["resolution_notes"],
            "reconciliation_transaction_id": r["reconciliation_transaction_id"],
            "recorded_by": r["recorded_by"],
            "recorded_at": r["recorded_at"],
            "resolved_by": r["resolved_by"],
            "resolved_at": r["resolved_at"],
        }

        # Financial redaction
        if role == "owner":
            unit_cost = float(r["unit_cost_rs"])
            item["unit_cost_rs"] = unit_cost
            item["estimated_loss_rs"] = round(classified_qty * unit_cost, 2)
            item["total_depletion_cost_rs"] = round(total_dep * unit_cost, 2)
        else:
            item["unit_cost_rs"] = None
            item["estimated_loss_rs"] = None
            item["total_depletion_cost_rs"] = None

        results.append(item)

    return jsonify({"depletions": results, "count": len(results)})


@app.get("/api/manager/depletions/<depletion_id>")
@auth("manager", "owner")
def manager_depletion_details(depletion_id):
    """
    Detailed investigation view:
    Depletion header, opening count record, closing count record, delivery lines,
    notes history, and active/reversed classifications.
    Strictly redacts financial info for managers.
    """
    role = request.user["role"]

    dep_rows = db.query(
        """
        SELECT d.*, i.name as ingredient_name, i.unit, i.unit_cost_rs
        FROM depletion_logs d
        JOIN ingredients i USING (ingredient_id)
        WHERE d.depletion_id = ?
        """,
        (depletion_id,)
    )
    if not dep_rows:
        return jsonify(error="Depletion record not found"), 404

    dep = dep_rows[0]
    date = dep["date"]
    iid = dep["ingredient_id"]

    # 1. Opening count
    op_counts = db.query(
        "SELECT count_id, date, physical_qty, entered_by, verified_by, verified_at, status, notes, created_at "
        "FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='AM_OPENING'",
        (date, iid)
    )
    opening_count = op_counts[0] if op_counts else None

    # 2. Closing count
    cl_counts = db.query(
        "SELECT count_id, date, physical_qty, entered_by, verified_by, verified_at, status, notes, created_at "
        "FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='PM_CLOSING'",
        (date, iid)
    )
    closing_count = cl_counts[0] if cl_counts else None

    # 3. Deliveries
    deliveries_rows = db.query(
        """
        SELECT i.item_id, i.invoice_id, inv.invoice_no, inv.supplier_name,
               i.billed_qty, i.inventory_qty, i.unit, i.batch_no, i.expiry_date,
               i.created_at, i.unit_price_rs, i.line_total_rs
        FROM supplier_invoice_items i
        JOIN supplier_invoices inv USING (invoice_id)
        WHERE inv.invoice_date = ? AND i.ingredient_id = ?
        """,
        (date, iid)
    )
    deliveries = []
    for d_item in deliveries_rows:
        item_copy = dict(d_item)
        if role != "owner":
            item_copy["unit_price_rs"] = None
            item_copy["line_total_rs"] = None
        deliveries.append(item_copy)

    # 4. Classifications
    cls_rows = db.query(
        """
        SELECT classification_id, depletion_id, category, classified_qty, unit,
               reclassification_transaction_id, classified_by, classified_at,
               notes, status, reversal_id, reversal_reason, reversed_by, reversed_at,
               idempotency_key
        FROM depletion_classifications
        WHERE depletion_id = ?
        ORDER BY classified_at ASC
        """,
        (depletion_id,)
    )

    classifications = []
    active_classified_qty = 0.0
    for c in cls_rows:
        c_dict = dict(c)
        if c["status"] == "ACTIVE":
            active_classified_qty += float(c["classified_qty"])
        if role == "owner":
            c_dict["cost_rs"] = round(float(c["classified_qty"]) * float(dep["unit_cost_rs"]), 2)
        else:
            c_dict["cost_rs"] = None
        classifications.append(c_dict)

    active_classified_qty = round(active_classified_qty, 4)
    total_dep = round(float(dep["calculated_depletion_kg"]), 4)
    remaining_unclassified = max(0.0, round(total_dep - active_classified_qty, 4))

    # 5. Investigation notes
    notes_rows = db.query(
        "SELECT note_id, author, note, created_at FROM depletion_investigation_notes "
        "WHERE depletion_id = ? ORDER BY created_at ASC",
        (depletion_id,)
    )

    res = {
        "depletion_id": dep["depletion_id"],
        "date": dep["date"],
        "ingredient_id": dep["ingredient_id"],
        "ingredient_name": dep["ingredient_name"],
        "unit": dep["unit"],
        "opening_qty": round(float(dep["opening_qty"]), 4),
        "deliveries_qty": round(float(dep["deliveries_qty"]), 4),
        "closing_qty": round(float(dep["closing_qty"]), 4),
        "calculated_depletion_kg": total_dep,
        "classified_qty": active_classified_qty,
        "remaining_unclassified_qty": remaining_unclassified,
        "unexplained_depletion_kg": round(float(dep["unexplained_depletion_kg"]), 4),
        "status": dep["status"],
        "notes": dep["notes"],
        "resolution_notes": dep["resolution_notes"],
        "reconciliation_transaction_id": dep["reconciliation_transaction_id"],
        "recorded_by": dep["recorded_by"],
        "recorded_at": dep["recorded_at"],
        "resolved_by": dep["resolved_by"],
        "resolved_at": dep["resolved_at"],
        "opening_count": opening_count,
        "closing_count": closing_count,
        "deliveries": deliveries,
        "classifications": classifications,
        "investigation_notes": notes_rows,
    }

    if role == "owner":
        res["unit_cost_rs"] = float(dep["unit_cost_rs"])
        res["estimated_loss_rs"] = round(active_classified_qty * float(dep["unit_cost_rs"]), 2)
    else:
        res["unit_cost_rs"] = None
        res["estimated_loss_rs"] = None

    return jsonify(res)


@app.post("/api/manager/depletions/<depletion_id>/classify")
@auth("manager", "owner")
def manager_classify_depletion(depletion_id):
    """
    Zero-sum depletion classification.
    Posts a ledger movement with delta_qty = 0.0.
    Rejects over-classification, physical overages, missing counts, and invalid categories.
    Mandatory explanatory notes for THEFT and OTHER_UNEXPLAINED.
    """
    b = request.get_json(force=True, silent=True) or {}
    actor = request.user["username"]
    now_ts = iot.now_str()

    with db.tx() as con:
        # 1. Fetch depletion record
        dep_rows = con.execute(
            """
            SELECT d.*, i.unit, i.unit_cost_rs
            FROM depletion_logs d
            JOIN ingredients i USING (ingredient_id)
            WHERE d.depletion_id = ?
            """,
            (depletion_id,)
        ).fetchall()
        if not dep_rows:
            return jsonify(error="Depletion record not found"), 404

        dep = dict(dep_rows[0])
        date = dep["date"]
        iid = dep["ingredient_id"]

        # 2. Check for missing counts (Requirement 8 Test 12)
        has_opening = con.execute(
            "SELECT 1 FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='AM_OPENING'",
            (date, iid)
        ).fetchone()
        has_closing = con.execute(
            "SELECT 1 FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='PM_CLOSING'",
            (date, iid)
        ).fetchone()
        if not has_opening or not has_closing:
            return jsonify(error="Cannot finalize or classify depletion investigation with missing opening or closing count"), 422

        # 3. Check for physical overage or zero depletion (Requirement 8 Test 11)
        total_dep = round(float(dep["calculated_depletion_kg"]), 4)
        if total_dep <= 0:
            return jsonify(error="Physical overage or zero depletion cannot be classified as wastage"), 422

        # 4. Validate category
        category = (b.get("category") or "").upper().strip()
        if category not in VALID_CLASSIFICATION_CATEGORIES:
            return jsonify(error=f"Invalid classification category '{category}'. Must be one of {list(VALID_CLASSIFICATION_CATEGORIES)}"), 400

        # 5. Mandatory notes for THEFT and OTHER_UNEXPLAINED
        notes = (b.get("notes") or "").strip()
        if category in ("THEFT", "OTHER_UNEXPLAINED"):
            if not notes or len(notes) < 5:
                return jsonify(error=f"Additional explanatory notes (minimum 5 characters) are mandatory for category '{category}'"), 400

        # 6. Validate quantity
        try:
            classified_qty = round(float(b.get("classified_qty", 0)), 4)
        except (TypeError, ValueError):
            return jsonify(error="Invalid classified_qty"), 400

        if classified_qty <= 0:
            return jsonify(error="Classified quantity must be greater than zero"), 400

        # 7. Idempotency check (Requirement 8 Test 8)
        idemp_key = b.get("idempotency_key")
        if idemp_key:
            existing = con.execute(
                "SELECT * FROM depletion_classifications WHERE idempotency_key = ?",
                (idemp_key,)
            ).fetchone()
            if existing:
                return jsonify({
                    "status": "duplicate",
                    "classification": dict(existing),
                    "idempotent": True
                }), 200

        # 8. Concurrency & Over-classification protection (Requirement 8 Test 7 & 9)
        active_sum = con.execute(
            "SELECT COALESCE(SUM(classified_qty), 0.0) FROM depletion_classifications WHERE depletion_id = ? AND status = 'ACTIVE'",
            (depletion_id,)
        ).fetchone()[0]
        active_sum = round(float(active_sum), 4)

        remaining = max(0.0, round(total_dep - active_sum, 4))
        if round(classified_qty, 4) > round(remaining, 4) + 0.0001:
            return jsonify(
                error=f"Classified quantity ({classified_qty} kg) exceeds remaining unclassified quantity ({remaining} kg)"
            ), 422

        # 9. Mandatory Zero-Sum Ledger Movement (delta_qty = 0.0)
        cls_id = f"CLS_{uuid.uuid4().hex[:10]}"
        tx_idemp = f"TX_RECLASS_{cls_id}"
        reclass_tx = ledger.post_transaction(
            ingredient_id=iid,
            transaction_type="RECLASSIFICATION",
            quantity=classified_qty,
            delta_qty=0.0,  # MANDATORY ZERO-SUM
            unit=b.get("unit") or dep["unit"] or "kg",
            actor=actor,
            source_channel="DEPLETION_INVESTIGATION",
            reference_id=f"RECLASS:{depletion_id}:{category}",
            idempotency_key=tx_idemp,
            reversal_ref_id=dep.get("reconciliation_transaction_id"),
            notes=f"Zero-sum classification [{category}] by {actor}: {notes}",
            allow_negative=True,
            con=con
        )

        # 10. Insert into depletion_classifications
        con.execute(
            """
            INSERT INTO depletion_classifications (
                classification_id, depletion_id, category, classified_qty,
                unit, reclassification_transaction_id, classified_by, classified_at,
                notes, status, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (
                cls_id, depletion_id, category, classified_qty,
                b.get("unit") or dep["unit"] or "kg",
                reclass_tx.get("transaction_id"), actor, now_ts,
                notes, idemp_key
            )
        )

        # 11. Update depletion_logs
        new_active_sum = round(active_sum + classified_qty, 4)
        new_remaining = max(0.0, round(total_dep - new_active_sum, 4))
        new_status = "CLASSIFIED" if new_remaining <= 0.0001 else "INVESTIGATING"

        con.execute(
            "UPDATE depletion_logs SET unexplained_depletion_kg = ?, status = ? WHERE depletion_id = ?",
            (new_remaining, new_status, depletion_id)
        )

        # 12. Audit log
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "DEPLETION_CLASSIFIED", f"{cls_id} {depletion_id} {category} {classified_qty}kg remaining={new_remaining}kg")
        )

    res_body = {
        "classification_id": cls_id,
        "depletion_id": depletion_id,
        "category": category,
        "classified_qty": classified_qty,
        "remaining_unclassified_qty": new_remaining,
        "status": new_status,
        "reclassification_transaction_id": reclass_tx.get("transaction_id"),
        "delta_qty": 0.0,
        "classified_by": actor,
        "classified_at": now_ts,
    }
    return jsonify(res_body), 201


@app.post("/api/manager/depletions/<depletion_id>/notes")
@auth("manager", "owner")
def manager_add_depletion_note(depletion_id):
    """Add an investigation note to a depletion record."""
    b = request.get_json(force=True, silent=True) or {}
    note_text = (b.get("note") or "").strip()
    if not note_text:
        return jsonify(error="Note content cannot be empty"), 400

    actor = request.user["username"]
    now_ts = iot.now_str()

    with db.tx() as con:
        dep = con.execute("SELECT * FROM depletion_logs WHERE depletion_id=?", (depletion_id,)).fetchone()
        if not dep:
            return jsonify(error="Depletion record not found"), 404

        note_id = f"NOTE_{uuid.uuid4().hex[:8]}"
        con.execute(
            "INSERT INTO depletion_investigation_notes (note_id, depletion_id, author, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (note_id, depletion_id, actor, note_text, now_ts)
        )

        if dep["status"] == "UNCLASSIFIED":
            con.execute("UPDATE depletion_logs SET status='INVESTIGATING' WHERE depletion_id=?", (depletion_id,))

    return jsonify({
        "note_id": note_id,
        "depletion_id": depletion_id,
        "author": actor,
        "note": note_text,
        "created_at": now_ts
    }), 201


@app.post("/api/manager/depletions/<depletion_id>/resolve")
@auth("manager", "owner")
def manager_resolve_depletion(depletion_id):
    """
    Explicitly resolve an investigation.
    Allows closing an investigation with unexplained remaining depletion.
    Rejects if opening or closing counts are missing.
    """
    b = request.get_json(force=True, silent=True) or {}
    resolution_notes = (b.get("resolution_notes") or "").strip()
    actor = request.user["username"]
    now_ts = iot.now_str()

    with db.tx() as con:
        dep_rows = con.execute("SELECT * FROM depletion_logs WHERE depletion_id=?", (depletion_id,)).fetchall()
        if not dep_rows:
            return jsonify(error="Depletion record not found"), 404

        dep = dict(dep_rows[0])
        date = dep["date"]
        iid = dep["ingredient_id"]

        # Missing counts check (Requirement 8 Test 12)
        has_opening = con.execute(
            "SELECT 1 FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='AM_OPENING'",
            (date, iid)
        ).fetchone()
        has_closing = con.execute(
            "SELECT 1 FROM daily_stock_counts WHERE date=? AND ingredient_id=? AND count_type='PM_CLOSING'",
            (date, iid)
        ).fetchone()
        if not has_opening or not has_closing:
            return jsonify(error="Cannot finalize or resolve depletion investigation with missing opening or closing count"), 422

        # Check remaining unclassified qty
        active_sum = con.execute(
            "SELECT COALESCE(SUM(classified_qty), 0.0) FROM depletion_classifications WHERE depletion_id = ? AND status = 'ACTIVE'",
            (depletion_id,)
        ).fetchone()[0]
        remaining = max(0.0, round(float(dep["calculated_depletion_kg"]) - float(active_sum), 4))

        if remaining > 0 and not resolution_notes:
            return jsonify(error="Resolution notes are required when closing an investigation with unexplained remaining depletion"), 400

        target_status = "CLASSIFIED" if remaining <= 0.0001 else "RESOLVED"

        con.execute(
            """
            UPDATE depletion_logs
            SET status = ?, resolution_notes = ?, resolved_by = ?, resolved_at = ?, unexplained_depletion_kg = ?
            WHERE depletion_id = ?
            """,
            (target_status, resolution_notes, actor, now_ts, remaining, depletion_id)
        )

        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "DEPLETION_RESOLVED", f"{depletion_id} status={target_status} remaining={remaining}kg")
        )

    return jsonify({
        "depletion_id": depletion_id,
        "status": target_status,
        "remaining_unclassified_qty": remaining,
        "resolution_notes": resolution_notes,
        "resolved_by": actor,
        "resolved_at": now_ts
    }), 200


@app.post("/api/manager/depletions/classifications/<classification_id>/reverse")
@auth("manager", "owner")
def manager_reverse_classification(classification_id):
    """
    Controlled reversal of a classification event.
    Posts a zero-sum compensating transaction (delta_qty = 0.0) to preserve audit history.
    Restores the unclassified balance in depletion_logs.
    """
    b = request.get_json(force=True, silent=True) or {}
    reason = (b.get("reason") or "").strip()
    if not reason or len(reason) < 3:
        return jsonify(error="A clear reason (at least 3 characters) is required for classification reversal"), 400

    actor = request.user["username"]
    now_ts = iot.now_str()

    with db.tx() as con:
        cls_rows = con.execute(
            "SELECT * FROM depletion_classifications WHERE classification_id=?",
            (classification_id,)
        ).fetchall()
        if not cls_rows:
            return jsonify(error="Classification not found"), 404

        cls_rec = dict(cls_rows[0])
        if cls_rec["status"] == "REVERSED":
            return jsonify(error="Classification is already reversed"), 409

        dep_id = cls_rec["depletion_id"]
        dep = con.execute("SELECT * FROM depletion_logs WHERE depletion_id=?", (dep_id,)).fetchone()
        if not dep:
            return jsonify(error="Linked depletion record not found"), 404

        rev_id = f"REV_{uuid.uuid4().hex[:8]}"

        # Zero-sum compensating ledger posting
        reclass_rev_tx = ledger.post_transaction(
            ingredient_id=dep["ingredient_id"],
            transaction_type="RECLASSIFICATION",
            quantity=float(cls_rec["classified_qty"]),
            delta_qty=0.0,  # ZERO-SUM
            unit=cls_rec["unit"],
            actor=actor,
            source_channel="DEPLETION_INVESTIGATION",
            reference_id=f"REVERSE:{classification_id}",
            idempotency_key=f"TX_REVERSE_{rev_id}",
            reversal_ref_id=cls_rec.get("reclassification_transaction_id"),
            notes=f"Reversal of {classification_id} [{cls_rec['category']}]: {reason}",
            allow_negative=True,
            con=con
        )

        # Update classification record
        con.execute(
            """
            UPDATE depletion_classifications
            SET status = 'REVERSED', reversal_id = ?, reversal_reason = ?,
                reversed_by = ?, reversed_at = ?
            WHERE classification_id = ?
            """,
            (rev_id, reason, actor, now_ts, classification_id)
        )

        # Recalculate remaining unclassified qty
        active_sum = con.execute(
            "SELECT COALESCE(SUM(classified_qty), 0.0) FROM depletion_classifications WHERE depletion_id=? AND status='ACTIVE'",
            (dep_id,)
        ).fetchone()[0]
        active_sum = round(float(active_sum), 4)

        total_dep = round(float(dep["calculated_depletion_kg"]), 4)
        new_remaining = max(0.0, round(total_dep - active_sum, 4))
        new_status = "UNCLASSIFIED" if active_sum == 0 else ("CLASSIFIED" if new_remaining <= 0.0001 else "INVESTIGATING")

        con.execute(
            "UPDATE depletion_logs SET unexplained_depletion_kg=?, status=? WHERE depletion_id=?",
            (new_remaining, new_status, dep_id)
        )

        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
            (now_ts, actor, "CLASSIFICATION_REVERSED", f"{classification_id} rev_id={rev_id} reason={reason}")
        )

    return jsonify({
        "status": "REVERSED",
        "classification_id": classification_id,
        "reversal_id": rev_id,
        "reversal_reason": reason,
        "reversed_by": actor,
        "reversed_at": now_ts,
        "remaining_unclassified_qty": new_remaining,
        "depletion_status": new_status
    }), 200


@app.get("/api/manager/reports/depletions")
@auth("manager", "owner")
def manager_depletions_reports():
    """
    Operational investigation reports:
    - Wastage quantity by category
    - Wastage quantity by ingredient
    - Daily & weekly classified depletion
    - Unresolved depletion list
    - Investigation history
    Strictly redacts financial / rupee data for managers.
    """
    role = request.user["role"]
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    iid_param = request.args.get("ingredient_id")

    where_clauses = ["c.status = 'ACTIVE'"]
    args = []
    if start_date:
        where_clauses.append("d.date >= ?")
        args.append(start_date)
    if end_date:
        where_clauses.append("d.date <= ?")
        args.append(end_date)
    if iid_param:
        where_clauses.append("d.ingredient_id = ?")
        args.append(iid_param)

    where_sql = " AND ".join(where_clauses)

    # 1. Wastage quantity by category
    cat_rows = db.query(
        f"""
        SELECT c.category, ROUND(SUM(c.classified_qty), 4) as total_qty_kg, COUNT(*) as count
        FROM depletion_classifications c
        JOIN depletion_logs d USING (depletion_id)
        WHERE {where_sql}
        GROUP BY c.category
        ORDER BY total_qty_kg DESC
        """,
        args
    )
    total_classified = sum(r["total_qty_kg"] for r in cat_rows) or 1.0
    wastage_by_category = [
        {
            "category": r["category"],
            "total_qty_kg": r["total_qty_kg"],
            "count": r["count"],
            "percentage": round((r["total_qty_kg"] / total_classified) * 100.0, 1)
        }
        for r in cat_rows
    ]

    # 2. Wastage quantity by ingredient
    ing_rows = db.query(
        f"""
        SELECT d.ingredient_id, i.name as ingredient_name, i.unit,
               ROUND(SUM(c.classified_qty), 4) as total_qty,
               COUNT(*) as count,
               i.unit_cost_rs
        FROM depletion_classifications c
        JOIN depletion_logs d USING (depletion_id)
        JOIN ingredients i ON d.ingredient_id = i.ingredient_id
        WHERE {where_sql}
        GROUP BY d.ingredient_id, i.name, i.unit
        ORDER BY total_qty DESC
        """,
        args
    )
    wastage_by_ingredient = []
    for r in ing_rows:
        item = {
            "ingredient_id": r["ingredient_id"],
            "ingredient_name": r["ingredient_name"],
            "unit": r["unit"],
            "total_qty": r["total_qty"],
            "count": r["count"]
        }
        if role == "owner":
            item["total_loss_rs"] = round(r["total_qty"] * float(r["unit_cost_rs"]), 2)
        else:
            item["total_loss_rs"] = None
        wastage_by_ingredient.append(item)

    # 3. Daily & weekly classified depletion timeline
    timeline_rows = db.query(
        f"""
        SELECT d.date,
               ROUND(SUM(c.classified_qty), 4) as daily_classified_kg,
               COUNT(DISTINCT c.classification_id) as classifications_count
        FROM depletion_classifications c
        JOIN depletion_logs d USING (depletion_id)
        WHERE {where_sql}
        GROUP BY d.date
        ORDER BY d.date DESC
        """,
        args
    )

    # 4. Unresolved depletion list
    unresolved_rows = db.query(
        """
        SELECT d.depletion_id, d.date, d.ingredient_id, i.name as ingredient_name, i.unit,
               d.calculated_depletion_kg, d.unexplained_depletion_kg, d.status, d.notes,
               i.unit_cost_rs
        FROM depletion_logs d
        JOIN ingredients i USING (ingredient_id)
        WHERE d.unexplained_depletion_kg > 0 AND d.calculated_depletion_kg > 0
        ORDER BY d.date DESC, d.unexplained_depletion_kg DESC
        """
    )
    unresolved = []
    for r in unresolved_rows:
        u_item = {
            "depletion_id": r["depletion_id"],
            "date": r["date"],
            "ingredient_id": r["ingredient_id"],
            "ingredient_name": r["ingredient_name"],
            "unit": r["unit"],
            "calculated_depletion_kg": round(float(r["calculated_depletion_kg"]), 4),
            "unexplained_depletion_kg": round(float(r["unexplained_depletion_kg"]), 4),
            "status": r["status"],
            "notes": r["notes"]
        }
        if role == "owner":
            u_item["unexplained_loss_rs"] = round(float(r["unexplained_depletion_kg"]) * float(r["unit_cost_rs"]), 2)
        else:
            u_item["unexplained_loss_rs"] = None
        unresolved.append(u_item)

    # 5. Investigation history (both active and reversed)
    history_rows = db.query(
        """
        SELECT c.classification_id, c.depletion_id, d.date, d.ingredient_id, i.name as ingredient_name,
               c.category, c.classified_qty, c.unit, c.classified_by, c.classified_at,
               c.status, c.notes, c.reversal_reason, c.reversed_by, c.reversed_at
        FROM depletion_classifications c
        JOIN depletion_logs d USING (depletion_id)
        JOIN ingredients i ON d.ingredient_id = i.ingredient_id
        ORDER BY c.classified_at DESC
        LIMIT 100
        """
    )

    res = {
        "wastage_by_category": wastage_by_category,
        "wastage_by_ingredient": wastage_by_ingredient,
        "timeline": timeline_rows,
        "unresolved_depletions": unresolved,
        "investigation_history": history_rows,
    }

    if role == "owner":
        total_loss_rs = sum(r.get("total_loss_rs") or 0.0 for r in wastage_by_ingredient)
        res["total_loss_rs"] = round(total_loss_rs, 2)
    else:
        res["total_loss_rs"] = None

    return jsonify(res)


# ------------------------------------------------------------------ inventory journal endpoints
@app.get("/api/inventory/transactions")
@auth("owner", "manager")
def inventory_transactions():
    ing = request.args.get("ingredient_id")
    limit = int(request.args.get("limit", 100))
    sql = "SELECT * FROM inventory_transactions"
    args = []
    if ing:
        sql += " WHERE ingredient_id=?"
        args.append(ing)
    sql += " ORDER BY timestamp DESC, created_at DESC LIMIT ?"
    args.append(limit)
    return jsonify(db.query(sql, args))


@app.get("/api/inventory/reconciliation")
@auth("owner", "manager")
def inventory_reconciliation():
    ing = request.args.get("ingredient_id")
    return jsonify(ledger.reconcile_balances(ingredient_id=ing))


@app.post("/api/inventory/reconciliation/fix")
@auth("owner")
def inventory_reconciliation_fix():
    ing = (request.get_json(force=True, silent=True) or {}).get("ingredient_id")
    return jsonify(ledger.reconcile_balances(ingredient_id=ing, fix=True, actor=request.user["username"]))


# ------------------------------------------------------------------ IoT
@app.post("/api/iot/readings")
def iot_ingest():
    code, body = iot.ingest(request.get_json(force=True, silent=True) or {}, request.headers.get("X-Device-Key", ""))
    return jsonify(body), code


@app.get("/api/iot/devices")
@auth()
def iot_devices():
    out = []
    for d in db.query("SELECT d.*, i.name, i.unit FROM devices d JOIN ingredients i USING (ingredient_id)"):
        last = db.query("SELECT * FROM iot_readings WHERE device_id=? ORDER BY ts DESC, reading_id DESC LIMIT 1", (d["device_id"],))
        online = False
        if d["last_seen"]:
            online = (datetime.now() - datetime.strptime(d["last_seen"], "%Y-%m-%d %H:%M:%S")).total_seconds() < 30
        sess = db.query("SELECT session_id FROM refill_sessions WHERE device_id=? AND status='OPEN'", (d["device_id"],))
        out.append({"device_id": d["device_id"], "ingredient_id": d["ingredient_id"], "name": d["name"], "unit": d["unit"],
                    "last_seen": d["last_seen"], "online": online, "weight_kg": last[0]["weight_kg"] if last else None,
                    "stable": last[0]["stable"] if last else None, "capacity_kg": 15,
                    "open_session": sess[0]["session_id"] if sess else None})
    return jsonify(out)


@app.get("/api/iot/readings")
@auth()
def iot_readings():
    dev = request.args["device_id"]; limit = int(request.args.get("limit", 200))
    live = db.query("SELECT ts, weight_kg, stable, event_type, session_id FROM iot_readings WHERE device_id=? AND source='live' "
                    "ORDER BY ts DESC, reading_id DESC LIMIT ?", (dev, limit))
    if len(live) >= 5:
        return jsonify(mode="live", readings=list(reversed(live)))
    day = db.query("SELECT MAX(substr(ts,1,10)) d FROM iot_readings WHERE device_id=? AND source='history'", (dev,))[0]["d"]
    hist = db.query("SELECT ts, weight_kg, stable, event_type, session_id FROM iot_readings WHERE device_id=? AND "
                    "source='history' AND substr(ts,1,10)=? ORDER BY ts, reading_id", (dev, day))
    return jsonify(mode="history", day=day, readings=hist)


@app.get("/api/iot/daily")
@auth()
def iot_daily():
    df = ml.iot_daily_usage()
    return jsonify(df.to_dict("records"))


@app.get("/api/iot/simulator")
@auth()
def sim_status():
    return jsonify(simulator.status())


@app.post("/api/iot/simulator/<action>")
@auth("owner", "manager")
def sim_action(action):
    b = request.get_json(force=True, silent=True) or {}
    if action == "start": return jsonify(simulator.start(b.get("interval", 2.0)))
    if action == "stop": return jsonify(simulator.stop())
    if action == "spill": return jsonify(simulator.inject_spill(b.get("device_id")))
    return jsonify(error="unknown action"), 404


# ------------------------------------------------------------------ barcode refill sessions
@app.post("/api/refill/open")
@auth()
def refill_open():
    b = request.get_json(force=True)
    code, body = iot.open_session(b.get("barcode", ""), request.user["username"], b.get("batch_no"), b.get("expiry_date"))
    return jsonify(body), code


@app.post("/api/refill/<sid>/complete")
@auth()
def refill_complete(sid):
    code, body = iot.complete_session(sid, request.user["username"])
    return jsonify(body), code


@app.post("/api/refill/<sid>/cancel")
@auth()
def refill_cancel(sid):
    code, body = iot.cancel_session(sid, request.user["username"])
    return jsonify(body), code


@app.get("/api/refill/sessions")
@auth()
def refill_sessions():
    return jsonify(db.query("SELECT r.*, i.name FROM refill_sessions r JOIN ingredients i USING (ingredient_id) "
                            "ORDER BY started_at DESC LIMIT ?", (int(request.args.get("limit", 25)),)))


# ------------------------------------------------------------------ reports (CSV)
def _csv(rows, name):
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}_{datetime.now():%Y%m%d}.csv"})


@app.get("/api/reports/<name>.csv")
@auth("owner", "manager")
def report(name):
    role = request.user["role"]
    res = ml.get_results()["results"]
    if name == "stock_summary":
        rows = [{"ingredient": r["name"], "unit": r["unit"], "stock": r["stock"], "stock_date": r["stock_date"],
                 "days_of_cover": r["days_of_cover"], "reorder_point": r["reorder_point"]} for r in res.values()]
    elif name == "forecast_reorder":
        rows = [{"ingredient": r["name"], "unit": r["unit"], "model": r["model"], "date": f["date"], "forecast": f["qty"],
                 "low": f["low"], "high": f["high"], "order_qty_today": r["order_qty"]} for r in res.values() for f in r["forecast"]]
    elif name == "model_evaluation":
        rows = [{"ingredient": r["name"], "model": m, **v, "selected": m == r["model"]} for r in res.values()
                for m, v in r["validation"].items()]
    elif name == "wastage":
        if role == "manager":
            rows = db.query("SELECT m.date, i.name ingredient, i.unit, m.wastage_qty, m.wastage_reason "
                            "FROM manual_entries m JOIN ingredients i USING (ingredient_id) "
                            "WHERE m.wastage_qty>0 ORDER BY m.date DESC")
        else:
            rows = db.query("SELECT m.date, i.name ingredient, i.unit, m.wastage_qty, m.wastage_reason, "
                            "ROUND(m.wastage_qty*i.unit_cost_rs,0) value_rs FROM manual_entries m JOIN ingredients i "
                            "USING (ingredient_id) WHERE m.wastage_qty>0 ORDER BY m.date DESC")
    elif name == "sales":
        sales_data = get_sales_metrics()
        if not sales_data or sales_data.get("status") == "DATA_UNAVAILABLE":
            return jsonify(error="DATA_UNAVAILABLE", message="Actual sales data is unavailable"), 404
        rows = sales_data["daily"]
    elif name == "manual_register":
        rows = db.query("SELECT m.date, i.name ingredient, i.unit, m.opening_stock, m.received_qty, m.batch_no, m.expiry_date,"
                        " m.used_qty, m.wastage_qty, m.wastage_reason, m.closing_stock, m.days_covered, m.entered_by,"
                        " m.entry_status FROM manual_entries m JOIN ingredients i USING (ingredient_id) ORDER BY m.date DESC")
    elif name == "iot_daily_usage":
        rows = ml.iot_daily_usage().to_dict("records")
    elif name == "refill_sessions":
        rows = db.query("SELECT * FROM refill_sessions ORDER BY started_at DESC")
    else:
        return jsonify(error="unknown report"), 404
    return _csv(rows, name)


# ------------------------------------------------------------------ built frontend (optional single-port demo)
@app.get("/")
@app.get("/<path:path>")
def spa(path="index.html"):
    if not os.path.isdir(DIST):
        return jsonify(message="SmartStock AI API is running. Start the frontend with `npm run dev` in /frontend."), 200
    full = os.path.join(DIST, path)
    return send_from_directory(DIST, path if os.path.isfile(full) else "index.html")


if __name__ == "__main__":
    if not os.path.exists(db.DB_PATH):
        import seed_db
        seed_db.seed()
    db.init_schema()
    print("Training forecasting models (first start takes ~10-20 s)...")
    ml.get_results()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
