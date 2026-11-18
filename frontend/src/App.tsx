import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Role, useAuth } from "./auth";
import { Loading } from "./ui";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import LiveIoT from "./pages/LiveIoT";
import Refill from "./pages/Refill";
import StockSheet from "./pages/StockSheet";
import Forecast from "./pages/Forecast";
import Alerts from "./pages/Alerts";
import Reports from "./pages/Reports";
import Users from "./pages/Users";

const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: "/", label: "Dashboard", roles: ["owner", "manager", "staff"] },
  { to: "/live", label: "Live IoT", roles: ["owner", "manager", "staff"] },
  { to: "/refill", label: "Barcode refill", roles: ["owner", "manager", "staff"] },
  { to: "/stock-sheet", label: "Stock sheet", roles: ["owner", "manager", "staff"] },
  { to: "/forecast", label: "AI forecast", roles: ["owner", "manager"] },
  { to: "/alerts", label: "Alerts", roles: ["owner", "manager", "staff"] },
  { to: "/reports", label: "Reports", roles: ["owner", "manager"] },
  { to: "/users", label: "Users", roles: ["owner"] },
];

export default function App() {
  const { user, loading, logout } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;
  const allowed = NAV.filter((n) => n.roles.includes(user.role));
  const can = (path: string) => allowed.some((n) => n.to === path);
  return (
    <div className="min-h-screen lg:flex">
      <aside className="bg-ink text-white lg:w-60 lg:min-h-screen lg:sticky lg:top-0 lg:h-screen flex lg:flex-col">
        <div className="px-5 py-5 hidden lg:block">
          <div className="text-lg font-semibold tracking-tight">SmartStock <span className="text-spice">AI</span></div>
          <div className="text-xs text-white/50 mt-0.5">Kitchen inventory intelligence</div>
        </div>
        <nav className="flex lg:flex-col gap-1 px-3 py-2 overflow-x-auto flex-1">
          {allowed.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-2 text-sm ${isActive ? "bg-white/10 text-white font-medium" : "text-white/70 hover:bg-white/5"}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-white/10 hidden lg:block">
          <div className="text-sm">{user.full_name}</div>
          <div className="text-xs text-white/50 capitalize mb-2">{user.role}</div>
          <button onClick={logout} className="text-xs text-white/70 hover:text-white underline">Sign out</button>
        </div>
        <button onClick={logout} className="lg:hidden px-4 text-xs text-white/70">Sign out</button>
      </aside>
      <main className="flex-1 min-w-0">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<LiveIoT />} />
          <Route path="/refill" element={<Refill />} />
          <Route path="/stock-sheet" element={<StockSheet />} />
          <Route path="/alerts" element={<Alerts />} />
          {can("/forecast") && <Route path="/forecast" element={<Forecast />} />}
          {can("/reports") && <Route path="/reports" element={<Reports />} />}
          {can("/users") && <Route path="/users" element={<Users />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
