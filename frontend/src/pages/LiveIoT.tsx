import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "../api";
import { useAuth } from "../auth";
import { Badge, ErrorNote, Loading, Page, useData } from "../ui";

function DeviceChart({ deviceId }: { deviceId: string }) {
  const { data } = useData(() => api(`/iot/readings?device_id=${deviceId}&limit=240`), 2000, [deviceId]);
  if (!data) return <div className="h-40" />;
  const rows = data.readings.filter((r: any) => r.stable || r.event_type !== "READING").map((r: any) => ({ t: r.ts.slice(11, 16), w: r.weight_kg, e: r.event_type }));
  return (
    <div>
      <div className="h-40">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ left: -15, right: 8, top: 8 }}>
            <CartesianGrid stroke="#e4e3df" vertical={false} />
            <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={40} />
            <YAxis domain={[0, 16]} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v: any) => `${v} kg`} />
            <Line dataKey="w" name="Weight" stroke="#2a78d6" strokeWidth={2} dot={false} isAnimationActive={false} />
            {rows.map((r: any, i: number) => r.e === "REFILL_END" ? <ReferenceDot key={i} x={r.t} y={r.w} r={4} fill="#1baf7a" stroke="#fff" /> : null)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[11px] text-ink-mute mt-1">{data.mode === "live" ? "Live readings" : `Recorded readings for ${data.day}`} · green dots are barcode refills</div>
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
  const canControl = user?.role !== "staff";
  const act = (a: string, body: any = {}) => api(`/iot/simulator/${a}`, { body }).then(() => { sim.reload(); setErr(""); }).catch((e) => setErr(e.message));
  if (!dev.data) return <Loading />;
  const last7 = (id: string) => (daily.data || []).filter((d: any) => d.ingredient_id === id).slice(-7);
  return (
    <Page title="Live IoT" sub="Load cell + HX711 + ESP32 weighing units. The simulator sends readings through the same API the real device uses."
      actions={canControl && (
        <>
          <select className="input w-40" value={speed} onChange={(e) => setSpeed(e.target.value)} disabled={sim.data?.running}>
            <option value="2">1 reading / 2 s</option><option value="1">1 reading / s</option><option value="0.5">2 readings / s</option>
          </select>
          {sim.data?.running
            ? <button className="btn-ghost" onClick={() => act("stop")}>Stop simulator</button>
            : <button className="btn-primary" onClick={() => act("start", { interval: Number(speed) })}>Start simulator</button>}
        </>
      )}>
      <ErrorNote msg={err} />
      {sim.data?.running && <div className="text-sm text-ink-mute mb-4">Simulator running · kitchen clock {sim.data.kitchen_time} · each reading is one 5-minute slot</div>}
      <div className="grid lg:grid-cols-3 gap-6">
        {dev.data.map((d: any) => (
          <div key={d.device_id} className="card p-4">
            <div className="flex items-start justify-between">
              <div><div className="font-semibold">{d.name}</div><div className="text-xs text-ink-mute">{d.device_id}</div></div>
              <div className="flex gap-1">{d.open_session && <Badge tone="medium">Refill open</Badge>}<Badge tone={d.online ? "ok" : "low"}>{d.online ? "Online" : "Idle"}</Badge></div>
            </div>
            <div className="mt-3 flex items-end gap-2">
              <div className={`text-4xl font-semibold num ${d.weight_kg < 3 ? "text-red-600" : ""}`}>{fmt(d.weight_kg, 2)}</div>
              <div className="text-sm text-ink-mute mb-1">kg in bin</div>
            </div>
            <div className="h-2 rounded bg-black/10 overflow-hidden mt-2 mb-3"><div className={`h-full ${d.weight_kg < 3 ? "bg-red-500" : "bg-leaf"}`} style={{ width: `${Math.min(100, (d.weight_kg / d.capacity_kg) * 100)}%` }} /></div>
            <DeviceChart deviceId={d.device_id} />
            {canControl && sim.data?.running && <button className="btn-ghost mt-3 text-xs" onClick={() => act("spill", { device_id: d.device_id })}>Simulate a 2 kg spill</button>}
            <div className="mt-4">
              <div className="label">Sensor-measured usage, last 7 recorded days</div>
              <table className="w-full"><tbody>
                {last7(d.ingredient_id).map((x: any) => (
                  <tr key={x.date}><td className="td py-1 text-xs">{x.date}</td><td className="td py-1 text-xs text-right num">{fmt(x.usage)} {d.unit}</td><td className="td py-1 text-xs text-right text-ink-mute">{x.refills} refills</td></tr>
                ))}
              </tbody></table>
            </div>
          </div>
        ))}
      </div>
    </Page>
  );
}
