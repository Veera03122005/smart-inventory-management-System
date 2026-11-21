import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

type Tab = "opening" | "deliveries" | "upload" | "closing" | "history";

export default function StockSheet() {
  const [tab, setTab] = useState<Tab>("opening");
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const ings = useData(() => api("/ingredients"));
  const dailyStatus = useData(() => api(`/traditional/status?date=${date}`), 0, [date]);

  // Status notes
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 1. Opening State
  const openingData = useData(() => api(`/traditional/opening?date=${date}`), 0, [date]);
  const [openingCounts, setOpeningCounts] = useState<{ [id: string]: number | string }>({});

  useEffect(() => {
    if (openingData.data?.rows) {
      const map: any = {};
      openingData.data.rows.forEach((r: any) => {
        map[r.ingredient_id] = r.physical_qty ?? "";
      });
      setOpeningCounts(map);
    }
  }, [openingData.data]);

  const saveOpening = async () => {
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      const counts = (ings.data || []).map((ing: any) => ({
        ingredient_id: ing.ingredient_id,
        physical_qty: Number(openingCounts[ing.ingredient_id] || 0),
      }));
      const res: any = await api("/traditional/opening", {
        body: { date, counts },
      });
      setOk(
        `Morning opening count verified and posted for ${date}. (${res.counts_recorded || counts.length} ingredients recorded).`
      );
      openingData.reload();
      dailyStatus.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // 2. Deliveries State
  const deliveriesData = useData(() => api(`/traditional/deliveries?date=${date}`), 0, [date]);
  const [delivForm, setDelivForm] = useState({
    supplier_name: "",
    invoice_no: "",
    invoice_date: date,
    ingredient_id: "ING01",
    billed_qty: "",
    unit_price_rs: "",
    batch_no: "",
    expiry_date: "",
  });

  const saveDelivery = async () => {
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      const ing = ings.data?.find((i: any) => i.ingredient_id === delivForm.ingredient_id);
      const res: any = await api("/traditional/delivery", {
        body: {
          supplier_name: delivForm.supplier_name,
          invoice_no: delivForm.invoice_no,
          invoice_date: delivForm.invoice_date || date,
          items: [
            {
              ingredient_id: delivForm.ingredient_id,
              billed_qty: Number(delivForm.billed_qty),
              unit: ing?.unit || "kg",
              unit_price_rs: Number(delivForm.unit_price_rs || 0),
              batch_no: delivForm.batch_no || undefined,
              expiry_date: delivForm.expiry_date || undefined,
            },
          ],
        },
      });
      setOk(`Delivery invoice #${delivForm.invoice_no} posted successfully to inventory journal.`);
      setDelivForm({
        supplier_name: delivForm.supplier_name,
        invoice_no: "",
        invoice_date: date,
        ingredient_id: "ING01",
        billed_qty: "",
        unit_price_rs: "",
        batch_no: "",
        expiry_date: "",
      });
      deliveriesData.reload();
      dailyStatus.reload();
      closingData.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // 3. Document Staging & Upload State
  const uploadsData = useData(() => api("/traditional/uploads"), 0, [tab]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [workflowType, setWorkflowType] = useState("DELIVERY_INVOICE");
  const [activeStaged, setActiveStaged] = useState<any>(null);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      fd.append("workflow_type", workflowType);
      const token = localStorage.getItem("smartstock_token") || "";
      const resp = await fetch("/api/traditional/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Upload failed");
      setOk(`Document '${uploadFile.name}' uploaded and extracted successfully. Ready for staff review.`);
      setActiveStaged(data);
      setStagedRows(data.rows || []);
      setEditingStaged(false);
      setUploadFile(null);
      uploadsData.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const [editingStaged, setEditingStaged] = useState(false);
  const [stagedRows, setStagedRows] = useState<any[]>([]);

  const loadStaged = async (uid: string) => {
    try {
      setErr("");
      const res = await api(`/traditional/staged/${uid}`);
      setActiveStaged(res);
      setStagedRows(res.rows || []);
      setEditingStaged(false);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const saveStagedEdits = async () => {
    if (!activeStaged) return;
    setSubmitting(true);
    setErr("");
    try {
      const res = await api(`/traditional/staged/${activeStaged.upload_id}`, {
        method: "PUT",
        body: { rows: stagedRows },
      });
      setActiveStaged({ ...activeStaged, rows: res.rows });
      setStagedRows(res.rows || []);
      setEditingStaged(false);
      setOk("Staged draft updated successfully with corrected values.");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const downloadOriginal = async (uid: string, filename: string) => {
    try {
      const token = localStorage.getItem("smartstock_token") || "";
      const resp = await fetch(`/api/traditional/uploads/${uid}/file`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || "Failed to download original document");
      }
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  // 4. Closing State
  const closingData = useData(() => api(`/traditional/closing?date=${date}`), 0, [date]);
  const [closingCounts, setClosingCounts] = useState<{ [id: string]: number | string }>({});

  useEffect(() => {
    if (closingData.data?.rows) {
      const map: any = {};
      closingData.data.rows.forEach((r: any) => {
        map[r.ingredient_id] = r.physical_closing_qty ?? r.available_qty ?? "";
      });
      setClosingCounts(map);
    }
  }, [closingData.data]);

  const saveClosing = async () => {
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      const counts = (closingData.data?.rows || []).map((row: any) => ({
        ingredient_id: row.ingredient_id,
        physical_qty: Number(closingCounts[row.ingredient_id] || 0),
      }));
      const res: any = await api("/traditional/closing", {
        body: { date, counts },
      });
      setOk(
        `Evening closing stock reconciled and posted. Depletion movements calculated and posted exactly once.`
      );
      closingData.reload();
      dailyStatus.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // 5. History State
  const historyEntries = useData(() => api("/manual-entries?limit=50"), 0, [tab]);

  const st = dailyStatus.data || {};

  return (
    <Page
      title="Kitchen Stock Register"
      sub="Traditional kitchen inventory workflow. Record morning opening counts, supplier deliveries, review document drafts, and reconcile evening closing counts."
      actions={
        <div className="flex items-center gap-3">
          <label htmlFor="reg-date" className="text-xs font-semibold text-content-muted">
            Business Date:
          </label>
          <input
            id="reg-date"
            type="date"
            className="input py-1 px-2.5 text-sm font-semibold max-w-[155px]"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
      }
    >
      {/* ----------------- Daily Operational Progress Bar ----------------- */}
      <div className="card p-4 mb-6 bg-slate-50/70 border-surface-border flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-content-muted">Morning:</span>
            <Badge tone={st.opening_status === "POSTED" ? "ok" : st.opening_status === "PARTIAL" ? "warn" : "muted"}>
              {st.opening_status || "PENDING"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-content-muted">Deliveries:</span>
            <span className="text-xs font-semibold text-content-primary">
              {st.deliveries_invoices_count || 0} invoice(s) · {st.deliveries_total_kg || 0} kg
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-content-muted">Evening:</span>
            <Badge tone={st.closing_status === "POSTED" ? "ok" : "muted"}>
              {st.closing_status || "PENDING"}
            </Badge>
          </div>
        </div>

        {st.unexplained_depletions_count > 0 && (
          <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-md">
            {st.unexplained_depletions_count} depletion item(s) logged for Manager triage
          </span>
        )}
      </div>

      {/* ----------------- Tab Navigation ----------------- */}
      <div className="flex border-b border-surface-border mb-6 space-x-1 sm:space-x-4 overflow-x-auto">
        <button
          onClick={() => { setTab("opening"); setErr(""); setOk(""); }}
          className={`py-2.5 px-4 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
            tab === "opening"
              ? "border-emerald-600 text-emerald-700 bg-emerald-50/40 rounded-t-lg"
              : "border-transparent text-content-muted hover:text-content-primary"
          }`}
        >
          1. Morning Opening Stock
        </button>
        <button
          onClick={() => { setTab("deliveries"); setErr(""); setOk(""); }}
          className={`py-2.5 px-4 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
            tab === "deliveries"
              ? "border-emerald-600 text-emerald-700 bg-emerald-50/40 rounded-t-lg"
              : "border-transparent text-content-muted hover:text-content-primary"
          }`}
        >
          2. Supplier Deliveries
        </button>
        <button
          onClick={() => { setTab("upload"); setErr(""); setOk(""); }}
          className={`py-2.5 px-4 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
            tab === "upload"
              ? "border-emerald-600 text-emerald-700 bg-emerald-50/40 rounded-t-lg"
              : "border-transparent text-content-muted hover:text-content-primary"
          }`}
        >
          3. Document Upload & Review
        </button>
        <button
          onClick={() => { setTab("closing"); setErr(""); setOk(""); }}
          className={`py-2.5 px-4 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
            tab === "closing"
              ? "border-emerald-600 text-emerald-700 bg-emerald-50/40 rounded-t-lg"
              : "border-transparent text-content-muted hover:text-content-primary"
          }`}
        >
          4. Evening Closing Reconciliation
        </button>
        <button
          onClick={() => { setTab("history"); setErr(""); setOk(""); }}
          className={`py-2.5 px-4 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
            tab === "history"
              ? "border-emerald-600 text-emerald-700 bg-emerald-50/40 rounded-t-lg"
              : "border-transparent text-content-muted hover:text-content-primary"
          }`}
        >
          Submission History
        </button>
      </div>

      <div className="mb-4">
        <ErrorNote msg={err} onDismiss={() => setErr("")} />
        <OkNote msg={ok} onDismiss={() => setOk("")} />
      </div>

      {/* ----------------- TAB 1: MORNING OPENING STOCK ----------------- */}
      {tab === "opening" && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Morning Opening Physical Counts</h2>
              <p className="text-xs text-content-muted mt-0.5">
                Staff verifies starting physical quantities on hand before prep and service begin.
              </p>
            </div>
            <button
              onClick={saveOpening}
              disabled={submitting}
              className="btn-primary text-sm py-2 px-5"
            >
              {submitting ? "Verifying…" : "Verify & Post Opening Stock"}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Ingredient</th>
                  <th className="th" scope="col">Unit</th>
                  <th className="th" scope="col">Physical Opening Count</th>
                  <th className="th text-center" scope="col">Status</th>
                  <th className="th" scope="col">Last Verification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(openingData.data?.rows || []).map((r: any) => (
                  <tr key={r.ingredient_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="td font-medium text-content-primary">{r.name}</td>
                    <td className="td text-content-muted font-mono">{r.unit}</td>
                    <td className="td">
                      <div className="flex items-center gap-2 max-w-[180px]">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          className="input py-1 px-2.5 font-mono text-sm"
                          value={openingCounts[r.ingredient_id] ?? ""}
                          onChange={(e) =>
                            setOpeningCounts({ ...openingCounts, [r.ingredient_id]: e.target.value })
                          }
                          placeholder="0.0"
                        />
                        <span className="text-xs text-content-muted">{r.unit}</span>
                      </div>
                    </td>
                    <td className="td text-center">
                      <Badge tone={r.recorded ? "ok" : "muted"}>{r.status}</Badge>
                    </td>
                    <td className="td text-xs text-content-muted">
                      {r.verified_at ? `${r.verified_at.slice(0, 16)} by ${r.verified_by}` : "Not yet verified"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------- TAB 2: SUPPLIER DELIVERIES ----------------- */}
      {tab === "deliveries" && (
        <div className="grid lg:grid-cols-5 gap-6">
          {/* Delivery Entry Form */}
          <div className="card p-6 lg:col-span-2 space-y-4 flex flex-col justify-between">
            <div>
              <div className="pb-3 border-b border-surface-border mb-4">
                <h2 className="text-base font-bold text-content-primary">Record Supplier Delivery</h2>
                <p className="text-xs text-content-muted mt-0.5">
                  Posts verified STOCK_IN movements to the inventory journal. Duplicate invoice numbers are rejected.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="label">Supplier Name *</label>
                  <input
                    className="input"
                    value={delivForm.supplier_name}
                    onChange={(e) => setDelivForm({ ...delivForm, supplier_name: e.target.value })}
                    placeholder="e.g. Metro Meats Bangalore"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Invoice Number *</label>
                    <input
                      className="input font-mono"
                      value={delivForm.invoice_no}
                      onChange={(e) => setDelivForm({ ...delivForm, invoice_no: e.target.value })}
                      placeholder="e.g. INV-9842"
                    />
                  </div>
                  <div>
                    <label className="label">Invoice Date *</label>
                    <input
                      type="date"
                      className="input"
                      value={delivForm.invoice_date}
                      onChange={(e) => setDelivForm({ ...delivForm, invoice_date: e.target.value })}
                    />
                  </div>
                </div>

                <div>
                  <label className="label">Ingredient Delivered *</label>
                  <select
                    className="input font-semibold"
                    value={delivForm.ingredient_id}
                    onChange={(e) => setDelivForm({ ...delivForm, ingredient_id: e.target.value })}
                  >
                    {(ings.data || []).map((i: any) => (
                      <option key={i.ingredient_id} value={i.ingredient_id}>
                        {i.name} ({i.unit})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Billed Quantity *</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      className="input font-mono"
                      value={delivForm.billed_qty}
                      onChange={(e) => setDelivForm({ ...delivForm, billed_qty: e.target.value })}
                      placeholder="e.g. 25.0"
                    />
                  </div>
                  <div>
                    <label className="label">Billed Unit Price (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="input font-mono"
                      value={delivForm.unit_price_rs}
                      onChange={(e) => setDelivForm({ ...delivForm, unit_price_rs: e.target.value })}
                      placeholder="e.g. 220.0"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Batch Number</label>
                    <input
                      className="input font-mono"
                      value={delivForm.batch_no}
                      onChange={(e) => setDelivForm({ ...delivForm, batch_no: e.target.value })}
                      placeholder="Optional"
                    />
                  </div>
                  <div>
                    <label className="label">Expiry Date</label>
                    <input
                      type="date"
                      className="input"
                      value={delivForm.expiry_date}
                      onChange={(e) => setDelivForm({ ...delivForm, expiry_date: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-surface-border">
              <button
                className="btn-primary w-full py-2.5 text-sm"
                onClick={saveDelivery}
                disabled={submitting || !delivForm.supplier_name || !delivForm.invoice_no || !delivForm.billed_qty}
              >
                {submitting ? "Posting Delivery…" : "Post Verified Delivery"}
              </button>
            </div>
          </div>

          {/* Deliveries List */}
          <div className="card overflow-hidden lg:col-span-3 flex flex-col">
            <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
              <div>
                <h2 className="text-base font-bold text-content-primary">Posted Deliveries for {date}</h2>
                <p className="text-xs text-content-muted mt-0.5">Verified supplier shipments posted to inventory</p>
              </div>
              <span className="text-xs text-content-muted num">{deliveriesData.data?.length || 0} shipments</span>
            </div>

            <div className="overflow-x-auto flex-1">
              <table className="w-full text-left text-sm" role="table">
                <thead>
                  <tr className="bg-slate-50/70">
                    <th className="th" scope="col">Invoice #</th>
                    <th className="th" scope="col">Supplier</th>
                    <th className="th" scope="col">Item Delivered</th>
                    <th className="th text-right" scope="col">Quantity</th>
                    <th className="th text-right" scope="col">Price / kg</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(deliveriesData.data || []).map((d: any) => (
                    <tr key={d.item_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="td font-mono font-medium text-content-primary">{d.invoice_no}</td>
                      <td className="td text-content-secondary">{d.supplier_name}</td>
                      <td className="td font-medium text-content-primary">{d.ingredient_name}</td>
                      <td className="td text-right font-mono font-bold text-emerald-700">
                        +{fmt(d.billed_qty)} {d.unit}
                      </td>
                      <td className="td text-right font-mono text-content-muted">
                        {d.unit_price_rs ? `₹${d.unit_price_rs}` : "—"}
                      </td>
                    </tr>
                  ))}
                  {(!deliveriesData.data || deliveriesData.data.length === 0) && (
                    <tr>
                      <td colSpan={5} className="td text-center py-8 text-content-muted">
                        No supplier shipments recorded for {date} yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- TAB 3: DOCUMENT UPLOAD & STAGING REVIEW ----------------- */}
      {tab === "upload" && (
        <div className="space-y-6">
          <div className="card p-6">
            <h2 className="text-base font-bold text-content-primary mb-1">Upload Stock Sheet or Supplier Invoice</h2>
            <p className="text-xs text-content-muted mb-4">
              Supported formats: CSV, Excel (.xlsx/.xls), PDF invoices, and physical stock sheet photos (JPG, PNG).
              Extracted values are staged as drafts for staff correction before any ledger movement is posted.
            </p>

            <div className="grid sm:grid-cols-3 gap-4 items-end">
              <div>
                <label className="label">Workflow Type *</label>
                <select
                  className="input font-semibold"
                  value={workflowType}
                  onChange={(e) => setWorkflowType(e.target.value)}
                >
                  <option value="DELIVERY_INVOICE">Supplier Delivery Invoice</option>
                  <option value="OPENING_STOCK">Morning Opening Stock Count</option>
                  <option value="CLOSING_STOCK">Evening Closing Reconciliation</option>
                </select>
              </div>

              <div>
                <label className="label">Select Document File *</label>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.pdf,.jpg,.jpeg,.png"
                  className="input text-xs"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
              </div>

              <div>
                <button
                  onClick={handleUpload}
                  disabled={submitting || !uploadFile}
                  className="btn-primary w-full py-2.5 text-sm"
                >
                  {submitting ? "Extracting…" : "Upload & Extract Draft"}
                </button>
              </div>
            </div>
          </div>

          {/* Staged Draft Review Table */}
          {activeStaged && (
            <div className="card overflow-hidden border-2 border-emerald-500/30">
              <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-emerald-50/40">
                <div>
                  <h3 className="text-base font-bold text-content-primary">
                    Review Draft: {activeStaged.filename}
                  </h3>
                  <p className="text-xs text-content-muted mt-0.5">
                    Status: <Badge tone="warn">{activeStaged.status}</Badge> · Verify extracted values before confirming
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => downloadOriginal(activeStaged.upload_id, activeStaged.filename)}
                    className="btn-ghost btn-sm text-xs py-1 px-3 border border-slate-300"
                  >
                    Download Original File
                  </button>
                  {activeStaged.status !== "POSTED" && (
                    <button
                      onClick={() => {
                        if (editingStaged) {
                          saveStagedEdits();
                        } else {
                          setEditingStaged(true);
                        }
                      }}
                      disabled={submitting}
                      className="btn-primary btn-sm text-xs py-1 px-3"
                    >
                      {editingStaged ? (submitting ? "Saving…" : "Save Staged Corrections") : "Edit Staged Values"}
                    </button>
                  )}
                </div>
              </div>

              {/* OCR Limitation Notice for Images */}
              {(activeStaged.file_type === "jpeg" || activeStaged.file_type === "png") && (
                <div className="mx-5 mt-4 p-3 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg text-xs flex items-center justify-between">
                  <div>
                    <span className="font-bold">Manual Entry Required:</span> Optical Character Recognition (OCR) is not supported for scanned images. Please review and input physical counts manually before confirming.
                  </div>
                  <span className="text-[10px] font-bold uppercase bg-amber-200 text-amber-900 px-2 py-0.5 rounded">
                    Photo Upload
                  </span>
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm" role="table">
                  <thead>
                    <tr className="bg-slate-50/70">
                      <th className="th">Ingredient</th>
                      <th className="th text-right">Opening Qty</th>
                      <th className="th text-right">Received Qty</th>
                      <th className="th text-right">Closing Qty</th>
                      <th className="th">Supplier / Invoice</th>
                      <th className="th text-center">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(stagedRows.length > 0 ? stagedRows : activeStaged.rows || []).map((r: any, idx: number) => (
                      <tr key={idx} className="hover:bg-slate-50/80">
                        <td className="td font-medium">
                          {r.name || r.raw_name || "Unknown item"}
                          {r.flags?.includes("UNCERTAIN_MATCH") && (
                            <span className="ml-2 text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">Uncertain</span>
                          )}
                          {r.flags?.includes("MANUAL_ENTRY_REQUIRED") && (
                            <span className="ml-2 text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">Manual Keying</span>
                          )}
                        </td>
                        <td className="td text-right font-mono">
                          {editingStaged ? (
                            <input
                              type="number"
                              step="0.01"
                              className="input py-0.5 px-2 text-xs w-20 text-right"
                              value={r.opening_qty ?? ""}
                              onChange={(e) => {
                                const copy = [...stagedRows];
                                copy[idx] = { ...copy[idx], opening_qty: parseFloat(e.target.value) || 0 };
                                setStagedRows(copy);
                              }}
                            />
                          ) : (
                            r.opening_qty ?? "—"
                          )}
                        </td>
                        <td className="td text-right font-mono text-emerald-700 font-bold">
                          {editingStaged ? (
                            <input
                              type="number"
                              step="0.01"
                              className="input py-0.5 px-2 text-xs w-20 text-right"
                              value={r.received_qty ?? ""}
                              onChange={(e) => {
                                const copy = [...stagedRows];
                                copy[idx] = { ...copy[idx], received_qty: parseFloat(e.target.value) || 0 };
                                setStagedRows(copy);
                              }}
                            />
                          ) : (
                            r.received_qty ? `+${r.received_qty}` : "—"
                          )}
                        </td>
                        <td className="td text-right font-mono">
                          {editingStaged ? (
                            <input
                              type="number"
                              step="0.01"
                              className="input py-0.5 px-2 text-xs w-20 text-right"
                              value={r.closing_qty ?? ""}
                              onChange={(e) => {
                                const copy = [...stagedRows];
                                copy[idx] = { ...copy[idx], closing_qty: parseFloat(e.target.value) || 0 };
                                setStagedRows(copy);
                              }}
                            />
                          ) : (
                            r.closing_qty ?? "—"
                          )}
                        </td>
                        <td className="td text-xs text-content-secondary">
                          {r.supplier_name ? `${r.supplier_name} (#${r.invoice_no || ""})` : "—"}
                        </td>
                        <td className="td text-center">
                          <span className={`text-xs font-mono font-bold ${
                            (r.confidence || 0) >= 0.8 ? "text-emerald-600" : (r.confidence || 0) > 0 ? "text-amber-600" : "text-slate-400"
                          }`}>
                            {Math.round((r.confidence || 0) * 100)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Upload History */}
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
              <h3 className="text-sm font-bold text-content-primary">Recent Staged Documents</h3>
              <span className="text-xs text-content-muted num">{uploadsData.data?.length || 0} files</span>
            </div>
            <div className="divide-y divide-slate-100 text-sm">
              {(uploadsData.data || []).map((u: any) => (
                <div key={u.upload_id} className="p-4 flex items-center justify-between hover:bg-slate-50/80">
                  <div>
                    <div className="font-semibold text-content-primary">{u.filename}</div>
                    <div className="text-xs text-content-muted mt-0.5">
                      {u.workflow_type} · Uploaded {u.uploaded_at?.slice(0, 16)} by {u.uploaded_by}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge tone={u.status === "POSTED" ? "ok" : u.status === "NEEDS_REVIEW" ? "warn" : "muted"}>
                      {u.status}
                    </Badge>
                    <button
                      onClick={() => loadStaged(u.upload_id)}
                      className="btn-ghost btn-sm text-xs py-1 px-2.5"
                    >
                      View Draft
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ----------------- TAB 4: EVENING CLOSING RECONCILIATION ----------------- */}
      {tab === "closing" && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Evening Physical Closing Reconciliation</h2>
              <p className="text-xs text-content-muted mt-0.5">
                Depletion = Opening + Deliveries - Physical Closing. Posts single CONSUMPTION movement; unexplained depletion is flagged for Manager triage.
              </p>
            </div>
            <button
              onClick={saveClosing}
              disabled={submitting}
              className="btn-primary text-sm py-2 px-5"
            >
              {submitting ? "Reconciling…" : "Verify & Post Closing Stock"}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Ingredient</th>
                  <th className="th text-right" scope="col">Morning Opening</th>
                  <th className="th text-right" scope="col">Deliveries</th>
                  <th className="th text-right" scope="col">Total Available</th>
                  <th className="th text-right" scope="col">Physical Closing Count *</th>
                  <th className="th text-right" scope="col">Daily Depletion</th>
                  <th className="th text-center" scope="col">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(closingData.data?.rows || []).map((r: any) => {
                  const val = closingCounts[r.ingredient_id];
                  const cVal = val !== undefined && val !== "" ? Number(val) : r.available_qty;
                  const depletion = roundNum(r.available_qty - cVal);

                  return (
                    <tr key={r.ingredient_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="td font-medium text-content-primary">{r.name}</td>
                      <td className="td text-right font-mono text-content-secondary">
                        {fmt(r.opening_qty)} {r.unit}
                      </td>
                      <td className="td text-right font-mono text-emerald-700">
                        +{fmt(r.deliveries_qty)} {r.unit}
                      </td>
                      <td className="td text-right font-mono font-semibold text-content-primary">
                        {fmt(r.available_qty)} {r.unit}
                      </td>
                      <td className="td text-right">
                        <div className="flex items-center justify-end gap-2">
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            className="input py-1 px-2.5 font-mono text-sm max-w-[130px] text-right"
                            value={closingCounts[r.ingredient_id] ?? ""}
                            onChange={(e) =>
                              setClosingCounts({ ...closingCounts, [r.ingredient_id]: e.target.value })
                            }
                            placeholder="0.0"
                          />
                          <span className="text-xs text-content-muted">{r.unit}</span>
                        </div>
                      </td>
                      <td className="td text-right font-mono font-bold text-rose-600">
                        {depletion >= 0 ? `-${fmt(depletion)}` : `+${fmt(Math.abs(depletion))}`} {r.unit}
                      </td>
                      <td className="td text-center">
                        <Badge tone={r.closing_recorded ? "ok" : "muted"}>
                          {r.closing_recorded ? "POSTED" : "PENDING"}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ----------------- TAB 5: SUBMISSION HISTORY ----------------- */}
      {tab === "history" && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Historical Daily Stock Register</h2>
              <p className="text-xs text-content-muted mt-0.5">Authoritative audit ledger of all kitchen reconciliations</p>
            </div>
            <span className="text-xs text-content-muted num">{historyEntries.data?.length || 0} entries</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Date</th>
                  <th className="th" scope="col">Ingredient</th>
                  <th className="th text-right" scope="col">Opening</th>
                  <th className="th text-right" scope="col">Received</th>
                  <th className="th text-right" scope="col">Used (Depletion)</th>
                  <th className="th text-right" scope="col">Closing Stock</th>
                  <th className="th" scope="col">Recorded By</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(historyEntries.data || []).map((h: any) => (
                  <tr key={`${h.date}-${h.ingredient_id}`} className="hover:bg-slate-50/80 transition-colors">
                    <td className="td font-mono text-content-secondary">{h.date}</td>
                    <td className="td font-medium text-content-primary">{h.name}</td>
                    <td className="td text-right font-mono">{fmt(h.opening_stock)} {h.unit}</td>
                    <td className="td text-right font-mono text-emerald-700">+{fmt(h.received_qty || 0)} {h.unit}</td>
                    <td className="td text-right font-mono text-rose-600">-{fmt(h.used_qty || 0)} {h.unit}</td>
                    <td className="td text-right font-mono font-bold text-content-primary">{fmt(h.closing_stock)} {h.unit}</td>
                    <td className="td text-xs text-content-muted">{h.entered_by || "staff"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Page>
  );
}

function roundNum(val: number): number {
  return Math.round(val * 100) / 100;
}
