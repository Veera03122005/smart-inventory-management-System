import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

const REASONS = ["", "Expired", "Spilled", "Burnt", "Over-prepared", "Quality reject"];
const blank = {
  date: "",
  opening_stock: "",
  received_qty: "",
  batch_no: "",
  expiry_date: "",
  used_qty: "",
  wastage_qty: "",
  wastage_reason: "",
};

export default function StockSheet() {
  const ings = useData(() => api("/ingredients"));
  const [ing, setIng] = useState("ING01");
  const [f, setF] = useState<any>(blank);
  const [hint, setHint] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const entries = useData(() => api(`/manual-entries?ingredient_id=${ing}&limit=30`), 0, [ing]);

  const unit = ings.data?.find((i: any) => i.ingredient_id === ing)?.unit || "";

  const prefill = () =>
    api(`/manual-entries/prefill?ingredient_id=${ing}`).then((p) => {
      setF({ ...blank, date: p.date, opening_stock: String(p.opening_stock) });
      setHint(p.suggested_used);
    });

  useEffect(() => {
    prefill();
    setErr("");
    setOk("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ing]);

  const n = (k: string) => Number(f[k] || 0);
  const closing = n("opening_stock") + n("received_qty") - n("used_qty") - n("wastage_qty");
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setErr("");
    setOk("");
    try {
      const r = await api("/manual-entries", { body: { ...f, ingredient_id: ing } });
      setOk(
        `Entry saved successfully. Calculated closing stock: ${fmt(r.closing_stock)} ${unit}${
          r.days_covered > 1
            ? ` (Entry covers ${r.days_covered} days; split evenly by Tamil Nadu calendar weekday consumption)`
            : ""
        }. ML forecasts refreshed.`
      );
      entries.reload();
      prefill();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  return (
    <Page
      title="Daily Stock Register"
      sub="The manual recording channel. Kitchens without load cells receive identical AI demand forecasts and replenishment advice from these ledger entries."
    >
      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left Form: Entry Input (2 Columns) */}
        <div className="card p-6 space-y-4 lg:col-span-2 flex flex-col justify-between">
          <div>
            <div className="pb-3 border-b border-surface-border mb-4">
              <label htmlFor="stock-ingredient-select" className="label">
                Select Ingredient
              </label>
              <select
                id="stock-ingredient-select"
                className="input text-base font-semibold"
                value={ing}
                onChange={(e) => setIng(e.target.value)}
              >
                {(ings.data || []).map((i: any) => (
                  <option key={i.ingredient_id} value={i.ingredient_id}>
                    {i.name} ({i.unit})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <div>
                <label htmlFor="stock-date" className="label">
                  Register Date
                </label>
                <input
                  id="stock-date"
                  className="input"
                  type="date"
                  value={f.date}
                  onChange={set("date")}
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor="stock-opening" className="label">
                  Opening Stock ({unit})
                </label>
                <input
                  id="stock-opening"
                  className="input num"
                  type="number"
                  step="0.1"
                  value={f.opening_stock}
                  onChange={set("opening_stock")}
                />
              </div>

              <div>
                <label htmlFor="stock-received" className="label">
                  Received Today ({unit})
                </label>
                <input
                  id="stock-received"
                  className="input num"
                  type="number"
                  step="0.1"
                  value={f.received_qty}
                  onChange={set("received_qty")}
                  placeholder="0.0"
                />
              </div>

              <div>
                <label htmlFor="stock-expiry" className="label">
                  Expiry of Received
                </label>
                <input
                  id="stock-expiry"
                  className="input"
                  type="date"
                  value={f.expiry_date}
                  onChange={set("expiry_date")}
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor="stock-batch" className="label">
                  Batch Number
                </label>
                <input
                  id="stock-batch"
                  className="input"
                  value={f.batch_no}
                  onChange={set("batch_no")}
                  placeholder="Auto-generated if left blank"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="stock-used" className="label mb-0">
                    Used Today ({unit}) *
                  </label>
                  {hint && (
                    <span className="text-[10px] text-brand-700 bg-brand-50 px-1.5 py-0.5 rounded border border-brand-200">
                      AI: ~{fmt(hint)}
                    </span>
                  )}
                </div>
                <input
                  id="stock-used"
                  className="input num font-semibold"
                  type="number"
                  step="0.1"
                  value={f.used_qty}
                  onChange={set("used_qty")}
                  placeholder={hint ? `~${fmt(hint)}` : "Required"}
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor="stock-wastage" className="label">
                  Wastage / Spoilage ({unit})
                </label>
                <input
                  id="stock-wastage"
                  className="input num"
                  type="number"
                  step="0.1"
                  value={f.wastage_qty}
                  onChange={set("wastage_qty")}
                  placeholder="0.0"
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor="stock-reason" className="label">
                  Wastage Reason
                </label>
                <select
                  id="stock-reason"
                  className="input"
                  value={f.wastage_reason}
                  onChange={set("wastage_reason")}
                >
                  {REASONS.map((r) => (
                    <option key={r} value={r}>
                      {r || "None / Normal"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Calculated Closing Stock Banner */}
            <div
              className={`rounded-xl p-4 text-sm mt-4 border transition-colors ${
                closing < 0
                  ? "bg-rose-50 text-rose-800 border-rose-200"
                  : "bg-emerald-50 text-emerald-900 border-emerald-200"
              }`}
              aria-live="polite"
            >
              <div className="text-xs uppercase font-semibold tracking-wider text-content-muted mb-0.5">
                Calculated Closing Balance
              </div>
              <div className="text-lg font-bold">
                Opening + Received − Used − Wastage ={" "}
                <span className="num font-extrabold text-xl ml-1">
                  {fmt(closing, 2)} {unit}
                </span>
              </div>
              {closing < 0 && (
                <div className="text-xs text-rose-700 mt-1 font-medium">
                  Warning: Closing stock cannot be negative. Please verify opening and used quantities.
                </div>
              )}
            </div>

            <div className="mt-3">
              <ErrorNote msg={err} onDismiss={() => setErr("")} />
              <OkNote msg={ok} onDismiss={() => setOk("")} />
            </div>
          </div>

          <div className="pt-4 border-t border-surface-border">
            <button
              className="btn-primary w-full py-2.5 text-base"
              onClick={save}
              disabled={!f.date || f.used_qty === ""}
            >
              Save Daily Ledger Entry
            </button>
          </div>
        </div>

        {/* Right Table: Recent Entries (3 Columns) */}
        <div className="card overflow-hidden flex flex-col lg:col-span-3">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Recorded Register History</h2>
              <p className="text-xs text-content-muted mt-0.5">Showing last 30 entries for selected ingredient</p>
            </div>
            <span className="text-xs text-content-muted num">{entries.data?.length || 0} rows</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Date</th>
                  <th className="th text-right" scope="col">Opening</th>
                  <th className="th text-right" scope="col">Received</th>
                  <th className="th text-right" scope="col">Used</th>
                  <th className="th text-right" scope="col">Wastage</th>
                  <th className="th text-right" scope="col">Closing</th>
                  <th className="th" scope="col">Staff</th>
                  <th className="th text-center" scope="col">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(entries.data || []).map((e: any) => {
                  const isMissed = e.entry_status === "MISSED";
                  return (
                    <tr
                      key={e.id}
                      className={`hover:bg-slate-50/80 transition-colors ${
                        isMissed ? "bg-amber-50/50" : ""
                      }`}
                    >
                      <td className="td text-xs font-mono font-medium text-content-primary">{e.date}</td>
                      <td className="td text-right num text-content-secondary">{fmt(e.opening_stock)}</td>
                      <td className="td text-right num text-content-secondary">
                        {e.received_qty > 0 ? `+${fmt(e.received_qty)}` : "–"}
                      </td>
                      <td className="td text-right num font-bold text-content-primary">
                        {fmt(e.used_qty)}
                        {e.days_covered > 1 && (
                          <span className="text-[10px] font-normal text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200 ml-1">
                            {e.days_covered}d
                          </span>
                        )}
                      </td>
                      <td className="td text-right num">
                        {e.wastage_qty > 0 ? (
                          <span className="text-rose-600 font-medium">
                            {fmt(e.wastage_qty)}
                            {e.wastage_reason && (
                              <span className="text-[10px] text-content-muted block">{e.wastage_reason}</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-content-subtle">–</span>
                        )}
                      </td>
                      <td className="td text-right num font-bold text-content-primary">{fmt(e.closing_stock)}</td>
                      <td className="td text-xs text-content-secondary">{e.entered_by || "–"}</td>
                      <td className="td text-center">
                        <Badge tone={isMissed ? "warn" : "ok"} withDot={isMissed}>
                          {isMissed ? "Reconstructed" : "Entered"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Page>
  );
}
