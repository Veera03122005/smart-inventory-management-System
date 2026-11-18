import { useState } from "react";
import { api } from "../api";
import { Badge, ErrorNote, OkNote, Page, useData } from "../ui";

export default function Users() {
  const { data, reload } = useData(() => api("/users"));
  const [f, setF] = useState({ username: "", full_name: "", password: "", role: "staff" });
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const add = async () => {
    setErr(""); setOk("");
    try { await api("/users", { body: f }); setOk(`User ${f.username} created.`); setF({ username: "", full_name: "", password: "", role: "staff" }); reload(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <Page title="Users and roles" sub="Owner only. Staff record data, managers see forecasts and reports, owners also manage users.">
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="th">Username</th><th className="th">Name</th><th className="th">Role</th></tr></thead>
            <tbody>{(data || []).map((u: any) => <tr key={u.id}><td className="td font-medium">{u.username}</td><td className="td">{u.full_name}</td><td className="td"><Badge tone={u.role === "owner" ? "high" : u.role === "manager" ? "medium" : "low"}>{u.role}</Badge></td></tr>)}</tbody>
          </table>
        </div>
        <div className="card p-5 space-y-3">
          <div className="font-semibold">Add a user</div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Username</label><input className="input" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></div>
            <div><label className="label">Full name</label><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>
            <div><label className="label">Password</label><input className="input" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
            <div><label className="label">Role</label><select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="staff">Staff</option><option value="manager">Manager</option><option value="owner">Owner</option></select></div>
          </div>
          <ErrorNote msg={err} /><OkNote msg={ok} />
          <button className="btn-primary" onClick={add}>Create user</button>
        </div>
      </div>
    </Page>
  );
}
