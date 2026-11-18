import { ReactNode, useEffect, useRef, useState } from "react";

export function Page({ title, sub, actions, children }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="p-6 lg:p-8 max-w-[1400px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {sub && <p className="text-sm text-ink-mute mt-1">{sub}</p>}
        </div>
        <div className="flex gap-2">{actions}</div>
      </div>
      {children}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "warn" | "bad" | "good" }) {
  const c = tone === "bad" ? "text-red-600" : tone === "warn" ? "text-spice" : tone === "good" ? "text-leaf" : "text-ink";
  return (
    <div className="card p-4">
      <div className="label">{label}</div>
      <div className={`text-2xl font-semibold num ${c}`}>{value}</div>
      {hint && <div className="text-xs text-ink-mute mt-1">{hint}</div>}
    </div>
  );
}

const tones: Record<string, string> = {
  high: "bg-red-50 text-red-700 border-red-200", medium: "bg-amber-50 text-amber-800 border-amber-200",
  low: "bg-slate-50 text-slate-600 border-slate-200", ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
};
export function Badge({ tone = "low", children }: { tone?: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone] || tones.low}`}>{children}</span>;
}

export function ErrorNote({ msg }: { msg: string }) {
  return msg ? <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm px-3 py-2">{msg}</div> : null;
}
export function OkNote({ msg }: { msg: string }) {
  return msg ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-800 text-sm px-3 py-2">{msg}</div> : null;
}
export function Loading() {
  return <div className="p-10 text-center text-ink-mute text-sm">Loading…</div>;
}

/** Fetch on mount and optionally poll. */
export function useData<T>(loader: () => Promise<T>, pollMs = 0, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const ref = useRef(loader);
  ref.current = loader;
  const reload = () => ref.current().then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => {
    reload();
    if (!pollMs) return;
    const t = setInterval(reload, pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, reload };
}
