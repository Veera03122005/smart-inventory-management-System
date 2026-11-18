import { useState } from "react";
import { downloadReport } from "../api";
import { ErrorNote, Page } from "../ui";

const REPORTS = [
  {
    id: "stock_summary",
    title: "Stock Balance Summary",
    desc: "Current on-hand inventory levels, calculated days of stock cover, and dynamic reorder points for every ingredient.",
  },
  {
    id: "forecast_reorder",
    title: "Forecast & Replenishment Plan",
    desc: "Next 7-day demand projections with high/low confidence boundaries and recommended purchase order quantities.",
  },
  {
    id: "model_evaluation",
    title: "ML Model Benchmarks",
    desc: "MAE, RMSE, and WAPE evaluation metrics across all four forecasting models (Random Forest, XGBoost, Naive, Moving Average).",
  },
  {
    id: "wastage",
    title: "Kitchen Wastage & Spoilage Log",
    desc: "Comprehensive log of expired, spilled, burnt, and rejected kitchen stock with calculated rupee cost valuations.",
  },
  {
    id: "manual_register",
    title: "Master Stock Sheet Register",
    desc: "Full historical daily stock sheet ledger export including opening stocks, received shipments, and usage logs.",
  },
  {
    id: "iot_daily_usage",
    title: "IoT Sensor Daily Consumption",
    desc: "Aggregated daily consumption measurements from load-cell units with tare-reconciled refill session counters.",
  },
  {
    id: "refill_sessions",
    title: "Barcode Refill Sessions",
    desc: "Complete audit log of all barcode-initiated scale replenishment events with before and after tare measurements.",
  },
];

export default function Reports() {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [err, setErr] = useState("");

  const handleDownload = async (id: string) => {
    setDownloading(id);
    setErr("");
    try {
      await downloadReport(id);
    } catch (e: any) {
      setErr(e.message || "Failed to download report");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Page
      title="Operational Reports & Auditing"
      sub="Download raw operational data in CSV format for executive analysis in Excel, Google Sheets, or business intelligence tools."
    >
      <ErrorNote msg={err} onDismiss={() => setErr("")} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {REPORTS.map((r) => {
          const isBusy = downloading === r.id;
          return (
            <div key={r.id} className="card p-5 flex flex-col justify-between card-hover">
              <div>
                <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center mb-3">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h2 className="text-base font-bold text-content-primary">{r.title}</h2>
                <p className="text-xs text-content-muted mt-1 leading-relaxed">{r.desc}</p>
              </div>

              <div className="pt-5 mt-4 border-t border-surface-border">
                <button
                  type="button"
                  className="btn-ghost btn-sm w-full text-center"
                  onClick={() => handleDownload(r.id)}
                  disabled={isBusy}
                  aria-label={`Download ${r.title} as CSV`}
                >
                  {isBusy ? (
                    <>
                      <svg className="animate-spin h-3.5 w-3.5 mr-1.5 text-content-secondary" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Downloading…
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 mr-1.5 text-content-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Download CSV Export
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </Page>
  );
}
