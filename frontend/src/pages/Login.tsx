import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
import { ErrorNote } from "../ui";

const DEMO = [["owner", "owner123"], ["manager", "manager123"], ["staff", "staff123"]];

export default function Login() {
  const { login } = useAuth();
  const [u, setU] = useState("manager");
  const [p, setP] = useState("manager123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await login(u, p); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-ink text-white p-12">
        <div className="text-xl font-semibold">SmartStock <span className="text-spice">AI</span></div>
        <div>
          <h1 className="text-4xl font-semibold leading-tight max-w-md">Know what to cook, what to order and what is about to expire.</h1>
          <p className="text-white/60 mt-4 max-w-md">Load-cell readings and the daily stock sheet feed one ledger. Machine learning turns it into tomorrow's plan.</p>
        </div>
        <div className="text-xs text-white/40">Kalasalingam Academy of Research and Education</div>
      </div>
      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4">
          <h2 className="text-2xl font-semibold">Sign in</h2>
          <div><label className="label">Username</label><input className="input" value={u} onChange={(e) => setU(e.target.value)} autoFocus /></div>
          <div><label className="label">Password</label><input className="input" type="password" value={p} onChange={(e) => setP(e.target.value)} /></div>
          <ErrorNote msg={err} />
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <div className="pt-2">
            <div className="label">Demo accounts</div>
            <div className="flex gap-2">
              {DEMO.map(([a, b]) => (
                <button type="button" key={a} className="btn-ghost flex-1 capitalize" onClick={() => { setU(a); setP(b); }}>{a}</button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
