import { useState } from "react";
import { api, fmt } from "../api";
import { Badge, ConfirmModal, ErrorNote, OkNote, Page, useData } from "../ui";

export default function Refill() {
  const ings = useData(() => api("/ingredients"));
  const sessions = useData(() => api("/refill/sessions?limit=12"), 4000);
  const devices = useData(() => api("/iot/devices"), 2000);

  const [barcode, setBarcode] = useState("");
  const [batch, setBatch] = useState("");
  const [expiry, setExpiry] = useState("");
  const [open, setOpen] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const live = open && devices.data?.find((d: any) => d.device_id === open.device_id);

  const start = async () => {
    setErr("");
    setResult(null);
    try {
      setOpen(
        await api("/refill/open", {
          body: { barcode, batch_no: batch || null, expiry_date: expiry || null },
        })
      );
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const finish = async () => {
    try {
      setResult(await api(`/refill/${open.session_id}/complete`, { method: "POST" }));
      setOpen(null);
      setBarcode("");
      setBatch("");
      sessions.reload();
    } catch (e: any) {
      setErr(e.message);
      setOpen(null);
      sessions.reload();
    }
  };

  const cancel = async () => {
    await api(`/refill/${open.session_id}/cancel`, { method: "POST" });
    setOpen(null);
    setShowCancelConfirm(false);
    sessions.reload();
  };

  return (
    <Page
      title="Barcode Refill Station"
      sub="Refills are tracked inside a tare-locked session so stock additions are never falsely recorded as kitchen consumption."
    >
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Left Card: Refill Action Flow */}
        <div className="card p-6 flex flex-col justify-between">
          {!open ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-surface-border">
                <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-800 text-xs font-bold flex items-center justify-center">
                  1
                </span>
                <h2 className="text-base font-bold text-content-primary">Scan or Enter Product Barcode</h2>
              </div>

              <div>
                <label htmlFor="refill-barcode" className="label">
                  Barcode Number
                </label>
                <input
                  id="refill-barcode"
                  className="input text-lg font-mono tracking-widest"
                  placeholder="e.g. 890103000003"
                  value={barcode}
                  autoFocus
                  onChange={(e) => setBarcode(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && start()}
                  aria-required="true"
                />
              </div>

              {/* Quick Select Buttons */}
              <div>
                <span className="text-xs text-content-muted block mb-1.5 font-medium">Quick Select Registered Products:</span>
                <div className="flex flex-wrap gap-2">
                  {(ings.data || []).map((i: any) => (
                    <button
                      key={i.ingredient_id}
                      type="button"
                      className={`btn-ghost text-xs py-1 px-2.5 ${barcode === i.barcode ? "border-brand-500 bg-brand-50 text-brand-800" : ""}`}
                      onClick={() => setBarcode(i.barcode)}
                    >
                      {i.name}
                      <span className="text-[10px] text-content-subtle ml-1">
                        {i.iot_enabled ? "(IoT Scale)" : "(Manual)"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Batch & Expiry Input Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <div>
                  <label htmlFor="refill-batch" className="label">
                    Batch Number (Optional)
                  </label>
                  <input
                    id="refill-batch"
                    className="input"
                    value={batch}
                    onChange={(e) => setBatch(e.target.value)}
                    placeholder="e.g. BATCH-2026-X"
                  />
                </div>
                <div>
                  <label htmlFor="refill-expiry" className="label">
                    Expiry Date
                  </label>
                  <input
                    id="refill-expiry"
                    className="input"
                    type="date"
                    value={expiry}
                    onChange={(e) => setExpiry(e.target.value)}
                  />
                </div>
              </div>

              <div className="pt-2">
                <button
                  className="btn-primary w-full py-2.5 text-base"
                  onClick={start}
                  disabled={!barcode}
                >
                  Open Refill Session
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center justify-between pb-3 border-b border-surface-border">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-800 text-xs font-bold flex items-center justify-center">
                    2
                  </span>
                  <h2 className="text-base font-bold text-content-primary">
                    Tare Active: Add Stock to {open.ingredient} Bin
                  </h2>
                </div>
                <Badge tone="warn" withDot={true}>
                  Session #{open.session_id}
                </Badge>
              </div>

              {/* Weight Comparison Metrics */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-xl bg-surface-muted/60 p-3.5 border border-surface-border">
                  <div className="label mb-1">Tare Baseline</div>
                  <div className="text-2xl font-bold num text-content-secondary">
                    {fmt(open.weight_before_kg, 2)} <span className="text-xs text-content-muted font-normal">kg</span>
                  </div>
                </div>
                <div className="rounded-xl bg-surface-muted/60 p-3.5 border border-surface-border">
                  <div className="label mb-1">Live Weight</div>
                  <div className="text-2xl font-bold num text-content-primary">
                    {fmt(live?.weight_kg, 2)} <span className="text-xs text-content-muted font-normal">kg</span>
                  </div>
                </div>
                <div className="rounded-xl bg-emerald-50 p-3.5 border border-emerald-200">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-800 mb-1">Net Added</div>
                  <div className="text-2xl font-extrabold num text-emerald-700">
                    +{fmt(Math.max(0, (live?.weight_kg ?? 0) - open.weight_before_kg), 2)}{" "}
                    <span className="text-xs font-normal text-emerald-600">kg</span>
                  </div>
                </div>
              </div>

              <div className="rounded-lg bg-slate-50 p-3 text-xs text-content-muted flex items-start gap-2 border border-slate-200/60">
                <svg className="w-4 h-4 text-content-subtle shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  Pour stock into the bin and wait for the weight reading to stabilize. With the simulator running, the bin fills automatically within a few seconds.
                </span>
              </div>

              <div className="flex gap-3 pt-2">
                <button className="btn-primary flex-1 py-2.5" onClick={finish}>
                  Complete Refill
                </button>
                <button className="btn-ghost" onClick={() => setShowCancelConfirm(true)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="mt-4">
            <ErrorNote msg={err} onDismiss={() => setErr("")} />
            {result && (
              <OkNote
                msg={`Refill completed successfully: +${fmt(result.refill_kg, 2)} kg registered (${fmt(
                  result.weight_before_kg,
                  2
                )} kg → ${fmt(result.weight_after_kg, 2)} kg). Logged in session #${result.session_id}.`}
                onDismiss={() => setResult(null)}
              />
            )}
          </div>
        </div>

        {/* Right Card: Recent Refill Sessions Log */}
        <div className="card overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <h2 className="text-base font-bold text-content-primary">Recent Refill Sessions</h2>
            <span className="text-xs text-content-muted num">{sessions.data?.length || 0} entries</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Started</th>
                  <th className="th" scope="col">Ingredient</th>
                  <th className="th text-right" scope="col">Net Added</th>
                  <th className="th" scope="col">Batch</th>
                  <th className="th" scope="col">Scanned By</th>
                  <th className="th text-center" scope="col">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(sessions.data || []).map((s: any) => (
                  <tr key={s.session_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="td text-xs font-mono text-content-secondary">{s.started_at.slice(5, 16)}</td>
                    <td className="td font-medium text-content-primary">{s.name}</td>
                    <td className="td text-right num font-semibold">
                      {s.refill_kg != null ? (
                        <span className="text-emerald-700">+{fmt(s.refill_kg, 2)} kg</span>
                      ) : (
                        <span className="text-content-subtle">–</span>
                      )}
                    </td>
                    <td className="td text-xs font-mono text-content-muted">{s.batch_no || "–"}</td>
                    <td className="td text-xs text-content-secondary">{s.scanned_by}</td>
                    <td className="td text-center">
                      <Badge
                        tone={s.status === "COMPLETED" ? "ok" : s.status === "OPEN" ? "warn" : "low"}
                        withDot={s.status === "OPEN"}
                      >
                        {s.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ----------------- Cancel Session Modal ----------------- */}
      <ConfirmModal
        isOpen={showCancelConfirm}
        title="Abort Refill Session"
        message="Are you sure you want to cancel this active refill session? Any added weight may be reconciled as an untracked variance."
        confirmLabel="Abort Session"
        confirmTone="danger"
        onConfirm={cancel}
        onCancel={() => setShowCancelConfirm(false)}
      />
    </Page>
  );
}
