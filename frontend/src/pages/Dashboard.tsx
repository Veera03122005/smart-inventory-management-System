import { useState } from "react";
import { Link } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt, rupees, shortDate } from "../api";
import { Badge, ErrorNote, Loading, Page, Stat, useData } from "../ui";

export default function Dashboard() {
  const { data, error } = useData(() => api("/dashboard"), 15000);
  const fc = useData(() => api("/forecast"), 60000);
  const [sel, setSel] = useState("ING01");
  if (error) return <Page title="Dashboard"><ErrorNote msg={error} /></Page>;
  if (!data) return <Loading />;
  const c = data.cards;
  const r = fc.data?.results.find((x: any) => x.ingredient_id === sel);
  const series = r ? [
    ...r.history.slice(-30).map((h: any) => ({ date: h.date, actual: h.usage })),
    ...r.forecast.map((f: any) => ({ date: f.date, forecast: f.qty, band: [f.low, f.high] })),
  ] : [];
  return (
    <Page title="Kitchen overview" sub={`Plan for ${new Date(data.target_date + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })} · models updated ${data.run_at?.replace("T", " ")}`}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Stock value" value={rupees(c.stock_value_rs)} hint={`${c.ingredients} key ingredients`} />
        <Stat label="To order today" value={rupees(c.order_value_rs)} hint={`${c.low_stock} item(s) below reorder point`} tone={c.low_stock ? "warn" : undefined} />
        <Stat label="Open alerts" value={c.open_alerts} hint={`${c.expiry_risk} expiry risk`} tone={c.open_alerts ? "bad" : "good"} />
        <Stat label="Wastage, last 7 days" value={rupees(c.wastage_7d_rs)} hint={`${fmt((100 * c.wastage_7d_rs) / Math.max(1, c.usage_7d_rs), 2)}% of usage value`} />
      </div>
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card lg:col-span-2 overflow-x-auto">
          <div className="px-4 py-3 font-semibold">Today's plan</div>
          <table className="w-full">
            <thead><tr><th className="th">Ingredient</th><th className="th text-right">In stock</th><th className="th">Days of cover</th><th className="th text-right">Prepare (AI)</th><th className="th text-right">Order now</th><th className="th">Status</th></tr></thead>
            <tbody>
              {data.rows.map((x: any) => (
                <tr key={x.ingredient_id} onClick={() => setSel(x.ingredient_id)} className={`cursor-pointer hover:bg-leaf-light/50 ${sel === x.ingredient_id ? "bg-leaf-light" : ""}`}>
                  <td className="td font-medium">{x.name}</td>
                  <td className="td text-right num">{fmt(x.stock)} {x.unit}</td>
                  <td className="td">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 rounded bg-black/10 overflow-hidden"><div className={`h-full ${x.days_of_cover < 1 ? "bg-red-500" : x.days_of_cover < 2 ? "bg-spice" : "bg-leaf"}`} style={{ width: `${Math.min(100, (x.days_of_cover / 7) * 100)}%` }} /></div>
                      <span className="num text-xs text-ink-mute">{fmt(x.days_of_cover)} d</span>
                    </div>
                  </td>
                  <td className="td text-right num font-semibold">{fmt(x.prep_qty)} {x.unit}</td>
                  <td className="td text-right num">{x.order_qty > 0 ? <span className="text-spice font-semibold">{fmt(x.order_qty)} {x.unit}</span> : "–"}</td>
                  <td className="td"><Badge tone={x.status === "OK" ? "ok" : x.status === "Low stock" ? "high" : "medium"}>{x.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="px-4 py-3 font-semibold flex justify-between">Needs attention <Link to="/alerts" className="text-xs text-leaf font-normal underline">All alerts</Link></div>
          <div className="divide-y divide-black/5">
            {data.alerts.length === 0 && <div className="p-4 text-sm text-ink-mute">Nothing needs attention.</div>}
            {data.alerts.map((a: any) => (
              <div key={a.key} className="px-4 py-3">
                <div className="flex items-start gap-2"><Badge tone={a.severity}>{a.severity}</Badge><div className="text-sm font-medium">{a.title}</div></div>
                <div className="text-xs text-ink-mute mt-1">{a.action}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {r && (
        <div className="card mt-6 p-4">
          <div className="flex items-baseline justify-between mb-2">
            <div className="font-semibold">{r.name}: last 30 days and 7-day forecast</div>
            <div className="text-xs text-ink-mute">Model: {r.model} · validation WAPE {r.validation[r.model].WAPE}%</div>
          </div>
          <div className="h-64">
            <ResponsiveContainer>
              <ComposedChart data={series} margin={{ left: 0, right: 10, top: 5 }}>
                <CartesianGrid stroke="#e4e3df" vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} minTickGap={24} />
                <YAxis tick={{ fontSize: 11 }} width={40} unit={` ${r.unit}`} />
                <Tooltip labelFormatter={(l) => shortDate(String(l))} formatter={(v: any) => (Array.isArray(v) ? `${v[0]} – ${v[1]}` : v)} />
                <Area dataKey="band" name="Forecast range" stroke="none" fill="#eb6834" fillOpacity={0.15} />
                <Line dataKey="actual" name="Actual usage" stroke="#16211c" strokeWidth={2} dot={false} />
                <Line dataKey="forecast" name="Forecast" stroke="#eb6834" strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Page>
  );
}
