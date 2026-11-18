"""
SmartStock AI - machine-learning layer.

1. Builds one clean daily-usage series per ingredient from BOTH channels:
   - IoT: sum of stable weight drops, excluding barcode refill sessions
   - Manual register: skipped days reconstructed with a learned weekday profile
2. Trains Random Forest and XGBoost per ingredient and compares them with
   seasonal-naive and 7-day moving-average baselines (time-based validation).
3. Forecasts the next 7 days, sizes safety stock, computes reorder point / order quantity,
   flags expiry risk and usage anomalies.
"""
import json, os, threading, time
from datetime import datetime, timedelta
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
import db
from calendar_tn import is_purattasi, festival_name

VAL_DAYS = 60
HORIZON = 7
Z = 2.05                  # 98 % cycle service level
FEATS = ["dow", "weekend", "month", "purattasi", "festival", "lag1", "lag2", "lag7", "lag14",
         "rm7", "rm28", "rsd7", "same_dow_mean4"]
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_cache.json")
_lock = threading.Lock()
_cache = {"run_at": None, "results": {}}


# ---------------------------------------------------------------- data preparation
def iot_daily_usage(ingredient_id=None, include_live=False):
    """Daily usage from load-cell readings: stable drops only, refill windows excluded."""
    sql = "SELECT device_id, ingredient_id, ts, weight_kg, stable, event_type FROM iot_readings"
    cond, args = [], []
    if ingredient_id:
        cond.append("ingredient_id=?"); args.append(ingredient_id)
    if not include_live:
        cond.append("source='history'")
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    df = pd.DataFrame(db.query(sql + " ORDER BY device_id, ts", args))
    if df.empty:
        return pd.DataFrame(columns=["date", "ingredient_id", "usage", "refills", "readings"])
    out = []
    for (dev, ing), g in df.groupby(["device_id", "ingredient_id"]):
        g = g.copy(); g["date"] = g.ts.str[:10]
        last, cur_date, used, refills, n = None, None, 0.0, 0, 0
        for r in g.itertuples():
            if r.date != cur_date:
                if cur_date is not None:
                    out.append((cur_date, ing, round(used, 3), refills, n))
                cur_date, used, refills, n = r.date, 0.0, 0, 0
            if r.event_type == "REFILL_START":
                if last is not None and r.weight_kg < last:
                    used += last - r.weight_kg
                last = None; refills += 1
                continue
            if r.event_type == "REFILL_END":
                last = r.weight_kg
                continue
            if not r.stable:
                continue
            n += 1
            if last is not None and r.weight_kg < last:
                used += last - r.weight_kg
            last = r.weight_kg
        out.append((cur_date, ing, round(used, 3), refills, n))
    return pd.DataFrame(out, columns=["date", "ingredient_id", "usage", "refills", "readings"])


def manual_daily_usage(ingredient_id):
    rows = db.query("SELECT date, used_qty, days_covered, entry_status FROM manual_entries "
                    "WHERE ingredient_id=? ORDER BY date", (ingredient_id,))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["dow"] = pd.to_datetime(df.date).dt.dayofweek
    one = df[(df.entry_status == "ENTERED") & (df.days_covered == 1)]
    prof = one.groupby("dow").used_qty.mean().reindex(range(7)).fillna(one.used_qty.mean())
    usage, quality = [None] * len(df), [None] * len(df)
    i = 0
    while i < len(df):
        if df.entry_status.iloc[i] == "ENTERED":
            k = int(df.days_covered.iloc[i] or 1)
            idx = list(range(max(0, i - k + 1), i + 1))
            w = np.array([prof[df.dow.iloc[j]] for j in idx]); w = w / w.sum()
            for j, wj in zip(idx, w):
                usage[j] = float(df.used_qty.iloc[i]) * wj
                quality[j] = "entered" if k == 1 else "reconstructed"
        i += 1
    df["usage"] = usage; df["quality"] = quality
    return df[["date", "usage", "quality"]].dropna(subset=["usage"])


def daily_series(ingredient_id):
    """Merged daily series: IoT where a full sensor day exists, else manual register."""
    m = manual_daily_usage(ingredient_id).set_index("date")
    s = m.usage.copy(); q = m.quality.copy()
    iot = iot_daily_usage(ingredient_id)
    if not iot.empty:
        full = iot[iot.readings >= 150]                 # >= ~80 % of the day's 5-min readings
        for r in full.itertuples():
            s.loc[r.date] = r.usage; q.loc[r.date] = "iot"
    s = s.sort_index(); q = q.reindex(s.index)
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D").strftime("%Y-%m-%d")
    s = s.reindex(idx); q = q.reindex(idx).fillna("missing")
    return pd.DataFrame({"usage": s, "quality": q})


def calendar_frame(dates):
    d = pd.to_datetime(pd.Index(dates))
    ds = d.strftime("%Y-%m-%d")
    return pd.DataFrame({"dow": d.dayofweek, "weekend": (d.dayofweek >= 5).astype(int), "month": d.month,
                         "purattasi": [is_purattasi(x) for x in ds],
                         "festival": [int(festival_name(x) is not None) for x in ds]}, index=ds)


def features(series):
    f = calendar_frame(series.index)
    v = series.interpolate(limit_direction="both")
    for l in (1, 2, 7, 14):
        f[f"lag{l}"] = v.shift(l).values
    f["rm7"] = v.shift(1).rolling(7).mean().values
    f["rm28"] = v.shift(1).rolling(28).mean().values
    f["rsd7"] = v.shift(1).rolling(7).std().values
    f["same_dow_mean4"] = ((v.shift(7) + v.shift(14) + v.shift(21) + v.shift(28)) / 4).values
    return f


def make_model(name, seed=42):
    if name == "Random Forest":
        return RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=2, random_state=seed, n_jobs=-1)
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8,
                        colsample_bytree=0.8, random_state=seed, n_jobs=4)


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = p - y
    return {"MAE": round(float(np.mean(np.abs(e))), 3), "RMSE": round(float(np.sqrt(np.mean(e ** 2))), 3),
            "WAPE": round(float(100 * np.sum(np.abs(e)) / np.sum(y)), 2)}


def recursive_forecast(model, series, h):
    s = series.copy()
    out = []
    for _ in range(h):
        nxt = (pd.Timestamp(s.index[-1]) + timedelta(days=1)).strftime("%Y-%m-%d")
        s.loc[nxt] = np.nan
        X = features(s).iloc[[-1]][FEATS]
        p = max(0.0, float(model.predict(X)[0]))
        s.loc[nxt] = p
        out.append((nxt, p))
    return out


# ---------------------------------------------------------------- stock, batches, expiry
def current_stock(ingredient_id):
    r = db.query("SELECT date, closing_stock FROM manual_entries WHERE ingredient_id=? AND entry_status='ENTERED' "
                 "AND closing_stock IS NOT NULL ORDER BY date DESC LIMIT 1", (ingredient_id,))
    return (r[0]["closing_stock"], r[0]["date"]) if r else (0.0, None)


def open_batches(ingredient_id, stock):
    """Allocate remaining stock to the newest receipts (FIFO issue means old batches are used first)."""
    rec = db.query("SELECT date, batch_no, received_qty, expiry_date FROM manual_entries WHERE ingredient_id=? "
                   "AND received_qty > 0 AND batch_no IS NOT NULL ORDER BY date DESC", (ingredient_id,))
    left, out = stock, []
    for r in rec:
        if left <= 1e-6:
            break
        q = min(left, r["received_qty"])
        out.append({"batch_no": r["batch_no"], "received": r["date"], "qty_remaining": round(q, 2),
                    "expiry_date": r["expiry_date"]})
        left -= q
    return list(reversed(out))


def expiry_risk(batches, forecast, today):
    """Quantity in each batch expected to expire before it is used (FIFO, forecast usage)."""
    risk = []
    cum_use = 0.0
    fc = dict(forecast)
    for b in batches:
        days_left = (pd.Timestamp(b["expiry_date"]) - pd.Timestamp(today)).days + 1
        usable = sum(v for d, v in fc.items() if (pd.Timestamp(d) - pd.Timestamp(today)).days < days_left)
        if days_left > len(fc):
            usable += np.mean(list(fc.values())) * (days_left - len(fc))
        avail_for_batch = max(0.0, usable - cum_use)
        at_risk = max(0.0, b["qty_remaining"] - avail_for_batch)
        cum_use += b["qty_remaining"]
        risk.append({**b, "days_to_expiry": int(days_left), "at_risk_qty": round(at_risk, 2)})
    return risk


# ---------------------------------------------------------------- training
def train_ingredient(ing):
    iid = ing["ingredient_id"]
    ds = daily_series(iid)
    s = ds.usage
    X = features(s)
    y = s.values
    n = len(s)
    val = np.zeros(n, bool); val[-VAL_DAYS:] = True
    ok = X[FEATS].notna().all(axis=1).values & ~np.isnan(y)
    tr = ok & ~val
    yv = y[val]; dates_v = list(s.index[val])
    v = s.interpolate(limit_direction="both")
    preds = {"Seasonal naive": v.shift(7).values[val], "Moving avg (7d)": v.shift(1).rolling(7).mean().values[val]}
    models = {}
    for name in ("Random Forest", "XGBoost"):
        m = make_model(name).fit(X.loc[tr, FEATS], y[tr])
        preds[name] = m.predict(X.loc[val, FEATS])
        models[name] = m
    evals = {k: metrics(yv, p) for k, p in preds.items()}
    best = min(evals, key=lambda k: evals[k]["WAPE"])
    sigma = float(np.std(yv - preds[best]))
    # anomalies in the validation window
    resid = yv - preds[best]
    anomalies = [{"date": d, "actual": round(float(a), 2), "expected": round(float(p), 2),
                  "z": round(float(r / sigma), 2)} for d, a, p, r in zip(dates_v, yv, preds[best], resid)
                 if sigma > 0 and abs(r) > 3 * sigma]
    # refit on all data and forecast
    if best in ("Random Forest", "XGBoost"):
        final = make_model(best).fit(X.loc[ok, FEATS], y[ok])
        fc = recursive_forecast(final, s, HORIZON)
    elif best == "Seasonal naive":
        fc = [((pd.Timestamp(s.index[-1]) + timedelta(days=k + 1)).strftime("%Y-%m-%d"), float(v.iloc[-7 + k % 7]))
              for k in range(HORIZON)]
    else:
        m7 = float(v.iloc[-7:].mean())
        fc = [((pd.Timestamp(s.index[-1]) + timedelta(days=k + 1)).strftime("%Y-%m-%d"), m7) for k in range(HORIZON)]
    stock, stock_date = current_stock(iid)
    L = int(ing["lead_time_days"]); perish = ing["shelf_life_days"] <= 5
    H = L if perish else L + 7
    s_pt = sum(p for _, p in fc[:L]) + Z * sigma * np.sqrt(L)
    S_pt = sum(p for _, p in fc[:H]) + Z * sigma * np.sqrt(H) if H <= HORIZON else \
        sum(p for _, p in fc) * H / HORIZON + Z * sigma * np.sqrt(H)
    order_qty = max(0.0, S_pt - stock) if (perish or stock < s_pt) else 0.0
    avg_fc = np.mean([p for _, p in fc])
    batches = open_batches(iid, stock)
    risk = expiry_risk(batches, fc, fc[0][0])
    return {
        "ingredient_id": iid, "name": ing["name"], "unit": ing["unit"],
        "model": best, "validation": evals, "sigma": round(sigma, 3),
        "history": [{"date": d, "usage": None if np.isnan(u) else round(float(u), 2), "quality": q}
                    for d, u, q in zip(s.index[-90:], s.values[-90:], ds.quality.values[-90:])],
        "validation_series": [{"date": d, "actual": round(float(a), 2),
                               **{k: round(float(p[i]), 2) for k, p in preds.items()}}
                              for i, (d, a) in enumerate(zip(dates_v, yv))],
        "forecast": [{"date": d, "qty": round(p, 2), "low": round(max(0, p - Z * sigma), 2),
                      "high": round(p + Z * sigma, 2)} for d, p in fc],
        "target_date": fc[0][0], "prep_qty": round(fc[0][1], 2),
        "stock": stock, "stock_date": stock_date, "days_of_cover": round(stock / avg_fc, 2) if avg_fc else None,
        "reorder_point": round(s_pt, 2), "order_up_to": round(S_pt, 2), "order_qty": round(order_qty, 2),
        "perishable": bool(perish), "batches": risk, "anomalies": anomalies,
        "data_quality": ds.quality.value_counts().to_dict(),
    }


def train_all():
    with _lock:
        t0 = time.time()
        ings = db.query("SELECT * FROM ingredients ORDER BY ingredient_id")
        res = {i["ingredient_id"]: train_ingredient(i) for i in ings}
        _cache["results"] = res
        _cache["run_at"] = datetime.now().isoformat(timespec="seconds")
        _cache["seconds"] = round(time.time() - t0, 1)
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
        return _cache


def get_results():
    if not _cache["results"]:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                _cache.update(json.load(f))
        else:
            train_all()
    return _cache


def invalidate():
    """Called after new manual entries: recompute stock-dependent figures by retraining."""
    threading.Thread(target=train_all, daemon=True).start()
