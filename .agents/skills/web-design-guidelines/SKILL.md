---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
---

# Web Interface Guidelines & Audit Skill

Review code files and UI components for compliance with modern Web Interface Guidelines, UX quality, and accessibility standards.

## How It Works

1. Read the specified source files (e.g. React components in `src/pages/` or `src/ui.tsx`).
2. Compare the implementation against the bundled checklist in [guidelines.md](./references/guidelines.md).
3. Check for accessibility, interactive states, responsive behavior, keyboard navigation, and anti-patterns.
4. Output findings using the terse `file:line` format for direct navigation:

```text
src/pages/Dashboard.tsx:42 Icon-only refresh button missing aria-label
src/pages/StockSheet.tsx:88 Input field missing htmlFor connection to label
src/pages/LiveIoT.tsx:115 transition-all used; change to transition-colors or transition-transform
```

## Audit Categories

Refer to [guidelines.md](./references/guidelines.md) for full rule definitions:
- **Layout & Visual Polish**: Optical alignment, safe areas, responsive behavior.
- **Content Handling**: Text truncation with `min-w-0`, empty states, tabular numerals.
- **Forms & Inputs**: Labels, autocomplete, hit targets, loading states, paste preservation.
- **Navigation & Links**: Semantic routing, state preservation, destructive action confirmation.
- **Performance**: Minimizing re-renders, preventing layout shifts (CLS), list performance.
- **Anti-Patterns**: Banned patterns including `outline-none` without `focus-visible`, missing labels, and non-semantic buttons.
