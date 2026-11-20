import { useState } from "react";
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
import DepletionInvestigation from "./pages/DepletionInvestigation";

interface NavItem {
  to: string;
  label: string;
  roles: Role[];
  icon: (active: boolean) => JSX.Element;
}

const NAV: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    roles: ["owner", "manager", "staff"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    to: "/live",
    label: "Live IoT",
    roles: ["owner", "manager", "staff"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
      </svg>
    ),
  },
  {
    to: "/refill",
    label: "Barcode Refill",
    roles: ["owner", "manager", "staff"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
      </svg>
    ),
  },
  {
    to: "/stock-sheet",
    label: "Stock Sheet",
    roles: ["owner", "manager", "staff"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    to: "/investigations",
    label: "Depletion Investigation",
    roles: ["owner", "manager"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
      </svg>
    ),
  },
  {
    to: "/forecast",
    label: "AI Forecast",
    roles: ["owner", "manager"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  },
  {
    to: "/alerts",
    label: "Alerts",
    roles: ["owner", "manager", "staff"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
  {
    to: "/reports",
    label: "Reports",
    roles: ["owner", "manager"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    to: "/users",
    label: "Users & Roles",
    roles: ["owner", "manager"],
    icon: (a) => (
      <svg className={`w-5 h-5 shrink-0 ${a ? "text-emerald-400" : "text-white/60"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    ),
  },
];

export default function App() {
  const { user, loading, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (loading) return <Loading label="Initializing SmartStock AI…" />;
  if (!user) return <Routes><Route path="*" element={<Login />} /></Routes>;

  const allowed = NAV.filter((n) => n.roles.includes(user.role));
  const can = (path: string) => allowed.some((n) => n.to === path);

  return (
    <div className="min-h-screen lg:flex bg-surface-canvas text-content-primary">
      {/* ----------------- Top Mobile Header (<1024px) ----------------- */}
      <header className="lg:hidden sticky top-0 z-40 bg-ink text-white px-4 py-3 flex items-center justify-between border-b border-white/10 shadow-md">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center font-bold text-white shadow-sm">
            S
          </div>
          <div>
            <div className="text-base font-bold tracking-tight leading-tight">
              SmartStock <span className="text-spice">AI</span>
            </div>
            <div className="text-[10px] text-white/50 tracking-wide uppercase">Kitchen Intelligence</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white/10 text-white/90 capitalize">
            {user.role}
          </span>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            className="p-2 rounded-lg bg-white/10 text-white hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            {mobileOpen ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* ----------------- Mobile Drawer Backdrop ----------------- */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ----------------- Desktop Sidebar & Mobile Drawer ----------------- */}
      <aside
        className={`fixed lg:sticky top-0 z-50 lg:z-30 lg:top-0 h-screen bg-ink text-white lg:w-64 w-72 flex flex-col justify-between border-r border-white/10 transition-transform duration-300 ease-in-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div>
          {/* Brand header */}
          <div className="p-6 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center font-bold text-white shadow-md text-lg">
                S
              </div>
              <div>
                <div className="text-lg font-bold tracking-tight">
                  SmartStock <span className="text-spice">AI</span>
                </div>
                <div className="text-[11px] text-white/50 tracking-wider uppercase font-medium">
                  Kitchen Operations
                </div>
              </div>
            </div>
            {mobileOpen && (
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="lg:hidden p-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1 overflow-y-auto max-h-[calc(100vh-210px)]" aria-label="Main Navigation">
            {allowed.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                    isActive
                      ? "bg-white/15 text-white font-semibold shadow-inner border border-white/10"
                      : "text-white/75 hover:bg-white/10 hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {n.icon(isActive)}
                    <span>{n.to === "/users" && user.role === "manager" ? "Staff Accounts" : n.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* User Card & Sign Out */}
        <div className="p-4 border-t border-white/10 bg-black/20">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-white truncate">{user.full_name}</div>
              <div className="text-xs text-white/50 capitalize flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                {user.role} role
              </div>
            </div>
            <button
              onClick={logout}
              className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              title="Sign out"
              aria-label="Sign out"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ----------------- Main Content Area ----------------- */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<LiveIoT />} />
          <Route path="/refill" element={<Refill />} />
          <Route path="/stock-sheet" element={<StockSheet />} />
          <Route path="/alerts" element={<Alerts />} />
          {can("/investigations") && <Route path="/investigations" element={<DepletionInvestigation />} />}
          {can("/forecast") && <Route path="/forecast" element={<Forecast />} />}
          {can("/reports") && <Route path="/reports" element={<Reports />} />}
          {can("/users") && <Route path="/users" element={<Users />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
