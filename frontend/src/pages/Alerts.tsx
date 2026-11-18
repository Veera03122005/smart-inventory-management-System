import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, EmptyState, Loading, Page, useData } from "../ui";

const LABEL: Record<string, string> = {
  LOW_STOCK: "Low Stock",
  EXPIRY_RISK: "Expiry Risk",
  USAGE_ANOMALY: "Unusual Consumption",
  SUDDEN_DROP: "Sudden Weight Drop",
  MISSED_ENTRY: "Missed Ledger Entry",
  REFILL_NEEDED: "Refill Needed",
};

export default function Alerts() {
  const { user } = useAuth();
  const { data, reload, loading } = useData(() => api("/alerts"), 10000);
  const [type, setType] = useState("ALL");
  const [ackingKey, setAckingKey] = useState<string | null>(null);

  if (loading || !data) return <Loading label="Loading kitchen alerts…" />;

  const types = Array.from(new Set(data.map((a: any) => a.type))) as string[];
  const rows = data.filter((a: any) => type === "ALL" || a.type === type);

  const ack = async (key: string) => {
    setAckingKey(key);
    try {
      await api("/alerts/ack", { body: { key } });
      await reload();
    } finally {
      setAckingKey(null);
    }
  };

  return (
    <Page
      title="Kitchen Alerts & Action Items"
      sub="Automated rule checks (stockouts, batch expiry, missed registers) and AI statistical anomaly detections."
    >
      {/* ----------------- Filter Chips ----------------- */}
      <div className="flex flex-wrap gap-2 mb-6" role="toolbar" aria-label="Filter alerts by category">
        <button
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
            type === "ALL"
              ? "bg-brand-600 text-white shadow-sm"
              : "bg-white text-content-secondary hover:bg-slate-50 border border-surface-border"
          }`}
          onClick={() => setType("ALL")}
          aria-pressed={type === "ALL"}
        >
          All Categories ({data.length})
        </button>
        {types.map((t) => (
          <button
            key={t}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              type === t
                ? "bg-brand-600 text-white shadow-sm"
                : "bg-white text-content-secondary hover:bg-slate-50 border border-surface-border"
            }`}
            onClick={() => setType(t)}
            aria-pressed={type === t}
          >
            {LABEL[t] || t} ({data.filter((a: any) => a.type === t).length})
          </button>
        ))}
      </div>

      {/* ----------------- Alerts List ----------------- */}
      <div className="space-y-3.5">
        {rows.map((a: any) => {
          const isAcking = ackingKey === a.key;
          return (
            <div
              key={a.key}
              className={`card p-5 flex flex-col sm:flex-row sm:items-start justify-between gap-4 card-hover ${
                a.acknowledged ? "opacity-60 bg-slate-50/50" : ""
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-1.5">
                  <Badge tone={a.severity} withDot={true}>
                    {a.severity.toUpperCase()}
                  </Badge>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-content-secondary">
                    {LABEL[a.type] || a.type}
                  </span>
                  <h3 className="text-base font-bold text-content-primary">{a.title}</h3>
                </div>

                <p className="text-sm text-content-muted mt-1 leading-relaxed">{a.detail}</p>

                <div className="text-xs mt-3 flex items-center gap-2 p-2 rounded-lg bg-surface-muted/60 border border-surface-border/60">
                  <span className="font-semibold text-content-primary">Recommended Action:</span>
                  <span className="text-content-secondary">{a.action}</span>
                </div>
              </div>

              <div className="shrink-0 sm:self-center">
                {a.acknowledged ? (
                  <span className="inline-flex items-center gap-1.5 text-xs text-content-muted font-medium bg-slate-100 px-3 py-1.5 rounded-lg">
                    <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Acknowledged by {a.acked_by}
                  </span>
                ) : user?.role !== "staff" ? (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => ack(a.key)}
                    disabled={isAcking}
                  >
                    {isAcking ? "Updating…" : "Acknowledge"}
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}

        {rows.length === 0 && (
          <EmptyState
            title="Zero Active Alerts"
            description="All ingredients have sufficient stock cover, zero sudden load-cell drops have been detected, and all batches remain safely within shelf-life."
          />
        )}
      </div>
    </Page>
  );
}
