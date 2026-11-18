import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt, shortDate } from "../api";
import { Badge, ErrorNote, Loading, Page, Stat, useData } from "../ui";

const MODELS = ["Seasonal naive", "Moving avg (7d)", "Random Forest", "XGBoost"];

export default function Forecast() {
  const { data, error, reload } = useData(() => api("/forecast"));
  const [sel, setSel] = useState("ING01");
  const [busy, setBusy] = useState(false);
  if (error) return <Page title="AI forecast"><ErrorNote msg={error} /></Page>;
  if (!data) return <Loading />;
  const r = data.results.find((x: any) => x.ingredient_id === sel);
  const retrain = async () => { setBusy(true); try { await api("/forecast/retrain", { method: "POST" }); await reload(); } finally { setBusy(false); } };
  const chart = [
    ...r.validation_series.map((v: any) => ({ date: v.date, actual: v.actual, model: v[r.model], naive: v["Seasonal naive"] })),
    ...r.forecast.map((f: any) => ({ date: f.date, forecast: f.qty, band: [f.low, f.high] })),
  ];
  const q = r.data_quality;
  return (
    <Page title="AI forecast and reorder" sub={`Random Forest and XGBoost against two simple baselines, validated on the last 60 days. Last trained ${data.run_at?.replace("T", " ")} (${data.seconds}s).`}
      actions={<button className="btn-primary" onClick={retrain} disabled={busy}>{busy ? "Training…" : "Retrain models"}</button>}>
      <div className="flex flex-wrap gap-2 mb-5">
        {data.results.map((x: any) => (
          <button key={x.ingredient_id} onClick={() => setSel(x.ingredient_id)} className={sel === x.ingredient_id ? "btn-primary" : "btn-ghost"}>{x.name}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <Stat label={`Prepare on ${shortDate(r.target_date)}`} value={`${fmt(r.prep_qty)} ${r.unit}`} hint={`Range ${fmt(r.forecast[0].low)}–${fmt(r.forecast[0].high)}`} tone="good" />
        <Stat label="Selected model" value={<span className="text-lg">{r.model}</span>} hint={`WAPE ${r.validation[r.model].WAPE}% · MAE ${r.validation[r.model].MAE} ${r.unit}`} />
        <Stat label="In stock" value={`${fmt(r.stock)} ${r.unit}`} hint={`${fmt(r.days_of_cover)} days of cover`} />
        <Stat label="Reorder point" value={`${fmt(r.reorder_point)} ${r.unit}`} hint={`Order up to ${fmt(r.order_up_to)}`} />
        <Stat label="Order now" value={r.order_qty > 0 ? `${fmt(r.order_qty)} ${r.unit}` : "No order"} tone={r.order_qty > 0 ? "warn" : undefined} hint={r.perishable ? "Perishable: ordered daily" : "Dry goods: weekly cycle"} />
      </div>
      <div className="card p-4 mb-6">
        <div className="font-semibold mb-2">{r.name}: validation (last 60 days) and next 7 days</div>
        <div className="h-72">
          <ResponsiveContainer>
            <ComposedChart data={chart} margin={{ left: 0, right: 10, top: 5 }}>
              <CartesianGrid stroke="#e4e3df" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} minTickGap={28} />
              <YAxis tick={{ fontSize: 11 }} width={44} unit={` ${r.unit}`} />
              <Tooltip labelFormatter={(l) => shortDate(String(l))} formatter={(v: any) => (Array.isArray(v) ? `${v[0]} – ${v[1]}` : v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area dataKey="band" name="Forecast range" stroke="none" fill="#eb6834" fillOpacity={0.15} />
              <Line dataKey="actual" name="Actual usage" stroke="#16211c" strokeWidth={2} dot={false} />
              <Line dataKey="model" name={`${r.model} (1 day ahead)`} stroke="#2a78d6" strokeWidth={1.8} dot={false} />
              <Line dataKey="naive" name="Seasonal naive" stroke="#1baf7a" strokeWidth={1.2} strokeDasharray="4 3" dot={false} />
              <Line dataKey="forecast" name="Forecast" stroke="#eb6834" strokeWidth={2} dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="text-xs text-ink-mute mt-2">Training data: {q.entered || 0} entered days, {q.reconstructed || 0} reconstructed from skipped entries, {q.iot || 0} sensor-measured days.</div>
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card overflow-x-auto">
          <div className="px-4 py-3 font-semibold">Model comparison: validation WAPE (%)</div>
          <table className="w-full">
            <thead><tr><th className="th">Ingredient</th>{MODELS.map((m) => <th key={m} className="th text-right">{m}</th>)}</tr></thead>
            <tbody>
              {data.results.map((x: any) => (
                <tr key={x.ingredient_id}><td className="td font-medium">{x.name}</td>
                  {MODELS.map((m) => <td key={m} className={`td text-right num ${x.model === m ? "font-semibold text-leaf" : ""}`}>{x.validation[m].WAPE}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-xs text-ink-mute">Lower is better. The model in green is the one used for that ingredient.</div>
        </div>
        <div className="card overflow-x-auto">
          <div className="px-4 py-3 font-semibold">{r.name}: open batches and expiry risk</div>
          <table className="w-full">
            <thead><tr><th className="th">Batch</th><th className="th text-right">Remaining</th><th className="th">Expires</th><th className="th text-right">May expire unused</th></tr></thead>
            <tbody>
              {r.batches.length === 0 && <tr><td className="td text-ink-mute" colSpan={4}>No stock on hand.</td></tr>}
              {r.batches.map((b: any) => (
                <tr key={b.batch_no}><td className="td text-xs">{b.batch_no}</td><td className="td text-right num">{fmt(b.qty_remaining)} {r.unit}</td>
                  <td className="td text-xs">{b.expiry_date} <span className="text-ink-mute">({b.days_to_expiry} d)</span></td>
                  <td className="td text-right">{b.at_risk_qty > 0.5 ? <Badge tone="high">{fmt(b.at_risk_qty)} {r.unit}</Badge> : <span className="text-ink-mute">–</span>}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Page>
  );
}
