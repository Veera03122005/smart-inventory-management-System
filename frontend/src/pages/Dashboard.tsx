import { useState, useId } from "react";
import { Link } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt, rupees, shortDate } from "../api";
import { useAuth, isStaff, isManager, isOwner } from "../auth";
import { Badge, ErrorNote, Page, Stat, SkeletonCard, SkeletonTable, useData } from "../ui";

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading } = useData(() => api("/dashboard"), 15000);
  const fc = useData(() => api("/forecast"), 60000);
  const [sel, setSel] = useState("ING01");

  if (error) {
    return (
      <Page title="Kitchen Overview">
        <ErrorNote msg={error} />
      </Page>
    );
  }

  if (loading || !data || !data.cards) {
    return (
      <Page title="Kitchen Overview" sub="Loading live kitchen inventory intelligence…">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <SkeletonTable rows={6} cols={6} />
          </div>
          <div>
            <SkeletonCard />
          </div>
        </div>
      </Page>
    );
  }

  const c = data.cards;
  const r = (fc.data?.results || []).find((x: any) => x.ingredient_id === sel);
  const series = r && Array.isArray(r.history) && Array.isArray(r.forecast)
    ? [
        ...r.history.slice(-30).map((h: any) => ({ date: h.date, actual: h.usage })),
        ...r.forecast.map((f: any) => ({ date: f.date, forecast: f.qty, band: [f.low, f.high] })),
      ]
    : [];

  const formattedDate = new Date(data.target_date + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <Page
      title="Kitchen Overview"
      sub={`Daily operational plan for ${formattedDate} · Models updated ${data.run_at?.replace("T", " ")}`}
      actions={
        <div className="flex items-center gap-2">
          <Link to="/stock-sheet" className="btn-ghost btn-sm">
            <svg className="w-4 h-4 mr-1 text-content-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Stock Sheet
          </Link>
          <Link to="/refill" className="btn-primary btn-sm">
            <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4" />
            </svg>
            Barcode Refill
          </Link>
        </div>
      }
    >
      {/* ----------------- KPI Cards Grid ----------------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {isStaff(user) ? (
          <>
            <Stat
              label="Tracked Pantry Items"
              value={c.ingredients}
              hint="Active kitchen inventory items"
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              }
            />
            <Stat
              label="Items to Reorder"
              value={c.low_stock}
              hint={c.low_stock > 0 ? "Stock is below safety threshold" : "All items sufficiently stocked"}
              tone={c.low_stock > 0 ? "warn" : "good"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              }
            />
            <Stat
              label="Open Kitchen Alerts"
              value={c.open_alerts}
              hint={`${c.expiry_risk} batch(es) at risk of expiry`}
              tone={c.open_alerts > 0 ? "bad" : "good"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              }
            />
            <Stat
              label="Batches Expiring Soon"
              value={c.expiry_risk}
              hint={c.expiry_risk > 0 ? "Prioritize using these batches first" : "No batches at immediate risk"}
              tone={c.expiry_risk > 0 ? "warn" : "good"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
            />
          </>
        ) : isManager(user) ? (
          <>
            <Stat
              label="Today's Food Sales"
              value={c.sales_today_rs != null ? rupees(c.sales_today_rs) : "Data Unavailable"}
              hint={c.sales_today_rs != null ? "Daily restaurant food orders" : "Sales integration not configured"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
            />
            <Stat
              label="7-Day Food Sales"
              value={c.sales_7d_rs != null ? rupees(c.sales_7d_rs) : "Data Unavailable"}
              hint={c.sales_7d_rs != null ? "Weekly gross restaurant volume" : "Sales integration not configured"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              }
            />
            <Stat
              label="Open Alerts"
              value={c.open_alerts}
              hint={`${c.expiry_risk} batch(es) at risk of expiry`}
              tone={c.open_alerts > 0 ? "bad" : "good"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              }
            />
            <Stat
              label="Items to Reorder"
              value={c.low_stock}
              hint={`${c.low_stock} item(s) below reorder safety`}
              tone={c.low_stock > 0 ? "warn" : undefined}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              }
            />
          </>
        ) : (
          <>
            <Stat
              label="Total Stock Value"
              value={rupees(c.stock_value_rs)}
              hint={`${c.ingredients} tracked pantry items`}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              }
            />
            <Stat
              label="To Order Today"
              value={rupees(c.order_value_rs)}
              hint={`${c.low_stock} item(s) below reorder safety`}
              tone={c.low_stock > 0 ? "warn" : undefined}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              }
            />
            <Stat
              label="Open Alerts"
              value={c.open_alerts}
              hint={`${c.expiry_risk} batch(es) at risk of expiry`}
              tone={c.open_alerts > 0 ? "bad" : "good"}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              }
            />
            <Stat
              label="Wastage (Last 7 Days)"
              value={rupees(c.wastage_7d_rs)}
              hint={`${fmt((100 * c.wastage_7d_rs) / Math.max(1, c.usage_7d_rs), 2)}% of total usage value`}
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              }
            />
          </>
        )}
      </div>

      {/* ----------------- Main Content Grid ----------------- */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Today's Plan Table */}
        <div className="card lg:col-span-2 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Today's Kitchen Plan</h2>
              <p className="text-xs text-content-muted mt-0.5">Click any ingredient row to view its AI demand forecast chart</p>
            </div>
            <span className="text-xs text-content-muted num">{data.rows.length} items</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Ingredient</th>
                  <th className="th text-right" scope="col">In Stock</th>
                  <th className="th" scope="col">Days of Cover</th>
                  <th className="th text-right" scope="col">Prepare (AI)</th>
                  <th className="th text-right" scope="col">Order Today</th>
                  <th className="th text-center" scope="col">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.rows.map((x: any) => {
                  const isSelected = sel === x.ingredient_id;
                  const coverRatio = Math.min(100, (x.days_of_cover / 7) * 100);
                  const progressColor =
                    x.days_of_cover < 1
                      ? "bg-rose-500"
                      : x.days_of_cover < 2
                      ? "bg-amber-500"
                      : "bg-emerald-500";

                  return (
                    <tr
                      key={x.ingredient_id}
                      onClick={() => setSel(x.ingredient_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSel(x.ingredient_id);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-pressed={isSelected}
                      aria-label={`Select ${x.name} to view forecast`}
                      className={`cursor-pointer transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                        isSelected
                          ? "bg-brand-50/80 font-medium"
                          : "hover:bg-slate-50/80"
                      }`}
                    >
                      <td className="td font-medium text-content-primary">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${isSelected ? "bg-brand-600" : "bg-transparent"}`} />
                          {x.name}
                        </div>
                      </td>
                      <td className="td text-right num text-content-primary">
                        {fmt(x.stock)} <span className="text-xs text-content-muted">{x.unit}</span>
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-2.5">
                          <div
                            className="h-2 w-20 rounded-full bg-slate-200/80 overflow-hidden"
                            role="progressbar"
                            aria-valuenow={Math.round(x.days_of_cover * 10) / 10}
                            aria-valuemin={0}
                            aria-valuemax={7}
                            aria-label={`${x.name} days of stock cover`}
                          >
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${progressColor}`}
                              style={{ width: `${coverRatio}%` }}
                            />
                          </div>
                          <span className="num text-xs font-semibold text-content-secondary min-w-[2.5rem]">
                            {fmt(x.days_of_cover)} d
                          </span>
                        </div>
                      </td>
                      <td className="td text-right num font-bold text-content-primary">
                        {fmt(x.prep_qty)} <span className="text-xs font-normal text-content-muted">{x.unit}</span>
                      </td>
                      <td className="td text-right num">
                        {x.order_qty > 0 ? (
                          <span className="text-amber-700 font-bold bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                            {fmt(x.order_qty)} {x.unit}
                          </span>
                        ) : (
                          <span className="text-content-subtle">–</span>
                        )}
                      </td>
                      <td className="td text-center">
                        <Badge
                          tone={x.status === "OK" ? "ok" : x.status === "Low stock" ? "high" : "medium"}
                          withDot={true}
                        >
                          {x.status}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Needs Attention Panel */}
        <div className="card overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <h2 className="text-base font-bold text-content-primary flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
              Needs Attention
            </h2>
            <Link
              to="/alerts"
              className="text-xs font-semibold text-brand-700 hover:text-brand-800 hover:underline flex items-center gap-1"
            >
              All Alerts
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

          <div className="divide-y divide-slate-100 overflow-y-auto max-h-[380px] p-2 space-y-1">
            {data.alerts.length === 0 ? (
              <div className="p-8 text-center flex flex-col items-center justify-center">
                <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-2">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div className="text-sm font-semibold text-content-primary">All systems normal</div>
                <div className="text-xs text-content-muted mt-0.5">No critical kitchen alerts require attention.</div>
              </div>
            ) : (
              data.alerts.map((a: any) => (
                <div key={a.key} className="p-3.5 rounded-lg hover:bg-slate-50 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-semibold text-content-primary">{a.title}</span>
                    <Badge tone={a.severity}>{a.severity}</Badge>
                  </div>
                  <div className="text-xs text-content-muted mt-1 leading-normal">{a.action}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ----------------- Selected Ingredient 30-Day Forecast Chart ----------------- */}
      {r && (
        <div className="card mt-6 p-5">
          <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 mb-4 pb-3 border-b border-surface-border">
            <div>
              <h3 className="text-base font-bold text-content-primary">
                {r.name} Demand Analysis
              </h3>
              <p className="text-xs text-content-muted mt-0.5">
                Past 30 days historical usage plotted alongside 7-day recursive ML forecast
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="px-2.5 py-1 rounded-md bg-surface-muted text-content-secondary font-medium">
                Active Model: <strong className="text-content-primary">{r.model}</strong>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 font-semibold border border-emerald-200">
                WAPE: {r.validation[r.model].WAPE}%
              </span>
            </div>
          </div>

          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
                <CartesianGrid stroke="#f1f5f9" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={shortDate}
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  minTickGap={28}
                  axisLine={{ stroke: "#e2e8f0" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  width={48}
                  unit={` ${r.unit}`}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={(l) => shortDate(String(l))}
                  formatter={(v: any, name: string) => [
                    Array.isArray(v) ? `${fmt(v[0])} – ${fmt(v[1])} ${r.unit}` : `${fmt(v)} ${r.unit}`,
                    name,
                  ]}
                  contentStyle={{
                    backgroundColor: "rgba(255, 255, 255, 0.95)",
                    backdropFilter: "blur(4px)",
                    borderRadius: "0.75rem",
                    border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                    fontSize: "0.8125rem",
                  }}
                />
                <Area
                  dataKey="band"
                  name="Confidence Range"
                  stroke="none"
                  fill="#f59e0b"
                  fillOpacity={0.18}
                />
                <Line
                  dataKey="actual"
                  name="Actual Consumption"
                  stroke="#0f172a"
                  strokeWidth={2.25}
                  dot={false}
                  activeDot={{ r: 5, fill: "#0f172a" }}
                />
                <Line
                  dataKey="forecast"
                  name="AI Forecast"
                  stroke="#d97706"
                  strokeWidth={2.25}
                  strokeDasharray="4 4"
                  dot={{ r: 3.5, fill: "#d97706" }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Page>
  );
}
