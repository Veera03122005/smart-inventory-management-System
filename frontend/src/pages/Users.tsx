import { useState } from "react";
import { api } from "../api";
import { isManager, isOwner, useAuth } from "../auth";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

export default function Users() {
  const { user } = useAuth();
  const { data, reload } = useData(() => api("/users"));
  const [f, setF] = useState({ username: "", full_name: "", password: "", role: "staff" });
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const add = async () => {
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      await api("/users", { body: f });
      setOk(`New ${f.role} user '${f.username}' successfully created.`);
      setF({ username: "", full_name: "", password: "", role: "staff" });
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleStatus = async (targetUser: any) => {
    setErr("");
    setOk("");
    setTogglingId(targetUser.id);
    try {
      const res: any = await api(`/users/${targetUser.id}/toggle-status`, { method: "POST" });
      const statusLabel = res.is_active === 1 ? "reactivated" : "deactivated";
      setOk(`User '${targetUser.username}' has been ${statusLabel}.`);
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setTogglingId(null);
    }
  };

  const isMgr = isManager(user);

  return (
    <Page
      title={isMgr ? "Staff Account Management" : "User Management & Access Control"}
      sub={
        isMgr
          ? "Manager privileges. Provision, monitor and manage Kitchen Staff accounts."
          : "Owner privileges. Full team governance, role assignment, and access control."
      }
    >
      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left: Registered Users Table (3 Cols) */}
        <div className="card overflow-hidden flex flex-col lg:col-span-3">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">
                {isMgr ? "Kitchen Staff Team" : "Active Team Members"}
              </h2>
              <p className="text-xs text-content-muted mt-0.5">Role assignments, status & activity</p>
            </div>
            <span className="text-xs text-content-muted num">{data?.length || 0} users</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">User</th>
                  <th className="th text-center" scope="col">Role</th>
                  <th className="th text-center" scope="col">Status</th>
                  <th className="th text-right" scope="col">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(data || []).map((u: any) => {
                  const isActive = u.is_active !== 0;
                  const isSelf = u.username === user?.username;
                  const canManage = isMgr ? u.role === "staff" : !isSelf;

                  return (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="td">
                        <div className="font-mono font-medium text-content-primary">{u.username}</div>
                        <div className="text-xs text-content-muted">{u.full_name}</div>
                        {u.last_active && (
                          <div className="text-[11px] text-content-muted/80 mt-0.5">
                            Active: {u.last_active.slice(0, 16)} ({u.action_count || 0} events)
                          </div>
                        )}
                      </td>
                      <td className="td text-center">
                        <Badge
                          tone={u.role === "owner" ? "high" : u.role === "manager" ? "warn" : "ok"}
                          withDot={true}
                        >
                          {u.role.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="td text-center">
                        <Badge tone={isActive ? "ok" : "muted"}>
                          {isActive ? "ACTIVE" : "INACTIVE"}
                        </Badge>
                      </td>
                      <td className="td text-right">
                        {canManage ? (
                          <button
                            onClick={() => toggleStatus(u)}
                            disabled={togglingId === u.id}
                            className={`btn-sm text-xs font-semibold px-2.5 py-1 rounded-lg border transition-colors ${
                              isActive
                                ? "border-rose-200 text-rose-700 hover:bg-rose-50"
                                : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                            }`}
                          >
                            {togglingId === u.id
                              ? "Updating…"
                              : isActive
                              ? "Deactivate"
                              : "Reactivate"}
                          </button>
                        ) : isSelf ? (
                          <span className="text-xs text-content-muted italic">(Current account)</span>
                        ) : (
                          <span className="text-xs text-content-muted italic">Protected</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Create User Form (2 Cols) */}
        <div className="card p-6 flex flex-col justify-between lg:col-span-2">
          <div>
            <div className="pb-3 border-b border-surface-border mb-4">
              <h2 className="text-base font-bold text-content-primary">
                {isMgr ? "Provision Staff Account" : "Add New Team Member"}
              </h2>
              <p className="text-xs text-content-muted mt-0.5">
                {isMgr
                  ? "Create a dedicated staff account for kitchen stock registration"
                  : "Provision an account with designated role rights"}
              </p>
            </div>

            <div className="space-y-3.5">
              <div>
                <label htmlFor="user-username" className="label">
                  Username *
                </label>
                <input
                  id="user-username"
                  className="input font-mono"
                  value={f.username}
                  onChange={(e) => setF({ ...f, username: e.target.value })}
                  placeholder="e.g. chef_ravi"
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor="user-fullname" className="label">
                  Full Name *
                </label>
                <input
                  id="user-fullname"
                  className="input"
                  value={f.full_name}
                  onChange={(e) => setF({ ...f, full_name: e.target.value })}
                  placeholder="e.g. Ravi Kumar"
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor="user-password" className="label">
                  Password *
                </label>
                <input
                  id="user-password"
                  className="input"
                  type="password"
                  value={f.password}
                  onChange={(e) => setF({ ...f, password: e.target.value })}
                  placeholder="Minimum 6 characters"
                  aria-required="true"
                />
              </div>

              <div>
                <label htmlFor="user-role" className="label">
                  Permission Role *
                </label>
                <select
                  id="user-role"
                  className="input font-semibold"
                  value={f.role}
                  onChange={(e) => setF({ ...f, role: e.target.value })}
                  disabled={isMgr}
                >
                  <option value="staff">Staff (Stock Entry & IoT Scales)</option>
                  {!isMgr && <option value="manager">Manager (Forecasts, Sales & Reports)</option>}
                  {!isMgr && <option value="owner">Owner (Full Governance & Financials)</option>}
                </select>
                {isMgr && (
                  <p className="text-[11px] text-content-muted mt-1">
                    Managers can only provision Staff accounts.
                  </p>
                )}
              </div>
            </div>

            <div className="mt-4">
              <ErrorNote msg={err} onDismiss={() => setErr("")} />
              <OkNote msg={ok} onDismiss={() => setOk("")} />
            </div>
          </div>

          <div className="pt-4 border-t border-surface-border mt-4">
            <button
              className="btn-primary w-full py-2.5 text-base"
              onClick={add}
              disabled={submitting || !f.username || !f.password || !f.full_name}
            >
              {submitting ? "Creating User…" : isMgr ? "Create Staff Account" : "Create User Account"}
            </button>
          </div>
        </div>
      </div>
    </Page>
  );
}
