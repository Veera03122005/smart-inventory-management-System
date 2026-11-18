import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
import { ErrorNote } from "../ui";

const DEMO = [
  { role: "owner", pass: "owner123", desc: "Full Governance" },
  { role: "manager", pass: "manager123", desc: "Forecasts, IoT Sim, Alerts" },
  { role: "staff", pass: "staff123", desc: "Stock Sheet & Scales" },
];

export default function Login() {
  const { login } = useAuth();
  const [u, setU] = useState("owner");
  const [p, setP] = useState("owner123");
  const [showPass, setShowPass] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await login(u, p);
    } catch (x: any) {
      setErr(x.message || "Invalid username or password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-surface-canvas">
      {/* ----------------- Left Editorial Brand Panel ----------------- */}
      <div className="hidden lg:flex flex-col justify-between bg-ink text-white p-12 lg:p-16 border-r border-white/10 relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center font-bold text-white shadow-md text-xl">
            S
          </div>
          <div>
            <div className="text-xl font-bold tracking-tight">
              SmartStock <span className="text-spice">AI</span>
            </div>
            <div className="text-xs text-white/50 tracking-wider uppercase font-medium">
              Restaurant Kitchen Intelligence
            </div>
          </div>
        </div>

        <div className="my-auto py-12 max-w-lg">
          <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-white">
            Know what to prep, what to order, and what is about to expire.
          </h1>
          <p className="text-white/70 mt-5 text-base leading-relaxed">
            Real-time IoT load-cell telemetry and daily kitchen stock sheets feed one dual-channel ledger. Random Forest and XGBoost algorithms predict tomorrow's demand and protect your bottom line.
          </p>

          <div className="mt-8 grid grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10">
              <div className="font-bold text-emerald-400 text-sm">IoT Weighing Scales</div>
              <div className="text-white/60 mt-0.5">5-minute interval HX711 sensor telemetry</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white/5 border border-white/10">
              <div className="font-bold text-amber-400 text-sm">Dual ML Forecasting</div>
              <div className="text-white/60 mt-0.5">Automated champion model selection</div>
            </div>
          </div>
        </div>

        <div className="text-xs text-white/40 flex items-center justify-between border-t border-white/10 pt-4">
          <span>Kalasalingam Academy of Research and Education</span>
          <span>v1.0 Production</span>
        </div>
      </div>

      {/* ----------------- Right Sign-in Form ----------------- */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <form onSubmit={submit} className="w-full max-w-md space-y-5 card p-8 shadow-elevated">
          <div>
            <div className="lg:hidden flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center font-bold text-white">
                S
              </div>
              <span className="font-bold text-lg text-content-primary">SmartStock AI</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-content-primary">Sign in to your kitchen</h2>
            <p className="text-xs text-content-muted mt-1">Enter your credentials or click a demo account below</p>
          </div>

          <div>
            <label htmlFor="login-username" className="label">
              Username
            </label>
            <input
              id="login-username"
              className="input text-base"
              value={u}
              onChange={(e) => setU(e.target.value)}
              autoFocus
              aria-required="true"
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="login-password" className="label">
                Password
              </label>
              <button
                type="button"
                className="text-xs text-brand-700 hover:text-brand-800 font-medium mb-1"
                onClick={() => setShowPass(!showPass)}
              >
                {showPass ? "Hide" : "Show"}
              </button>
            </div>
            <div className="relative">
              <input
                id="login-password"
                className="input text-base pr-10"
                type={showPass ? "text" : "password"}
                value={p}
                onChange={(e) => setP(e.target.value)}
                aria-required="true"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-content-muted hover:text-content-primary"
                onClick={() => setShowPass(!showPass)}
                aria-label={showPass ? "Hide password" : "Show password"}
              >
                {showPass ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <ErrorNote msg={err} onDismiss={() => setErr("")} />

          <button
            type="submit"
            className="btn-primary w-full py-2.5 text-base font-semibold"
            disabled={busy || !u || !p}
          >
            {busy ? "Signing in…" : "Sign In to Kitchen"}
          </button>

          {/* Quick Demo Access - Click any to auto-fill username & password */}
          <div className="pt-4 border-t border-surface-border">
            <span className="label">1-Click Demo Accounts</span>
            <div className="grid grid-cols-3 gap-2 mt-2">
              {DEMO.map((d) => (
                <button
                  type="button"
                  key={d.role}
                  className={`btn-ghost text-xs py-2 px-1 flex flex-col items-center gap-0.5 transition-all ${
                    u === d.role ? "border-brand-500 bg-brand-50 text-brand-800 shadow-sm" : ""
                  }`}
                  onClick={() => {
                    setU(d.role);
                    setP(d.pass);
                    setErr("");
                  }}
                  title={`Log in as ${d.role} (password: ${d.pass})`}
                >
                  <span className="font-bold capitalize">{d.role}</span>
                  <span className="text-[10px] text-content-muted leading-tight text-center">{d.desc}</span>
                </button>
              ))}
            </div>
            <p className="text-[11px] text-content-muted text-center mt-2.5">
              Default password for all roles is <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-content-primary font-semibold">&lt;role&gt;123</code> (e.g. <strong className="text-content-primary">owner123</strong>)
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
