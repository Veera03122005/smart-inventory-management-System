import { ReactNode, useEffect, useRef, useState } from "react";

// ------------------------------------------------------------------ Page Layout
export function Page({
  title,
  sub,
  actions,
  children,
}: {
  title: string;
  sub?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-[1440px] mx-auto animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6 pb-2 border-b border-surface-border/60">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-content-primary">{title}</h1>
          {sub && <p className="text-sm text-content-muted mt-1 leading-relaxed">{sub}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

// ------------------------------------------------------------------ Metric KPI Card
export function Stat({
  label,
  value,
  hint,
  tone,
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "warn" | "bad" | "good" | "info";
  icon?: ReactNode;
}) {
  const toneClasses = {
    bad: "text-rose-600 dark:text-rose-400",
    warn: "text-amber-600 dark:text-amber-400",
    good: "text-brand-700 dark:text-brand-400",
    info: "text-sky-600 dark:text-sky-400",
  };
  const valColor = tone ? toneClasses[tone] : "text-content-primary";

  return (
    <div className="card p-4 sm:p-5 card-hover relative overflow-hidden">
      <div className="flex items-start justify-between gap-2">
        <div className="label">{label}</div>
        {icon && <div className="text-content-subtle">{icon}</div>}
      </div>
      <div className={`text-2xl sm:text-3xl font-bold num tracking-tight mt-1 ${valColor}`}>
        {value}
      </div>
      {hint && (
        <div className="text-xs text-content-muted mt-1.5 flex items-center gap-1.5 font-normal">
          {hint}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Badges
const tones: Record<string, { badge: string; dot: string }> = {
  high: { badge: "bg-rose-50 text-rose-700 border-rose-200", dot: "bg-rose-500" },
  danger: { badge: "bg-rose-50 text-rose-700 border-rose-200", dot: "bg-rose-500" },
  medium: { badge: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  warn: { badge: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  low: { badge: "bg-slate-100 text-slate-700 border-slate-200", dot: "bg-slate-400" },
  ok: { badge: "bg-emerald-50 text-emerald-800 border-emerald-200", dot: "bg-emerald-500" },
  good: { badge: "bg-emerald-50 text-emerald-800 border-emerald-200", dot: "bg-emerald-500" },
  info: { badge: "bg-sky-50 text-sky-700 border-sky-200", dot: "bg-sky-500" },
};

export function Badge({
  tone = "low",
  withDot = false,
  children,
}: {
  tone?: string;
  withDot?: boolean;
  children: ReactNode;
}) {
  const current = tones[tone] || tones.low;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold select-none ${current.badge}`}>
      {withDot && <span className={`h-1.5 w-1.5 rounded-full ${current.dot}`} />}
      {children}
    </span>
  );
}

// ------------------------------------------------------------------ Live Beacon / Status Dot
export function LivePulse({ active = true, label }: { active?: boolean; label?: string }) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className="relative flex h-2.5 w-2.5">
        {active && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
        )}
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${active ? "bg-emerald-500" : "bg-slate-400"}`} />
      </span>
      {label && <span className="text-xs font-medium text-content-secondary">{label}</span>}
    </div>
  );
}

// ------------------------------------------------------------------ Notifications / Alerts
export function ErrorNote({ msg, onDismiss }: { msg: string; onDismiss?: () => void }) {
  if (!msg) return null;
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 text-rose-800 text-sm px-4 py-3 flex items-start justify-between gap-3 shadow-sm my-2" role="alert">
      <div className="flex items-start gap-2.5">
        <svg className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        <span className="font-medium">{msg}</span>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss error" className="text-rose-600 hover:text-rose-800 text-lg leading-none p-0.5">
          &times;
        </button>
      )}
    </div>
  );
}

export function OkNote({ msg, onDismiss }: { msg: string; onDismiss?: () => void }) {
  if (!msg) return null;
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-800 text-sm px-4 py-3 flex items-start justify-between gap-3 shadow-sm my-2" role="status">
      <div className="flex items-start gap-2.5">
        <svg className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
        <span className="font-medium">{msg}</span>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss success message" className="text-emerald-600 hover:text-emerald-800 text-lg leading-none p-0.5">
          &times;
        </button>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Skeletons & Loading
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-slate-200/80 ${className}`} aria-hidden="true" />;
}

export function SkeletonCard() {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-8 w-36" />
      <Skeleton className="h-3 w-48" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="p-4 border-b border-surface-border">
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="divide-y divide-slate-100">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="p-4 flex gap-4">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function Loading({ label = "Loading data…" }: { label?: string }) {
  return (
    <div className="p-12 text-center flex flex-col items-center justify-center gap-3" role="status">
      <svg className="animate-spin h-6 w-6 text-brand-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
      <div className="text-sm font-medium text-content-muted">{label}</div>
    </div>
  );
}

// ------------------------------------------------------------------ Empty State
export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="p-8 text-center flex flex-col items-center justify-center border border-dashed border-slate-300 rounded-xl bg-surface-muted/30 my-4">
      {icon ? (
        <div className="text-content-subtle mb-3">{icon}</div>
      ) : (
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
      )}
      <h3 className="text-base font-semibold text-content-primary">{title}</h3>
      <p className="text-sm text-content-muted max-w-sm mt-1 mb-4">{description}</p>
      {action}
    </div>
  );
}

// ------------------------------------------------------------------ Confirmation Dialog
export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  confirmTone = "danger",
  onConfirm,
  onCancel,
}: {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  confirmTone?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    // Auto-focus cancel button on modal open
    setTimeout(() => cancelBtnRef.current?.focus(), 50);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="card w-full max-w-md p-6 shadow-elevated animate-scale-up">
        <h3 id="modal-title" className="text-lg font-bold text-content-primary">
          {title}
        </h3>
        <p className="text-sm text-content-muted mt-2 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button ref={cancelBtnRef} className="btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={confirmTone === "danger" ? "btn-danger" : "btn-primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Data Loading Hook
export function useData<T>(loader: () => Promise<T>, pollMs = 0, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const ref = useRef(loader);
  ref.current = loader;

  const reload = () => {
    return ref.current()
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    reload();
    if (!pollMs) return;
    const t = setInterval(reload, pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload };
}
