import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { useAuth } from "../auth";
import { Badge, ConfirmModal, ErrorNote, LivePulse, Loading, Page, Skeleton, useData } from "../ui";

function DeviceChart({ deviceId }: { deviceId: string }) {
  const { data, loading } = useData(() => api(`/iot/readings?device_id=${deviceId}&limit=240`), 2000, [deviceId]);

  if (loading || !data) {
    return (
      <div className="h-40 flex items-center justify-center bg-surface-muted/40 rounded-lg my-2">
        <Skeleton className="h-32 w-full mx-4" />
      </div>
    );
  }

  const rows = data.readings
    .filter((r: any) => r.stable || r.event_type !== "READING")
    .map((r: any) => ({
      t: r.ts.slice(11, 16),
      w: r.weight_kg,
      e: r.event_type,
    }));

  return (
    <div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ left: -20, right: 10, top: 10, bottom: 0 }}>
            <CartesianGrid stroke="#f1f5f9" strokeDasharray="2 2" vertical={false} />
            <XAxis dataKey="t" tick={{ fontSize: 10, fill: "#64748b" }} minTickGap={35} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 16]} tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(v: any) => [`${v} kg`, "Bin Weight"]}
              labelFormatter={(l) => `Time: ${l}`}
              contentStyle={{
                backgroundColor: "rgba(255, 255, 255, 0.95)",
                borderRadius: "0.5rem",
                border: "1px solid #e2e8f0",
                fontSize: "0.75rem",
                boxShadow: "0 2px 4px rgba(0,0,0,0.06)",
              }}
            />
            <Line
              dataKey="w"
              name="Weight"
              stroke="#0284c7"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            {rows.map((r: any, i: number) =>
              r.e === "REFILL_END" ? (
                <ReferenceDot key={i} x={r.t} y={r.w} r={4.5} fill="#10b981" stroke="#ffffff" strokeWidth={1.5} />
              ) : null
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[11px] text-content-muted mt-1.5 flex items-center justify-between">
        <span>{data.mode === "live" ? "Live stream (5m resolution)" : `Recorded for ${data.day}`}</span>
        <span className="flex items-center gap-1 font-medium text-emerald-700">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
          Barcode Refills
        </span>
      </div>
    </div>
  );
}

export default function LiveIoT() {
  const { user } = useAuth();
  const dev = useData(() => api("/iot/devices"), 2000);
  const sim = useData(() => api("/iot/simulator"), 2000);
  const daily = useData(() => api("/iot/daily"));
  const [speed, setSpeed] = useState("2");
  const [err, setErr] = useState("");
  const [spillTarget, setSpillTarget] = useState<string | null>(null);

  const canControl = user?.role !== "staff";

  const act = (a: string, body: any = {}) =>
    api(`/iot/simulator/${a}`, { body })
      .then(() => {
        sim.reload();
        setErr("");
      })
      .catch((e) => setErr(e.message));

  if (!dev.data) return <Loading label="Connecting to IoT load cells…" />;

  const last7 = (id: string) =>
    (daily.data || []).filter((d: any) => d.ingredient_id === id).slice(-7);

  return (
    <Page
      title="Live IoT Weighing Bins"
      sub="Load cell + HX711 + ESP32 real-time telemetry. Ingested via hardware REST API with barcode tare reconciliation."
      actions={
        canControl && (
          <div className="flex items-center gap-2.5">
            <label htmlFor="sim-speed" className="sr-only">Simulation Interval</label>
            <select
              id="sim-speed"
              className="input w-40 text-xs py-1.5"
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
              disabled={sim.data?.running}
              aria-label="Simulator speed interval"
            >
              <option value="2">1 reading / 2 s</option>
              <option value="1">1 reading / 1 s</option>
              <option value="0.5">2 readings / 1 s</option>
            </select>
            {sim.data?.running ? (
              <button
                className="btn-ghost text-xs py-1.5 border-rose-200 text-rose-700 hover:bg-rose-50"
                onClick={() => act("stop")}
              >
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse mr-1" />
                Stop Simulator
              </button>
            ) : (
              <button
                className="btn-primary text-xs py-1.5"
                onClick={() => act("start", { interval: Number(speed) })}
              >
                Start Simulator
              </button>
            )}
          </div>
        )
      }
    >
      <ErrorNote msg={err} onDismiss={() => setErr("")} />

      {sim.data?.running && (
        <div className="mb-5 p-3 rounded-xl bg-sky-50 border border-sky-200 text-xs text-sky-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LivePulse active={true} />
            <span className="font-semibold">Hardware Simulator Active:</span>
            <span>Kitchen clock is currently {sim.data.kitchen_time}. Each reading represents one 5-minute interval.</span>
          </div>
          <span className="text-[11px] font-mono text-sky-700 uppercase tracking-wider font-semibold">ESP32 Sim</span>
        </div>
      )}

      {/* ----------------- Scale Devices Grid ----------------- */}
      <div className="grid lg:grid-cols-3 gap-6">
        {dev.data.map((d: any) => {
          const isLow = d.weight_kg < 3.0;
          const capacityPercent = Math.min(100, (d.weight_kg / d.capacity_kg) * 100);

          return (
            <div key={d.device_id} className="card p-5 flex flex-col justify-between card-hover">
              <div>
                <div className="flex items-start justify-between pb-3 border-b border-surface-border">
                  <div>
                    <div className="text-base font-bold text-content-primary">{d.name}</div>
                    <div className="text-xs text-content-muted font-mono">{d.device_id}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {d.open_session && (
                      <Badge tone="warn" withDot={true}>Refill Open</Badge>
                    )}
                    <Badge tone={d.online ? "ok" : "low"} withDot={true}>
                      {d.online ? "Online" : "Idle"}
                    </Badge>
                  </div>
                </div>

                {/* Main Weight Hero */}
                <div className="mt-4 flex items-baseline justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-content-muted">Current Weight</div>
                    <div className={`text-4xl font-extrabold num tracking-tight mt-0.5 ${isLow ? "text-rose-600" : "text-content-primary"}`}>
                      {fmt(d.weight_kg, 2)} <span className="text-sm font-medium text-content-muted">kg</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-content-muted">Bin Capacity</div>
                    <div className="text-sm font-semibold num text-content-secondary">{d.capacity_kg} kg</div>
                  </div>
                </div>

                {/* Capacity Fill Gauge */}
                <div
                  className="h-2.5 rounded-full bg-slate-100 overflow-hidden mt-3 mb-4 border border-slate-200/60"
                  role="progressbar"
                  aria-valuenow={Math.round(d.weight_kg * 10) / 10}
                  aria-valuemin={0}
                  aria-valuemax={d.capacity_kg}
                  aria-label={`${d.name} fill level`}
                >
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isLow ? "bg-rose-500" : "bg-emerald-500"
                    }`}
                    style={{ width: `${capacityPercent}%` }}
                  />
                </div>

                {/* Time-Series Chart */}
                <DeviceChart deviceId={d.device_id} />
              </div>

              <div>
                {/* Simulator Action: Spill */}
                {canControl && sim.data?.running && (
                  <button
                    className="btn-ghost w-full mt-4 text-xs py-2 border-amber-200 text-amber-800 hover:bg-amber-50"
                    onClick={() => setSpillTarget(d.device_id)}
                  >
                    Simulate a 2 kg Spill Anomaly
                  </button>
                )}

                {/* 7-Day History Table */}
                <div className="mt-5 pt-4 border-t border-surface-border">
                  <div className="label">Sensor-Measured Consumption (Last 7 Days)</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <tbody>
                        {last7(d.ingredient_id).map((x: any) => (
                          <tr key={x.date} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                            <td className="py-1.5 font-medium text-content-secondary">{x.date}</td>
                            <td className="py-1.5 text-right num font-semibold text-content-primary">
                              {fmt(x.usage)} {d.unit}
                            </td>
                            <td className="py-1.5 text-right text-content-muted">
                              {x.refills} refill{x.refills !== 1 ? "s" : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ----------------- Confirm Spill Modal ----------------- */}
      <ConfirmModal
        isOpen={spillTarget !== null}
        title="Simulate Spill Anomaly"
        message={`This will trigger an abrupt 2.0 kg loss on scale unit ${spillTarget}. The anomaly engine will immediately fire a 'Sudden weight drop' kitchen alert.`}
        confirmLabel="Simulate Spill"
        confirmTone="danger"
        onConfirm={() => {
          if (spillTarget) {
            act("spill", { device_id: spillTarget });
            setSpillTarget(null);
          }
        }}
        onCancel={() => setSpillTarget(null)}
      />
    </Page>
  );
}
