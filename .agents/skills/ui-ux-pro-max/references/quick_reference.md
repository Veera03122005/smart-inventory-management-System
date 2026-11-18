# UI/UX Pro Max Quick Reference

A structured cheatsheet of design principles, styles, tokens, and components for SmartStock AI.

## 1. Domain Target: Restaurant Inventory & Kitchen Operations
- **User Roles**: Staff (quick entry, high stress, physical movement), Manager (planning, charts, alerts), Owner (auditing, controls).
- **Core Workflow**: Scannable inventory tables, immediate warning visibility, easy barcode refill feedback, high-density live telemetry.

## 2. Core Tokens (Tailwind CSS)
- **Primary / Brand**: `emerald-600` (`#059669`), `hover:bg-emerald-700`, `focus-visible:ring-emerald-500`
- **Surface / Background**: `bg-slate-50 dark:bg-slate-900`
- **Cards**: `bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm`
- **Alert / Danger**: `rose-600` (`#e11d48`) with `bg-rose-50 text-rose-700 border-rose-200`
- **Caution / Warning**: `amber-500` (`#f59e0b`) with `bg-amber-50 text-amber-700 border-amber-200`
- **Info / IoT**: `sky-600` (`#0284c7`) with `bg-sky-50 text-sky-700 border-sky-200`

## 3. Component Patterns
- **KPI Metrics**: `text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white tabular-nums`
- **Status Badges**: `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium`
- **Buttons**:
  - Primary: `px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2`
  - Secondary: `px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors`
- **Tables**: `min-w-full divide-y divide-slate-200 dark:divide-slate-700 text-sm`
