import { useState, useEffect } from "react";
import { api, fmt, rupees } from "../api";
import { useAuth } from "../auth";
import { Badge, Loading, OkNote, ErrorNote } from "../ui";

interface DepletionSummary {
  unclassified_count: number;
  awaiting_investigation_qty: number;
  total_unclassified_kg_by_ingredient: {
    ingredient_id: string;
    ingredient_name: string;
    unit: string;
    unclassified_kg: number;
    record_count: number;
  }[];
  classified_by_category: Record<string, number>;
  classified_category_counts: Record<string, number>;
  historical_investigation_records: number;
  investigating_count: number;
  classified_records_count: number;
  resolved_records_count: number;
  active_classifications_count: number;
  total_estimated_wastage_rs?: number;
}

interface DepletionItem {
  depletion_id: string;
  date: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  opening_qty: number;
  deliveries_qty: number;
  closing_qty: number;
  calculated_depletion_kg: number;
  classified_qty: number;
  remaining_unclassified_qty: number;
  unexplained_depletion_kg: number;
  status: "UNCLASSIFIED" | "INVESTIGATING" | "INVESTIGATED" | "CLASSIFIED" | "RESOLVED";
  notes?: string;
  resolution_notes?: string;
  unit_cost_rs?: number | null;
  estimated_loss_rs?: number | null;
}

interface DepletionDetail extends DepletionItem {
  opening_count?: {
    physical_qty: number;
    entered_by: string;
    verified_by?: string;
    notes?: string;
  } | null;
  closing_count?: {
    physical_qty: number;
    entered_by: string;
    verified_by?: string;
    notes?: string;
  } | null;
  deliveries?: {
    item_id: string;
    invoice_no: string;
    supplier_name: string;
    billed_qty: number;
    inventory_qty?: number;
    batch_no?: string;
    expiry_date?: string;
    unit_price_rs?: number | null;
  }[];
  classifications: {
    classification_id: string;
    category: string;
    classified_qty: number;
    unit: string;
    notes?: string;
    classified_by: string;
    classified_at: string;
    status: "ACTIVE" | "REVERSED";
    reversal_reason?: string;
    cost_rs?: number | null;
  }[];
  investigation_notes: {
    note_id: string;
    author: string;
    note: string;
    created_at: string;
  }[];
}

const CATEGORIES = [
  { value: "SPOILAGE", label: "Spoilage", desc: "Perished or spoiled ingredients", badgeColor: "bg-red-500/10 text-red-400 border-red-500/20" },
  { value: "EXPIRED", label: "Expired", desc: "Past batch expiry date", badgeColor: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
  { value: "PREPARATION_LOSS", label: "Preparation Loss", desc: "Trimming, peeling, burning in cooking", badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  { value: "SPILLAGE", label: "Spillage", desc: "Accidental drop or spill on floor", badgeColor: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" },
  { value: "DAMAGE", label: "Damage", desc: "Crushed or container broken during handling", badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/20" },
  { value: "THEFT", label: "Theft / Suspected Removal", desc: "Unauthorized removal or unaccounted shortage", badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/20", notesRequired: true },
  { value: "MEASUREMENT_ERROR", label: "Measurement / Counting Error", desc: "Scale miscalibration or human miscount", badgeColor: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
  { value: "NORMAL_CONSUMPTION", label: "Normal Operational Consumption", desc: "Legitimate kitchen culinary usage", badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  { value: "OTHER_UNEXPLAINED", label: "Other / Unexplained", desc: "Unresolved variance requiring investigation notes", badgeColor: "bg-gray-500/10 text-gray-400 border-gray-500/20", notesRequired: true },
];

export default function DepletionInvestigation() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<DepletionSummary | null>(null);
  const [depletions, setDepletions] = useState<DepletionItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DepletionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filters
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [unclassifiedOnly, setUnclassifiedOnly] = useState(false);

  // Classification Form
  const [catCategory, setCatCategory] = useState("SPOILAGE");
  const [catQty, setCatQty] = useState<string>("");
  const [catNotes, setCatNotes] = useState("");
  const [submittingCls, setSubmittingCls] = useState(false);
  const [clsError, setClsError] = useState("");
  const [clsSuccess, setClsSuccess] = useState("");

  // Reversal Form
  const [reversingId, setReversingId] = useState<string | null>(null);
  const [reversalReason, setReversalReason] = useState("");
  const [reversingSubmitting, setReversingSubmitting] = useState(false);

  // New Note Form
  const [newNote, setNewNote] = useState("");
  const [submittingNote, setSubmittingNote] = useState(false);

  // Resolution Form
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  const fetchDashboardAndList = async () => {
    try {
      setLoading(true);
      const dash = await api<DepletionSummary>("/manager/depletions");
      setSummary(dash);

      let q = "/manager/depletions/list?";
      const params = new URLSearchParams();
      if (filterDate) params.append("date", filterDate);
      if (filterStatus) params.append("status", filterStatus);
      if (unclassifiedOnly) params.append("unclassified_only", "true");
      q += params.toString();

      const listRes = await api<{ depletions: DepletionItem[] }>(q);
      setDepletions(listRes.depletions || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardAndList();
  }, [filterDate, filterStatus, unclassifiedOnly]);

  const openDetail = async (id: string) => {
    setSelectedId(id);
    setDetailLoading(true);
    setClsError("");
    setClsSuccess("");
    try {
      const res = await api<DepletionDetail>(`/manager/depletions/${id}`);
      setDetail(res);
      setCatQty(res.remaining_unclassified_qty > 0 ? String(res.remaining_unclassified_qty) : "");
    } catch (err: any) {
      setClsError(err.message || "Failed to load details");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleClassify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    setClsError("");
    setClsSuccess("");

    const q = parseFloat(catQty);
    if (isNaN(q) || q <= 0) {
      setClsError("Please enter a valid positive quantity to classify.");
      return;
    }
    const catDef = CATEGORIES.find((c) => c.value === catCategory);
    if (catDef?.notesRequired && (!catNotes || catNotes.trim().length < 5)) {
      setClsError(`Mandatory explanatory notes (at least 5 characters) are required for ${catDef.label}.`);
      return;
    }

    try {
      setSubmittingCls(true);
      await api(`/manager/depletions/${detail.depletion_id}/classify`, {
        body: {
          category: catCategory,
          classified_qty: q,
          notes: catNotes.trim(),
        },
      });
      setClsSuccess(`Successfully classified ${q} kg under ${catCategory}. (Zero-Sum Δ=0)`);
      setCatNotes("");
      await openDetail(detail.depletion_id);
      fetchDashboardAndList();
    } catch (err: any) {
      setClsError(err.message || "Classification failed");
    } finally {
      setSubmittingCls(false);
    }
  };

  const handleReverse = async (classificationId: string) => {
    if (!reversalReason || reversalReason.trim().length < 3) {
      alert("A clear reason (at least 3 characters) is required for reversal.");
      return;
    }
    try {
      setReversingSubmitting(true);
      await api(`/manager/depletions/classifications/${classificationId}/reverse`, {
        body: { reason: reversalReason.trim() },
      });
      setReversingId(null);
      setReversalReason("");
      if (selectedId) await openDetail(selectedId);
      fetchDashboardAndList();
    } catch (err: any) {
      alert(err.message || "Reversal failed");
    } finally {
      setReversingSubmitting(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail || !newNote.trim()) return;
    try {
      setSubmittingNote(true);
      await api(`/manager/depletions/${detail.depletion_id}/notes`, {
        body: { note: newNote.trim() },
      });
      setNewNote("");
      await openDetail(detail.depletion_id);
      fetchDashboardAndList();
    } catch (err: any) {
      alert(err.message || "Failed to add note");
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleResolve = async () => {
    if (!detail) return;
    if (detail.remaining_unclassified_qty > 0 && (!resolutionNotes || resolutionNotes.trim().length < 3)) {
      alert("Please provide resolution notes explaining why this investigation is closed with unresolved variance.");
      return;
    }
    try {
      setResolving(true);
      await api(`/manager/depletions/${detail.depletion_id}/resolve`, {
        body: { resolution_notes: resolutionNotes.trim() },
      });
      setResolutionNotes("");
      await openDetail(detail.depletion_id);
      fetchDashboardAndList();
    } catch (err: any) {
      alert(err.message || "Failed to resolve investigation");
    } finally {
      setResolving(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "UNCLASSIFIED":
        return <Badge tone="warn" withDot>UNCLASSIFIED</Badge>;
      case "INVESTIGATING":
        return <Badge tone="info" withDot>INVESTIGATING</Badge>;
      case "CLASSIFIED":
        return <Badge tone="good" withDot>CLASSIFIED</Badge>;
      case "RESOLVED":
        return <Badge tone="low">RESOLVED</Badge>;
      default:
        return <Badge tone="low">{status}</Badge>;
    }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-[1440px] mx-auto space-y-6">
      {/* Title & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/10">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>Depletion Investigation</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-mono font-medium">
              Zero-Sum Reclassification (Δ=0)
            </span>
          </h1>
          <p className="text-sm text-white/60 mt-1">
            Authoritative manager triage for kitchen depletion. Closing reconciliation posted the physical stock deduction; classification attributes causes without double-deduction.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardAndList}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl text-sm font-medium bg-white/10 hover:bg-white/15 text-white transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* SECTION A: INVESTIGATION DASHBOARD */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 sm:p-5">
            <div className="text-xs font-semibold text-white/50 uppercase tracking-wider">Awaiting Investigation</div>
            <div className="text-2xl sm:text-3xl font-bold text-amber-400 mt-1 font-mono">
              {summary.unclassified_count} records
            </div>
            <div className="text-xs text-white/60 mt-1">
              Total {fmt(summary.awaiting_investigation_qty)} kg unexplained
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 sm:p-5">
            <div className="text-xs font-semibold text-white/50 uppercase tracking-wider">Active Investigations</div>
            <div className="text-2xl sm:text-3xl font-bold text-sky-400 mt-1 font-mono">
              {summary.investigating_count} in-progress
            </div>
            <div className="text-xs text-white/60 mt-1">Partially classified depletion</div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 sm:p-5">
            <div className="text-xs font-semibold text-white/50 uppercase tracking-wider">Fully Classified</div>
            <div className="text-2xl sm:text-3xl font-bold text-emerald-400 mt-1 font-mono">
              {summary.classified_records_count} resolved
            </div>
            <div className="text-xs text-white/60 mt-1">{summary.active_classifications_count} verified loss events</div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 sm:p-5">
            <div className="text-xs font-semibold text-white/50 uppercase tracking-wider">
              {user?.role === "owner" ? "Estimated Financial Loss" : "Unresolved Variances"}
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-white mt-1 font-mono">
              {user?.role === "owner" ? rupees(summary.total_estimated_wastage_rs || 0) : `${summary.resolved_records_count} closed`}
            </div>
            <div className="text-xs text-white/60 mt-1">
              {user?.role === "owner" ? "Owner financial valuation" : "Closed with remaining variance"}
            </div>
          </div>
        </div>
      )}

      {/* SECTION B: INVESTIGATION LIST WITH FILTERS */}
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">Daily Depletion Logs</h2>
            <span className="text-xs text-white/40">({depletions.length} records)</span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input
              type="date"
              value={filterDate}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFilterDate(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-white/15 bg-white/5 text-xs text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-emerald-400"
            />
            <select
              value={filterStatus}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-white/15 bg-black/40 text-xs text-white focus:outline-none focus:ring-1 focus:ring-emerald-400"
            >
              <option value="">All Statuses</option>
              <option value="UNCLASSIFIED">Unclassified</option>
              <option value="INVESTIGATING">Investigating</option>
              <option value="CLASSIFIED">Classified</option>
              <option value="RESOLVED">Resolved</option>
            </select>
            <label className="flex items-center gap-2 text-xs text-white/70 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={unclassifiedOnly}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUnclassifiedOnly(e.target.checked)}
                className="rounded border-white/20 bg-white/5 text-emerald-500 focus:ring-emerald-400"
              />
              <span>Unclassified Only</span>
            </label>
            {(filterDate || filterStatus || unclassifiedOnly) && (
              <button
                onClick={() => {
                  setFilterDate("");
                  setFilterStatus("");
                  setUnclassifiedOnly(false);
                }}
                className="px-2.5 py-1 text-xs text-white/60 hover:text-white hover:bg-white/10 rounded-lg"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="py-12 flex justify-center">
            <Loading label="Loading depletion records..." />
          </div>
        ) : depletions.length === 0 ? (
          <div className="py-12 text-center text-white/50 text-sm">
            No depletion records match the current filters.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full text-left text-sm text-white/80">
              <thead className="bg-white/5 text-xs uppercase text-white/50 font-semibold border-b border-white/10">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Ingredient</th>
                  <th className="px-4 py-3 text-right">Opening</th>
                  <th className="px-4 py-3 text-right">Deliveries</th>
                  <th className="px-4 py-3 text-right">Closing</th>
                  <th className="px-4 py-3 text-right">Depletion</th>
                  <th className="px-4 py-3 text-right">Classified</th>
                  <th className="px-4 py-3 text-right">Remaining</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono text-xs">
                {depletions.map((d) => (
                  <tr
                    key={d.depletion_id}
                    className={`hover:bg-white/[0.04] transition-colors ${
                      selectedId === d.depletion_id ? "bg-white/[0.08]" : ""
                    }`}
                  >
                    <td className="px-4 py-3 text-white font-sans">{d.date}</td>
                    <td className="px-4 py-3 font-sans font-medium text-white">
                      {d.ingredient_name}
                      <span className="text-white/40 text-[10px] ml-1.5 font-mono">({d.unit})</span>
                    </td>
                    <td className="px-4 py-3 text-right text-white/70">{fmt(d.opening_qty)}</td>
                    <td className="px-4 py-3 text-right text-white/70">+{fmt(d.deliveries_qty)}</td>
                    <td className="px-4 py-3 text-right text-white/70">{fmt(d.closing_qty)}</td>
                    <td className="px-4 py-3 text-right font-bold text-white">{fmt(d.calculated_depletion_kg)}</td>
                    <td className="px-4 py-3 text-right text-emerald-400 font-semibold">{fmt(d.classified_qty)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-amber-400">
                      {fmt(d.remaining_unclassified_qty)}
                    </td>
                    <td className="px-4 py-3 font-sans">{getStatusBadge(d.status)}</td>
                    <td className="px-4 py-3 text-center font-sans">
                      <button
                        onClick={() => openDetail(d.depletion_id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          selectedId === d.depletion_id
                            ? "bg-emerald-500 text-white"
                            : "bg-white/10 hover:bg-white/15 text-white"
                        }`}
                      >
                        {d.remaining_unclassified_qty > 0 ? "Investigate" : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SECTION C: INVESTIGATION DETAILS & CLASSIFICATION DRAWER/MODAL */}
      {selectedId && (
        <div className="rounded-2xl border border-emerald-500/30 bg-black/40 p-6 space-y-6 shadow-2xl relative" id="investigation-details-section">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-white">
                  Investigation: {detail?.ingredient_name || "Loading..."}
                </h3>
                {detail && getStatusBadge(detail.status)}
              </div>
              <div className="text-xs text-white/50 mt-1">
                Record ID: <span className="font-mono">{selectedId}</span> • Date: {detail?.date}
              </div>
            </div>
            <button
              onClick={() => setSelectedId(null)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 hover:bg-white/15 text-white transition-colors"
            >
              Close Panel
            </button>
          </div>

          {detailLoading ? (
            <div className="py-12 flex justify-center">
              <Loading label="Loading investigation details..." />
            </div>
          ) : detail ? (
            <div className="space-y-6">
              {/* Quantities Overview Ribbon */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-black/30 border border-white/10 text-center">
                <div>
                  <div className="text-xs text-white/40">Total Depletion</div>
                  <div className="text-lg font-bold text-white font-mono mt-0.5">
                    {fmt(detail.calculated_depletion_kg)} {detail.unit}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-white/40">Already Classified</div>
                  <div className="text-lg font-bold text-emerald-400 font-mono mt-0.5">
                    {fmt(detail.classified_qty)} {detail.unit}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-white/40">Remaining Unclassified</div>
                  <div className="text-lg font-bold text-amber-400 font-mono mt-0.5">
                    {fmt(detail.remaining_unclassified_qty)} {detail.unit}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-white/40">Reconciliation Action</div>
                  <div className="text-xs font-mono text-emerald-400/90 mt-1">
                    Zero-Sum Δ=0.0
                  </div>
                </div>
              </div>

              {/* Related Counts & Deliveries */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-white/50">Morning Opening</div>
                  {detail.opening_count ? (
                    <div className="text-sm">
                      <div className="font-bold text-white text-base font-mono">
                        {fmt(detail.opening_count.physical_qty)} {detail.unit}
                      </div>
                      <div className="text-xs text-white/50 mt-1">
                        Recorded by: {detail.opening_count.entered_by}
                      </div>
                      {detail.opening_count.notes && (
                        <div className="text-xs text-white/40 italic mt-0.5">"{detail.opening_count.notes}"</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-rose-400">Missing opening stock count!</div>
                  )}
                </div>

                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-white/50">Day Deliveries</div>
                  <div className="font-bold text-white text-base font-mono">
                    +{fmt(detail.deliveries_qty)} {detail.unit}
                  </div>
                  {detail.deliveries && detail.deliveries.length > 0 ? (
                    <div className="space-y-1 text-xs text-white/60 mt-1 max-h-24 overflow-y-auto">
                      {detail.deliveries.map((dl) => (
                        <div key={dl.item_id} className="truncate">
                          • {dl.supplier_name} ({dl.invoice_no}): {fmt(dl.billed_qty)} {detail.unit}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-white/40">No deliveries on this date.</div>
                  )}
                </div>

                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-white/50">Evening Closing</div>
                  {detail.closing_count ? (
                    <div className="text-sm">
                      <div className="font-bold text-white text-base font-mono">
                        {fmt(detail.closing_count.physical_qty)} {detail.unit}
                      </div>
                      <div className="text-xs text-white/50 mt-1">
                        Recorded by: {detail.closing_count.entered_by}
                      </div>
                      {detail.closing_count.notes && (
                        <div className="text-xs text-white/40 italic mt-0.5">"{detail.closing_count.notes}"</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-rose-400">Missing closing stock count!</div>
                  )}
                </div>
              </div>

              {/* SECTION: CLASSIFICATION AUDIT JOURNAL */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold uppercase tracking-wider text-white/70">
                    Classification History ({detail.classifications.length})
                  </h4>
                </div>

                {detail.classifications.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-white/10 text-center text-xs text-white/40">
                    No classification events recorded yet for this depletion.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {detail.classifications.map((c) => (
                      <div
                        key={c.classification_id}
                        className={`p-3.5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          c.status === "ACTIVE"
                            ? "bg-white/[0.04] border-white/10"
                            : "bg-rose-500/5 border-rose-500/20 opacity-60"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs px-2 py-0.5 rounded font-medium border ${
                                CATEGORIES.find((cat) => cat.value === c.category)?.badgeColor || "bg-white/10 text-white"
                              }`}
                            >
                              {c.category}
                            </span>
                            <span className="font-mono font-bold text-white text-sm">
                              {fmt(c.classified_qty)} {c.unit}
                            </span>
                            {c.status === "REVERSED" && (
                              <Badge tone="danger">REVERSED</Badge>
                            )}
                          </div>
                          {c.notes && <div className="text-xs text-white/70">"{c.notes}"</div>}
                          <div className="text-[11px] text-white/40">
                            Classified by {c.classified_by} at {c.classified_at}
                            {c.reversal_reason && ` • Reversal Reason: "${c.reversal_reason}"`}
                          </div>
                        </div>

                        {c.status === "ACTIVE" && (
                          <div>
                            {reversingId === c.classification_id ? (
                              <div className="flex items-center gap-2">
                                <input
                                  placeholder="Reversal reason..."
                                  value={reversalReason}
                                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setReversalReason(e.target.value)}
                                  className="px-2.5 py-1 text-xs rounded-lg border border-white/20 bg-black/40 text-white placeholder-white/40 w-48 focus:outline-none"
                                />
                                <button
                                  disabled={reversingSubmitting}
                                  onClick={() => handleReverse(c.classification_id)}
                                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-500 text-white transition-colors"
                                >
                                  Confirm
                                </button>
                                <button
                                  onClick={() => setReversingId(null)}
                                  className="px-2.5 py-1 text-xs rounded-lg text-white/60 hover:text-white"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => {
                                  setReversingId(c.classification_id);
                                  setReversalReason("");
                                }}
                                className="px-2.5 py-1 text-xs rounded-lg border border-white/15 text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                              >
                                Reverse
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* SECTION: CLASSIFY REMAINING QUANTITY FORM */}
              {detail.remaining_unclassified_qty > 0 && detail.calculated_depletion_kg > 0 ? (
                <div className="rounded-2xl bg-emerald-950/20 border border-emerald-500/30 p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-base font-bold text-white flex items-center gap-2">
                        <span>Classify Depletion</span>
                        <span className="text-xs text-emerald-400 font-normal">
                          (Eligible: {fmt(detail.remaining_unclassified_qty)} {detail.unit})
                        </span>
                      </h4>
                      <p className="text-xs text-white/60 mt-0.5">
                        Assign quantity into a loss category. This is an authoritative audit reclassification (Zero-Sum Δ=0).
                      </p>
                    </div>
                  </div>

                  {clsError && <ErrorNote msg={clsError} onDismiss={() => setClsError("")} />}
                  {clsSuccess && <OkNote msg={clsSuccess} onDismiss={() => setClsSuccess("")} />}

                  <form onSubmit={handleClassify} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-white/70 mb-1">Loss Category</label>
                        <select
                          value={catCategory}
                          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCatCategory(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl border border-white/20 bg-black/60 text-sm text-white focus:outline-none focus:ring-1 focus:ring-emerald-400"
                        >
                          {CATEGORIES.map((c) => (
                            <option key={c.value} value={c.value}>
                              {c.label} {c.notesRequired ? "(Notes required)" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-white/70 mb-1">
                          Quantity to Classify ({detail.unit})
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max={detail.remaining_unclassified_qty}
                          value={catQty}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCatQty(e.target.value)}
                          placeholder={`Max ${detail.remaining_unclassified_qty}`}
                          className="w-full px-3 py-2 rounded-xl border border-white/20 bg-black/60 text-sm text-white focus:outline-none focus:ring-1 focus:ring-emerald-400 font-mono"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-white/70 mb-1">
                        Investigation Notes {CATEGORIES.find((c) => c.value === catCategory)?.notesRequired ? "(Mandatory)" : "(Optional)"}
                      </label>
                      <input
                        value={catNotes}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCatNotes(e.target.value)}
                        placeholder="Explain root cause (e.g. walk-in temperature spike, kitchen drop, prep waste)"
                        className="w-full px-3 py-2 rounded-xl border border-white/20 bg-black/60 text-sm text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                      />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-2">
                      <button
                        type="submit"
                        disabled={submittingCls}
                        className="px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50"
                      >
                        {submittingCls ? "Posting Classification..." : "Post Classification (Zero-Sum Δ=0)"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : detail.remaining_unclassified_qty <= 0 ? (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center text-sm text-emerald-400 font-semibold">
                  ✓ 100% of this depletion has been accounted for and classified.
                </div>
              ) : null}

              {/* SECTION: INVESTIGATION NOTES & RESOLVE UNEXPLAINED */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                {/* Notes List & Add Note */}
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-white/70">
                    Manager Investigation Notes ({detail.investigation_notes.length})
                  </h4>

                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {detail.investigation_notes.length === 0 ? (
                      <div className="text-xs text-white/40 italic">No notes logged yet.</div>
                    ) : (
                      detail.investigation_notes.map((n) => (
                        <div key={n.note_id} className="p-2.5 rounded-lg bg-black/20 text-xs space-y-1">
                          <div className="text-white/80">{n.note}</div>
                          <div className="text-[10px] text-white/40">
                            {n.author} • {n.created_at}
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <form onSubmit={handleAddNote} className="flex gap-2 pt-1">
                    <input
                      placeholder="Add investigation observation..."
                      value={newNote}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewNote(e.target.value)}
                      className="flex-1 px-3 py-1.5 rounded-lg border border-white/15 bg-black/40 text-xs text-white placeholder-white/40 focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={submittingNote || !newNote.trim()}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/15 hover:bg-white/20 text-white transition-colors disabled:opacity-40"
                    >
                      Add
                    </button>
                  </form>
                </div>

                {/* Explicit Resolution Action */}
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-white/70">
                    Investigation Resolution
                  </h4>
                  <p className="text-xs text-white/60">
                    If investigation is complete or root cause cannot be determined, explicitly close the record. Remaining variance is retained as unresolved unexplained depletion.
                  </p>

                  <div className="space-y-2">
                    <input
                      placeholder="Resolution summary / notes..."
                      value={resolutionNotes}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setResolutionNotes(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg border border-white/15 bg-black/40 text-xs text-white placeholder-white/40 focus:outline-none"
                    />
                    <div className="flex justify-end">
                      <button
                        onClick={handleResolve}
                        disabled={resolving || (detail.remaining_unclassified_qty > 0 && !resolutionNotes.trim())}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-white/10 hover:bg-white/20 text-white transition-colors disabled:opacity-40"
                      >
                        {resolving ? "Resolving..." : "Mark Investigation Closed"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
