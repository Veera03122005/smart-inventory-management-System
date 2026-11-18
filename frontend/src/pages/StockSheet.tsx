import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

const REASONS = ["", "Expired", "Spilled", "Burnt", "Over-prepared", "Quality reject"];
const blank = { date: "", opening_stock: "", received_qty: "", batch_no: "", expiry_date: "", used_qty: "", wastage_qty: "", wastage_reason: "" };

export default function StockSheet() {
  const ings = useData(() => api("/ingredients"));
  const [ing, setIng] = useState("ING01");
  const [f, setF] = useState<any>(blank);
  const [hint, setHint] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const entries = useData(() => api(`/manual-entries?ingredient_id=${ing}&limit=30`), 0, [ing]);
  const unit = ings.data?.find((i: any) => i.ingredient_id === ing)?.unit || "";
  const prefill = () => api(`/manual-entries/prefill?ingredient_id=${ing}`).then((p) => { setF({ ...blank, date: p.date, opening_stock: String(p.opening_stock) }); setHint(p.suggested_used); });
  useEffect(() => { prefill(); setErr(""); setOk(""); /* eslint-disable-next-line */ }, [ing]);
  const n = (k: string) => Number(f[k] || 0);
  const closing = n("opening_stock") + n("received_qty") - n("used_qty") - n("wastage_qty");
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    setErr(""); setOk("");
    try {
      const r = await api("/manual-entries", { body: { ...f, ingredient_id: ing } });
      setOk(`Saved. Closing stock ${fmt(r.closing_stock)} ${unit}${r.days_covered > 1 ? `; this entry covers ${r.days_covered} days and will be split by the weekday pattern` : ""}. Forecasts are being refreshed.`);
      entries.reload(); prefill();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Page title="Daily stock sheet" sub="The manual channel. Kitchens without sensors get the same forecasts from these entries.">
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="card p-5 space-y-3 lg:col-span-2">
          <div><label className="label">Ingredient</label>
            <select className="input" value={ing} onChange={(e) => setIng(e.target.value)}>
              {(ings.data || []).map((i: any) => <option key={i.ingredient_id} value={i.ingredient_id}>{i.name} ({i.unit})</option>)}
            </select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Date</label><input className="input" type="date" value={f.date} onChange={set("date")} /></div>
            <div><label className="label">Opening stock ({unit})</label><input className="input num" type="number" step="0.1" value={f.opening_stock} onChange={set("opening_stock")} /></div>
            <div><label className="label">Received ({unit})</label><input className="input num" type="number" step="0.1" value={f.received_qty} onChange={set("received_qty")} /></div>
            <div><label className="label">Expiry of received</label><input className="input" type="date" value={f.expiry_date} onChange={set("expiry_date")} /></div>
            <div><label className="label">Batch number</label><input className="input" value={f.batch_no} onChange={set("batch_no")} placeholder="Auto if blank" /></div>
            <div><label className="label">Used ({unit})</label><input className="input num" type="number" step="0.1" value={f.used_qty} onChange={set("used_qty")} placeholder={hint ? `AI expects ~${fmt(hint)}` : ""} /></div>
            <div><label className="label">Wastage ({unit})</label><input className="input num" type="number" step="0.1" value={f.wastage_qty} onChange={set("wastage_qty")} /></div>
            <div><label className="label">Wastage reason</label><select className="input" value={f.wastage_reason} onChange={set("wastage_reason")}>{REASONS.map((r) => <option key={r} value={r}>{r || "None"}</option>)}</select></div>
          </div>
          <div className={`rounded-lg p-3 text-sm ${closing < 0 ? "bg-red-50 text-red-700" : "bg-leaf-light text-leaf-dark"}`}>
            Closing stock = opening + received − used − wastage = <span className="font-semibold num">{fmt(closing, 2)} {unit}</span>
          </div>
          <ErrorNote msg={err} /><OkNote msg={ok} />
          <button className="btn-primary" onClick={save} disabled={!f.date || f.used_qty === ""}>Save entry</button>
        </div>
        <div className="card overflow-x-auto lg:col-span-3">
          <div className="px-4 py-3 font-semibold">Recent entries</div>
          <table className="w-full">
            <thead><tr><th className="th">Date</th><th className="th text-right">Opening</th><th className="th text-right">Received</th><th className="th text-right">Used</th><th className="th text-right">Wastage</th><th className="th text-right">Closing</th><th className="th">By</th><th className="th">Status</th></tr></thead>
            <tbody>
              {(entries.data || []).map((e: any) => (
                <tr key={e.id} className={e.entry_status === "MISSED" ? "bg-amber-50/60" : ""}>
                  <td className="td text-xs">{e.date}</td><td className="td text-right num">{fmt(e.opening_stock)}</td>
                  <td className="td text-right num">{fmt(e.received_qty)}</td>
                  <td className="td text-right num">{fmt(e.used_qty)}{e.days_covered > 1 && <span className="text-[10px] text-ink-mute"> ({e.days_covered}d)</span>}</td>
                  <td className="td text-right num">{e.wastage_qty ? `${fmt(e.wastage_qty)} ${e.wastage_reason ? "· " + e.wastage_reason : ""}` : "–"}</td>
                  <td className="td text-right num">{fmt(e.closing_stock)}</td><td className="td text-xs">{e.entered_by || "–"}</td>
                  <td className="td"><Badge tone={e.entry_status === "MISSED" ? "medium" : "ok"}>{e.entry_status === "MISSED" ? "Missed" : "Entered"}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Page>
  );
}
