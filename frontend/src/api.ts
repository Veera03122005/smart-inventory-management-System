const KEY = "smartstock_token";

export const getToken = () => localStorage.getItem(KEY) || "";
export const setToken = (t: string) => localStorage.setItem(KEY, t);
export const clearToken = () => localStorage.removeItem(KEY);

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch("/api" + path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + getToken() },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/auth/login") {
    clearToken();
    window.location.href = "/login";
  }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data as T;
}

/** Secure Blob-based CSV report download that sends the JWT via Authorization header */
export async function downloadReport(name: string) {
  const res = await fetch(`/api/reports/${name}.csv`, {
    headers: { Authorization: "Bearer " + getToken() },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `Download failed (${res.status})` }));
    throw new Error(err.error || `Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// Backward-compatible fallback
export const reportUrl = (name: string) => `/api/reports/${name}.csv?token=${encodeURIComponent(getToken())}`;

export const fmt = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: 0 });

export const rupees = (v: number) => "₹" + Math.round(v).toLocaleString("en-IN");

export const shortDate = (s: string) => new Date(s + (s.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
