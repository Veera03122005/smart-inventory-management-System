import { reportUrl } from "../api";
import { Page } from "../ui";

const REPORTS = [
  ["stock_summary", "Stock summary", "Current stock, days of cover and reorder point per ingredient."],
  ["forecast_reorder", "Forecast and reorder plan", "7-day forecast with range and today's order quantity."],
  ["model_evaluation", "Model evaluation", "MAE, RMSE and WAPE of all four models on the validation window."],
  ["wastage", "Wastage report", "Every wastage entry with reason and value in rupees."],
  ["manual_register", "Stock register export", "The complete manual stock sheet."],
  ["iot_daily_usage", "IoT daily usage", "Sensor-measured usage and refill count per day."],
  ["refill_sessions", "Refill sessions", "All barcode refill sessions with before and after weights."],
];

export default function Reports() {
  return (
    <Page title="Reports" sub="CSV downloads for managers and owners. They open in Excel.">
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map(([id, title, desc]) => (
          <div key={id} className="card p-4 flex flex-col">
            <div className="font-semibold">{title}</div>
            <div className="text-sm text-ink-mute mt-1 flex-1">{desc}</div>
            <a className="btn-ghost mt-4 self-start" href={reportUrl(id)}>Download CSV</a>
          </div>
        ))}
      </div>
    </Page>
  );
}
