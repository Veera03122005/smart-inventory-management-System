import { useState } from "react";
import { api, fmt } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

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
  const live = open && devices.data?.find((d: any) => d.device_id === open.device_id);
  const start = async () => {
    setErr(""); setResult(null);
    try { setOpen(await api("/refill/open", { body: { barcode, batch_no: batch || null, expiry_date: expiry || null } })); }
    catch (e: any) { setErr(e.message); }
  };
  const finish = async () => {
    try { setResult(await api(`/refill/${open.session_id}/complete`, { method: "POST" })); setOpen(null); setBarcode(""); setBatch(""); sessions.reload(); }
    catch (e: any) { setErr(e.message); setOpen(null); sessions.reload(); }
  };
  const cancel = async () => { await api(`/refill/${open.session_id}/cancel`, { method: "POST" }); setOpen(null); sessions.reload(); };
  return (
    <Page title="Barcode refill" sub="A refill is recorded only inside a scan-opened session, so stock additions never get counted as consumption.">
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card p-5 space-y-4">
          {!open ? (
            <>
              <div className="font-semibold">1 · Scan the product barcode</div>
              <input className="input text-lg tracking-widest" placeholder="Scan or type barcode" value={barcode} autoFocus
                onChange={(e) => setBarcode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && start()} />
              <div className="flex flex-wrap gap-2">
                {(ings.data || []).map((i: any) => (
                  <button key={i.ingredient_id} className="btn-ghost text-xs" onClick={() => setBarcode(i.barcode)}>{i.name}{i.iot_enabled ? "" : " (no scale)"}</button>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Batch number</label><input className="input" value={batch} onChange={(e) => setBatch(e.target.value)} placeholder="Optional" /></div>
                <div><label className="label">Expiry date</label><input className="input" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></div>
              </div>
              <button className="btn-primary" onClick={start} disabled={!barcode}>Open refill session</button>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between"><div className="font-semibold">2 · Add stock to the {open.ingredient} bin</div><Badge tone="medium">Session {open.session_id}</Badge></div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg bg-paper p-3"><div className="label">Before</div><div className="text-2xl font-semibold num">{fmt(open.weight_before_kg, 2)}</div></div>
                <div className="rounded-lg bg-paper p-3"><div className="label">Now</div><div className="text-2xl font-semibold num">{fmt(live?.weight_kg, 2)}</div></div>
                <div className="rounded-lg bg-leaf-light p-3"><div className="label">Added</div><div className="text-2xl font-semibold num text-leaf">{fmt(Math.max(0, (live?.weight_kg ?? 0) - open.weight_before_kg), 2)}</div></div>
              </div>
              <p className="text-sm text-ink-mute">Pour the stock in and wait for the reading to settle. With the simulator running, the bin fills by itself within a few seconds.</p>
              <div className="flex gap-2"><button className="btn-primary" onClick={finish}>3 · Complete refill</button><button className="btn-ghost" onClick={cancel}>Cancel</button></div>
            </>
          )}
          <ErrorNote msg={err} />
          {result && <OkNote msg={`Refill recorded: ${fmt(result.refill_kg, 2)} kg added (${fmt(result.weight_before_kg, 2)} → ${fmt(result.weight_after_kg, 2)} kg). Session ${result.session_id}.`} />}
        </div>
        <div className="card overflow-x-auto">
          <div className="px-4 py-3 font-semibold">Recent refill sessions</div>
          <table className="w-full">
            <thead><tr><th className="th">Started</th><th className="th">Ingredient</th><th className="th text-right">Added</th><th className="th">Batch</th><th className="th">By</th><th className="th">Status</th></tr></thead>
            <tbody>
              {(sessions.data || []).map((s: any) => (
                <tr key={s.session_id}>
                  <td className="td text-xs">{s.started_at.slice(5, 16)}</td><td className="td">{s.name}</td>
                  <td className="td text-right num">{s.refill_kg != null ? `${fmt(s.refill_kg, 2)} kg` : "–"}</td>
                  <td className="td text-xs">{s.batch_no || "–"}</td><td className="td text-xs">{s.scanned_by}</td>
                  <td className="td"><Badge tone={s.status === "COMPLETED" ? "ok" : s.status === "OPEN" ? "medium" : "low"}>{s.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Page>
  );
}
