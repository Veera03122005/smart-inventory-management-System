import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Loading, Page, useData } from "../ui";

const LABEL: Record<string, string> = { LOW_STOCK: "Low stock", EXPIRY_RISK: "Expiry risk", USAGE_ANOMALY: "Unusual usage", SUDDEN_DROP: "Sudden weight drop", MISSED_ENTRY: "Missed entry", REFILL_NEEDED: "Refill needed" };

export default function Alerts() {
  const { user } = useAuth();
  const { data, reload } = useData(() => api("/alerts"), 10000);
  const [type, setType] = useState("ALL");
  if (!data) return <Loading />;
  const types = Array.from(new Set(data.map((a: any) => a.type))) as string[];
  const rows = data.filter((a: any) => type === "ALL" || a.type === type);
  const ack = (key: string) => api("/alerts/ack", { body: { key } }).then(reload);
  return (
    <Page title="Alerts" sub="Rule-based checks (stock, expiry, missed entries) and AI checks (unusual usage against the forecast).">
      <div className="flex flex-wrap gap-2 mb-4">
        <button className={type === "ALL" ? "btn-primary" : "btn-ghost"} onClick={() => setType("ALL")}>All ({data.length})</button>
        {types.map((t) => <button key={t} className={type === t ? "btn-primary" : "btn-ghost"} onClick={() => setType(t)}>{LABEL[t] || t} ({data.filter((a: any) => a.type === t).length})</button>)}
      </div>
      <div className="space-y-3">
        {rows.map((a: any) => (
          <div key={a.key} className={`card p-4 flex flex-wrap items-start justify-between gap-3 ${a.acknowledged ? "opacity-60" : ""}`}>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap"><Badge tone={a.severity}>{a.severity}</Badge><Badge>{LABEL[a.type] || a.type}</Badge><span className="font-medium">{a.title}</span></div>
              <div className="text-sm text-ink-mute mt-1">{a.detail}</div>
              <div className="text-sm mt-1"><span className="text-ink-mute">Suggested action:</span> {a.action}</div>
            </div>
            {a.acknowledged ? <span className="text-xs text-ink-mute">Acknowledged by {a.acked_by}</span>
              : user?.role !== "staff" ? <button className="btn-ghost" onClick={() => ack(a.key)}>Acknowledge</button> : null}
          </div>
        ))}
        {rows.length === 0 && <div className="card p-6 text-sm text-ink-mute">No alerts.</div>}
      </div>
    </Page>
  );
}
