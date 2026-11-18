---
name: ui-ux-pro-max
description: Design intelligence, style presets, color systems, and UI guidelines for web applications. Use when designing, building, or refining UI components, dashboards, color tokens, and responsive layouts.
---

# UI/UX Pro Max

UI/UX Pro Max equips the assistant with design intelligence to prevent generic, templated UI generation. It provides structured guidance on design styles, curated palettes, font pairings, chart representations, and framework-specific patterns (React + Tailwind CSS).

## Workflow

1. **Query Local Design Intelligence**:
   When designing a new page, modal, or component, use the local search script to look up design tokens and recommended styles:
   ```bash
   python .agents/skills/ui-ux-pro-max/scripts/search.py "<query>" [--category <category>] [--limit <n>]
   ```
   Categories: `styles`, `palettes`, `typography`, `stack`, `components`.

2. **Establish Design Tokens**:
   - Primary surface and cards
   - Dominant and accent color scales
   - Typography hierarchy (headlines, body, tabular numbers)
   - Consistent padding, border radius, and elevation

3. **Implement with React & Tailwind**:
   - Reuse existing semantic UI primitives in `src/ui.tsx`.
   - Ensure all interactive elements have visible focus indicators (`focus-visible:ring-2`).
   - Use tabular numbers for financial or inventory figures (`tabular-nums`).
   - Implement empty states and error boundaries.

4. **References**:
   - Quick reference cheatsheet: [quick_reference.md](./references/quick_reference.md)
   - Full rule database: [design_rules.json](./data/design_rules.json)
