"""
SmartStock AI - Baseline Metrics Generator for Research Paper Snapshot.
Trains models on shipped data and records per-ingredient WAPE, MAE, RMSE across all models,
along with data quality counts. Output is saved to docs/baseline_metrics.md.
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

import db
import seed_db
import ml


def generate_baseline_metrics():
    # Ensure database is present from shipped seed data
    if not os.path.exists(db.DB_PATH):
        print(f"Database not found at {db.DB_PATH}. Seeding from shipped CSVs...")
        seed_db.DATA = os.path.join(BACKEND_DIR, "data")
        seed_db.seed(fresh=True)

    print("Training models on shipped dataset...")
    train_cache = ml.train_all()
    results = train_cache.get("results", {})
    run_at = train_cache.get("run_at", datetime.now().isoformat(timespec="seconds"))
    seconds = train_cache.get("seconds", 0.0)

    lines = []
    lines.append("# SmartStock AI — Baseline Model Metrics Snapshot")
    lines.append("")
    lines.append("> **Research Paper Baseline**: Pre-intervention performance snapshot evaluated on the shipped 60-day validation window.")
    lines.append("")
    lines.append(f"- **Generated At**: {run_at}")
    lines.append(f"- **Training Duration**: {seconds} seconds")
    lines.append(f"- **Validation Horizon**: {ml.VAL_DAYS} days (time-based split)")
    lines.append(f"- **Forecast Horizon**: {ml.HORIZON} days")
    lines.append(f"- **Cycle Service Level**: 98% (Z = {ml.Z})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table across all ingredients
    lines.append("## Cross-Ingredient Champion Model Overview")
    lines.append("")
    lines.append("| Ingredient ID | Ingredient Name | Unit | Champion Model | Champion WAPE (%) | Champion MAE | Champion RMSE | Lead Time | Shelf Life |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    models_order = ["Seasonal naive", "Moving avg (7d)", "Random Forest", "XGBoost"]

    for iid, r in sorted(results.items()):
        best_m = r["model"]
        m_stats = r["validation"].get(best_m, {})
        # Query lead time and shelf life from DB
        ing_meta = db.query("SELECT lead_time_days, shelf_life_days FROM ingredients WHERE ingredient_id=?", (iid,))
        lead = ing_meta[0]["lead_time_days"] if ing_meta else "-"
        shelf = ing_meta[0]["shelf_life_days"] if ing_meta else "-"
        wape = m_stats.get("WAPE", "-")
        mae = m_stats.get("MAE", "-")
        rmse = m_stats.get("RMSE", "-")
        lines.append(f"| `{iid}` | **{r['name']}** | {r['unit']} | `{best_m}` | **{wape}%** | {mae} | {rmse} | {lead}d | {shelf}d |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-Ingredient Model Evaluation & Data Quality")
    lines.append("")

    for iid, r in sorted(results.items()):
        name = r["name"]
        unit = r["unit"]
        best_m = r["model"]
        sigma = r["sigma"]
        dq = r.get("data_quality", {})
        total_days = sum(dq.values()) if dq else 0

        lines.append(f"### {iid} — {name} ({unit})")
        lines.append("")
        lines.append(f"- **Selected Champion Model**: `{best_m}` (Residual Std Dev $\\sigma = {sigma}$ {unit})")
        lines.append(f"- **Current Closing Stock**: {r.get('stock', 0)} {unit} (as of {r.get('stock_date', 'N/A')})")
        lines.append(f"- **Days of Cover**: {r.get('days_of_cover', 'N/A')} days")
        lines.append(f"- **Reorder Point ($s$)**: {r.get('reorder_point', 'N/A')} {unit} | **Order-up-to ($S$)**: {r.get('order_up_to', 'N/A')} {unit}")
        lines.append("")

        # Data Quality Breakdown
        lines.append("#### Data Quality & Channel Provenance")
        lines.append("")
        lines.append("| Channel / Data Quality Category | Total Days | Proportion (%) |")
        lines.append("| :--- | :--- | :--- |")
        for cat in ["entered", "reconstructed", "iot", "missing"]:
            if cat in dq:
                count = dq[cat]
                pct = round(100.0 * count / total_days, 1) if total_days > 0 else 0
                lines.append(f"| `{cat}` | {count} | {pct}% |")
        lines.append(f"| **Total Observed Series Length** | **{total_days}** | **100.0%** |")
        lines.append("")

        # Model comparison table
        lines.append("#### 60-Day Validation Window Performance")
        lines.append("")
        lines.append("| Model | WAPE (%) | MAE | RMSE | Champion? |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for m in models_order:
            if m in r["validation"]:
                stats = r["validation"][m]
                is_champ = "✓ Selected" if m == best_m else ""
                lines.append(f"| {m} | {stats['WAPE']}% | {stats['MAE']} | {stats['RMSE']} | {is_champ} |")

        lines.append("")
        lines.append("---")
        lines.append("")

    docs_dir = os.path.join(REPO_ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    out_file = os.path.join(docs_dir, "baseline_metrics.md")
    content = "\n".join(lines) + "\n"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Baseline metrics snapshot written successfully to: {out_file}")
    return out_file


if __name__ == "__main__":
    generate_baseline_metrics()
