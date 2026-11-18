import { useState } from "react";
import { api } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

export default function Users() {
  const { data, reload } = useData(() => api("/users"));
  const [f, setF] = useState({ username: "", full_name: "", password: "", role: "staff" });
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const add = async () => {
    setErr("");
    setOk("");
    setSubmitting(true);
    try {
      await api("/users", { body: f });
      setOk(`New user '${f.username}' successfully created.`);
      setF({ username: "", full_name: "", password: "", role: "staff" });
      reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Page
      title="User Management & Access Control"
      sub="Owner privileges. Staff record operational data; managers review AI forecasts & reports; owners govern user access."
    >
      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left: Registered Users Table (3 Cols) */}
        <div className="card overflow-hidden flex flex-col lg:col-span-3">
          <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between bg-surface-canvas/50">
            <div>
              <h2 className="text-base font-bold text-content-primary">Active Team Members</h2>
              <p className="text-xs text-content-muted mt-0.5">Role assignments and permissions</p>
            </div>
            <span className="text-xs text-content-muted num">{data?.length || 0} users</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table">
              <thead>
                <tr className="bg-slate-50/70">
                  <th className="th" scope="col">Username</th>
                  <th className="th" scope="col">Full Name</th>
                  <th className="th text-center" scope="col">Assigned Role</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(data || []).map((u: any) => (
                  <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="td font-mono font-medium text-content-primary">{u.username}</td>
                    <td className="td text-content-secondary">{u.full_name}</td>
                    <td className="td text-center">
                      <Badge
                        tone={u.role === "owner" ? "high" : u.role === "manager" ? "warn" : "ok"}
                        withDot={true}
                      >
                        {u.role.toUpperCase()}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Create User Form (2 Cols) */}
        <div className="card p-6 flex flex-col justify-between lg:col-span-2">
          <div>
            <div className="pb-3 border-b border-surface-border mb-4">
              <h2 className="text-base font-bold text-content-primary">Add New Team Member</h2>
              <p className="text-xs text-content-muted mt-0.5">Provision an account with designated role rights</p>
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
                >
                  <option value="staff">Staff (Stock Entry & IoT Scales)</option>
                  <option value="manager">Manager (Forecasts, Simulator & Reports)</option>
                  <option value="owner">Owner (Full Governance + Users)</option>
                </select>
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
              {submitting ? "Creating User…" : "Create User Account"}
            </button>
          </div>
        </div>
      </div>
    </Page>
  );
}
