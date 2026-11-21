import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt, shortDate } from "../api";
import { Badge, ErrorNote, Loading, Page, Stat, useData } from "../ui";

const MODELS = ["Seasonal naive", "Moving avg (7d)", "Random Forest", "XGBoost"];

export default function Forecast() {
  const { data, error, reload } = useData(() => api("/forecast"));
  const [sel, setSel] = useState("ING01");
  const [busy, setBusy] = useState(false);

  if (error) {
    return (
      <Page title="AI Demand Forecast & Replenishment">
        <ErrorNote msg={error} />
      </Page>
    );
  }

  if (!data) return <Loading label="Loading ML models & validation series…" />;

  const r = (data?.results || []).find((x: any) => x.ingredient_id === sel);

  const retrain = async () => {
    setBusy(true);
    try {
      await api("/forecast/retrain", { method: "POST" });
      await reload();
    } finally {
      setBusy(false);
    }
  };

  const chart = [
    ...r.validation_series.map((v: any) => ({
      date: v.date,
      actual: v.actual,
      model: v[r.model],
      naive: v["Seasonal naive"],
    })),
    ...r.forecast.map((f: any) => ({
      date: f.date,
      forecast: f.qty,
      band: [f.low, f.high],
    })),
  ];

  const q = r.data_quality;

  return (
    <Page
      title="AI Demand Forecast & Replenishment"
      sub={`Random Forest and XGBoost benchmarked against baselines across a 60-day test window. Last fitted ${data.run_at?.replace(
        "T",
        " "
      )} in ${data.seconds}s.`}
      actions={
        <button
          className="btn-primary"
          onClick={retrain}
          disabled={busy}
          aria-label="Retrain machine learning models"
        >
          {busy ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Training Models…
            </>
          ) : (
            <>
              <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Retrain Models
            </>
          )}
        </button>
      }
    >
      {/* ----------------- Ingredient Selector Tabs ----------------- */}
      <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label="Ingredient tabs">
        {data.results.map((x: any) => {
          const isSelected = sel === x.ingredient_id;
          return (
            <button
              key={x.ingredient_id}
              role="tab"
              aria-selected={isSelected}
              onClick={() => setSel(x.ingredient_id)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                isSelected
                  ? "bg-brand-600 text-white shadow-sm"
                  : "bg-white text-content-secondary hover:bg-slate-50 border border-surface-border"
              }`}
            >
              {x.name}
            </button>
          );
        })}
      </div>

      {/* ----------------- Metric KPI Cards ----------------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <Stat
          label={`Prepare (${shortDate(r.target_date)})`}
          value={`${fmt(r.prep_qty)} ${r.unit}`}
          hint={`Range: ${fmt(r.forecast[0].low)}–${fmt(r.forecast[0].high)} ${r.unit}`}
          tone="good"
        />
        <Stat
          label="Champion Model"
          value={<span className="text-xl font-bold">{r.model}</span>}
          hint={`WAPE ${r.validation[r.model].WAPE}% · MAE ${r.validation[r.model].MAE} ${r.unit}`}
          tone="info"
        />
        <Stat
          label="Current Stock"
          value={`${fmt(r.stock)} ${r.unit}`}
          hint={`${fmt(r.days_of_cover)} days of stock cover`}
        />
        <Stat
          label="Reorder Point (s)"
          value={`${fmt(r.reorder_point)} ${r.unit}`}
          hint={`Target capacity (S): ${fmt(r.order_up_to)} ${r.unit}`}
        />
        <Stat
          label="Order Recommendation"
          value={r.order_qty > 0 ? `${fmt(r.order_qty)} ${r.unit}` : "No Order"}
          tone={r.order_qty > 0 ? "warn" : undefined}
          hint={r.perishable ? "Daily perishables policy" : "Weekly replenishment cycle"}
        />
      </div>

      {/* ----------------- Validation & Forecast Composed Chart ----------------- */}
      <div className="card p-5 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between pb-3 mb-4 border-b border-surface-border">
          <div>
            <h2 className="text-base font-bold text-content-primary">
              {r.name}: 60-Day Validation Backtest & 7-Day Forward Horizon
            </h2>
            <p className="text-xs text-content-muted mt-0.5">
              Evaluating predicted demand vs true consumption with upper/lower forecast confidence intervals
            </p>
          </div>
          <div className="text-xs text-content-muted">
            Data Quality: {q.entered || 0} entered, {q.reconstructed || 0} reconstructed gaps, {q.iot || 0} IoT sensor days
          </div>
        </div>

        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chart} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid stroke="#f1f5f9" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#64748b" }} minTickGap={28} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} width={48} unit={` ${r.unit}`} axisLine={false} tickLine={false} />
              <Tooltip
                labelFormatter={(l) => shortDate(String(l))}
                formatter={(v: any, name: string) => [
                  Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])} ${r.unit}` : `${fmt(v)} ${r.unit}`,
                  name,
                ]}
                contentStyle={{
                  backgroundColor: "rgba(255, 255, 255, 0.95)",
                  borderRadius: "0.75rem",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                  fontSize: "0.8125rem",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
              <Area dataKey="band" name="Forecast Range (±Z·σ)" stroke="none" fill="#f59e0b" fillOpacity={0.16} />
              <Line dataKey="actual" name="Actual Usage" stroke="#0f172a" strokeWidth={2.2} dot={false} />
              <Line dataKey="model" name={`${r.model} (1-day ahead)`} stroke="#0284c7" strokeWidth={1.8} dot={false} />
              <Line dataKey="naive" name="Seasonal Naive Baseline" stroke="#94a3b8" strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
              <Line dataKey="forecast" name="Forecast Target" stroke="#d97706" strokeWidth={2.2} strokeDasharray="4 4" dot={{ r: 3.5, fill: "#d97706" }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ----------------- Model Comparison & Batches Expiry ----------------- */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Model Evaluation Table */}
        <div className="card overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <h3 className="text-base font-bold text-content-primary">Model Comparison: Validation WAPE (%)</h3>
            <span className="text-xs text-content-muted font-medium">Lower is better</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Ingredient</th>
                  {MODELS.map((m) => (
                    <th key={m} className="th text-right" scope="col">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((x: any) => (
                  <tr key={x.ingredient_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="td font-medium text-content-primary">{x.name}</td>
                    {MODELS.map((m) => {
                      const isChampion = x.model === m;
                      return (
                        <td key={m} className={`td text-right num ${isChampion ? "font-bold text-emerald-700 bg-emerald-50/50" : "text-content-secondary"}`}>
                          {x.validation[m].WAPE}%
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-3 bg-surface-muted/30 border-t border-surface-border text-xs text-content-muted">
            Highlighted green column represents the auto-selected lowest-error algorithm for that ingredient.
          </div>
        </div>

        {/* Expiry Risk Batches Table */}
        <div className="card overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <h3 className="text-base font-bold text-content-primary">{r.name}: Open Batches & Expiry Risk</h3>
            <span className="text-xs text-content-muted num">{r.batches.length} active batch(es)</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Batch Number</th>
                  <th className="th text-right" scope="col">Remaining</th>
                  <th className="th" scope="col">Expiry Date</th>
                  <th className="th text-right" scope="col">At-Risk Qty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {r.batches.length === 0 ? (
                  <tr>
                    <td className="td text-center text-content-muted py-6" colSpan={4}>
                      No open batches in inventory.
                    </td>
                  </tr>
                ) : (
                  r.batches.map((b: any) => (
                    <tr key={b.batch_no} className="hover:bg-slate-50/80 transition-colors">
                      <td className="td text-xs font-mono font-medium text-content-primary">{b.batch_no}</td>
                      <td className="td text-right num font-semibold">
                        {fmt(b.qty_remaining)} <span className="text-xs font-normal text-content-muted">{r.unit}</span>
                      </td>
                      <td className="td text-xs text-content-secondary">
                        {b.expiry_date} <span className="text-content-subtle font-mono">({b.days_to_expiry}d left)</span>
                      </td>
                      <td className="td text-right">
                        {b.at_risk_qty > 0.5 ? (
                          <Badge tone="danger" withDot={true}>
                            {fmt(b.at_risk_qty)} {r.unit}
                          </Badge>
                        ) : (
                          <span className="text-xs text-emerald-700 font-medium">Safe</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Page>
  );
}
