"""
SmartStock AI - experiments behind the research paper.

For each random seed the script generates the two datasets, loads them into a temporary database and
runs the SAME ml.py used by the application. Everything is scored against the simulated true demand.

  E1  Forecast accuracy on the last 60 days: seasonal naive, 7-day moving average, Random Forest, XGBoost
  E2  Data handling: (a) manual gaps reconstructed vs. booked as zero
                     (b) hybrid series (sensor days replace register days) vs. register only
                     (c) sensor daily usage with vs. without barcode refill sessions
  E3  Replenishment over the same 60 days: habit par-level policy vs. forecast-driven policy

Usage:  python run_experiments.py            (about 6-8 minutes; results in ./results)
"""
import os, sys, tempfile, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
import db, seed_db, ml, generate_data as gd          # noqa: E402

END, TEST_DAYS, SEEDS = "2026-11-15", 60, [42, 7, 123, 2024, 99]
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
ING = {x[0]: dict(name=x[1], unit=x[2], shelf=x[6], lead=x[7], cost=x[8], iot=x[10]) for x in gd.INGREDIENTS}


def build(seed, workdir):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-08-01", END, freq="D")
    demand = gd.gen_demand(rng, dates)
    reg = gd.gen_manual_register(rng, demand)
    iot, sess = gd.gen_iot(rng, demand, END, 30)
    ing = pd.DataFrame([dict(ingredient_id=x[0], name=x[1], unit=x[2], shelf_life_days=x[6], lead_time_days=x[7],
                             unit_cost_rs=x[8], barcode=x[9], iot_enabled=int(x[10]),
                             device_id={"ING03": "ESP32-RICE-01", "ING04": "ESP32-OIL-01", "ING05": "ESP32-ONION-01"}.get(x[0], ""),
                             min_stock=round(x[3] * 0.6, 1)) for x in gd.INGREDIENTS])
    for name, df in [("true_daily_demand", demand), ("manual_stock_register", reg), ("iot_readings", iot),
                     ("refill_sessions", sess), ("ingredients", ing)]:
        df.to_csv(os.path.join(workdir, name + ".csv"), index=False)
    seed_db.DATA = workdir
    db.DB_PATH = os.path.join(workdir, "exp.db")
    seed_db.seed(fresh=True)
    return demand, reg, iot


def naive_manual_series(iid):
    rows = pd.DataFrame(db.query("SELECT date, used_qty, entry_status FROM manual_entries WHERE ingredient_id=? ORDER BY date", (iid,)))
    return pd.Series(np.where(rows.entry_status == "ENTERED", rows.used_qty.fillna(0), 0.0), index=rows.date)


def manual_only_series(iid):
    m = ml.manual_daily_usage(iid).set_index("date").usage
    idx = pd.date_range(m.index.min(), m.index.max(), freq="D").strftime("%Y-%m-%d")
    return m.reindex(idx)


def eval_series(s, truth, seed, iid, channel):
    """Train on everything before the test window, one-day-ahead forecasts in the window, score vs truth."""
    X = ml.features(s); y = s.values
    test = np.zeros(len(s), bool); test[-TEST_DAYS:] = True
    ok = X[ml.FEATS].notna().all(axis=1).values & ~np.isnan(y)
    yt = truth.reindex(s.index).values[test]
    v = s.interpolate(limit_direction="both")
    preds = {"Seasonal naive": v.shift(7).values[test], "Moving avg (7d)": v.shift(1).rolling(7).mean().values[test]}
    for name in ("Random Forest", "XGBoost"):
        preds[name] = ml.make_model(name, seed).fit(X.loc[ok & ~test, ml.FEATS], y[ok & ~test]).predict(X.loc[test, ml.FEATS])
    rows = [dict(seed=seed, ingredient=ING[iid]["name"], channel=channel, model=k, **ml.metrics(yt, p)) for k, p in preds.items()]
    return rows, preds, list(s.index[test]), yt


def iot_measurement(iot, truth_df, seed):
    """Daily usage from the sensor log: with refill sessions (eq. 1) vs. net weight change only."""
    rows = []
    with_s = ml.iot_daily_usage()
    for iid, g in iot.groupby("ingredient_id"):
        t = truth_df[truth_df.ingredient_id == iid].set_index("date").true_usage
        g = g[(g.stable == 1) | (g.event_type != "READING")].copy(); g["date"] = g.timestamp.str[:10]
        net = g.groupby("date").weight_kg.agg(lambda w: max(0.0, w.iloc[0] - w.iloc[-1]))
        ws = with_s[with_s.ingredient_id == iid].set_index("date").usage
        d = ws.index.intersection(t.index)
        for label, est in (("With refill session", ws), ("Without refill session", net)):
            rows.append(dict(seed=seed, ingredient=ING[iid]["name"], method=label,
                             WAPE=float(100 * np.abs(est.reindex(d) - t.reindex(d)).sum() / t.reindex(d).sum())))
    return rows


def simulate(iid, truth, s_obs, seed):
    """Fixed habit par level vs. forecast-driven (s, S) over the test window, FIFO with expiry."""
    p = ING[iid]; L, shelf = p["lead"], p["shelf"]; perish = shelf <= 5
    dates = list(s_obs.index); n = len(dates); t0 = n - TEST_DAYS
    d_true = truth.reindex(s_obs.index).values
    mean90 = np.nanmean(s_obs.values[t0 - 90:t0])
    par = mean90 * (1.4 * L if perish else 1.25 * (L + 4))
    # model selection and sigma on the 60 days before the test window
    X = ml.features(s_obs); y = s_obs.values
    ok = X[ml.FEATS].notna().all(axis=1).values & ~np.isnan(y)
    idx = np.arange(n); pre = ok & (idx < t0 - 60); val = (idx >= t0 - 60) & (idx < t0)
    best, best_w, sigma = None, 1e9, 0.0
    for name in ("Random Forest", "XGBoost"):
        pv = ml.make_model(name, seed).fit(X.loc[pre, ml.FEATS], y[pre]).predict(X.loc[val, ml.FEATS])
        w = ml.metrics(np.nan_to_num(y[val], nan=np.nanmean(y[val])), pv)["WAPE"]
        if w < best_w:
            best, best_w, sigma = name, w, float(np.nanstd(y[val] - pv))
    model = ml.make_model(best, seed).fit(X.loc[ok & (idx < t0), ml.FEATS], y[ok & (idx < t0)])
    out = []
    for policy in ("Fixed par level", "Forecast-driven"):
        batches, pipeline = [[par if policy == "Fixed par level" else mean90 * (L + 1), shelf]], {}
        served = unmet = expired = 0.0; so = 0; onhand = []
        for i in range(t0, n):
            if i in pipeline: batches.append([pipeline.pop(i), shelf])
            need = d_true[i]
            for b in batches:
                take = min(b[0], need); b[0] -= take; need -= take
                if need <= 1e-9: break
            served += d_true[i] - need; unmet += need; so += need > 0.01 * d_true[i]
            for b in batches: b[1] -= 1
            expired += sum(b[0] for b in batches if b[1] <= 0)
            batches = [b for b in batches if b[1] > 0 and b[0] > 1e-9]
            stock = sum(b[0] for b in batches); onhand.append(stock); on_order = sum(pipeline.values())
            if policy == "Fixed par level":
                q = max(0.0, par - stock - on_order)
            else:
                H = L if perish else L + 7
                fc = [v for _, v in ml.recursive_forecast(model, s_obs.iloc[:i + 1], H)]
                s_pt = sum(fc[:L]) + ml.Z * sigma * np.sqrt(L)
                S_pt = sum(fc) + ml.Z * sigma * np.sqrt(H)
                q = max(0.0, S_pt - stock - on_order) if (perish or stock + on_order < s_pt) else 0.0
            if q > 0: pipeline[i + L] = pipeline.get(i + L, 0.0) + q
        tot = d_true[t0:].sum()
        out.append(dict(seed=seed, ingredient=p["name"], policy=policy, model=best, fill_rate=100 * served / tot,
                        stockout_days=int(so), avg_cover_days=float(np.mean(onhand) / d_true[t0:].mean()),
                        expired_qty=expired, expired_rs=expired * p["cost"]))
    return out


def main():
    acc, meas, sims, keep = [], [], [], None
    for seed in SEEDS:
        with tempfile.TemporaryDirectory() as wd:
            demand, reg, iot = build(seed, wd)
            for iid in ING:
                truth = demand[demand.ingredient_id == iid].set_index("date").true_usage
                hybrid = ml.daily_series(iid).usage
                r, preds, dts, yt = eval_series(hybrid, truth, seed, iid, "Hybrid (register + sensor)")
                acc += r
                if seed == 42 and iid == "ING01":
                    keep = dict(dates=dts, actual=[float(x) for x in yt], **{k: [float(x) for x in v] for k, v in preds.items()})
                acc += eval_series(manual_only_series(iid), truth, seed, iid, "Register, reconstructed")[0]
                acc += eval_series(naive_manual_series(iid), truth, seed, iid, "Register, naive")[0]
                sims += simulate(iid, truth, hybrid, seed)
            meas += iot_measurement(iot, demand, seed)
            print("seed", seed, "done", flush=True)
    pd.DataFrame(acc).to_csv(os.path.join(OUT, "forecast_accuracy.csv"), index=False)
    pd.DataFrame(meas).to_csv(os.path.join(OUT, "sensor_measurement.csv"), index=False)
    pd.DataFrame(sims).to_csv(os.path.join(OUT, "replenishment.csv"), index=False)
    json.dump(keep, open(os.path.join(OUT, "chicken_seed42.json"), "w"))


if __name__ == "__main__":
    main()
