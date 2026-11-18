# Web Interface Guidelines & Audit Rules

This document provides a comprehensive checklist and audit guide for web application interfaces, accessibility, performance, and interaction design.

---

## 1. Layout & Visual Polish

- **Deliberate Alignment**: Every element must intentionally align to a grid, baseline, edge, or optical center. Avoid accidental positioning or floating elements.
- **Optical Balance**: When mathematical centers look off-center to human eyes (e.g. play icons in circle buttons), adjust positioning by ±1px for optical balance.
- **Contrast & Lockups**: When icons and text appear together, ensure balanced visual weight. Thin-stroke icons next to bold text feel weak; adjust icon stroke or size accordingly.
- **Responsive Coverage**: Test screens across mobile (<640px), tablet (640-1024px), laptop (1024-1440px), and desktop/widescreen displays (>1440px).
- **Safe Areas & Insets**: Account for mobile status bars, home indicators, and browser chrome using safe-area environment variables (`env(safe-area-inset-top)`, etc.).
- **Overscroll Behavior**: Avoid accidental horizontal body scrolling. Handle page-level or panel-level bounce with `overscroll-behavior-y: contain` where applicable.

---

## 2. Content Handling & Typography

- **Text Truncation**: Any container rendering variable or user-provided text must handle overflow gracefully using `truncate`, `line-clamp-*`, or `break-words`.
- **Flexbox Safety**: Inside flex containers, flex child items require `min-w-0` to allow child text elements to truncate properly without blowing out parent widths.
- **Empty States**: Never render empty containers, broken tables, or blank gaps when data is missing. Provide explicit, informative empty states with clear calls to action.
- **Tabular Numbers**: Any numbers displayed in comparison lists, tables, counters, prices, or countdown timers should use tabular numerals (`tabular-nums` / `font-variant-numeric: tabular-nums`) to prevent jitter and maintain vertical alignment.
- **Typographic Characters**: Use proper typographical symbols: true ellipses (`…`), curly quotes/apostrophes, and em/en dashes where appropriate. Avoid widow words on headlines.

---

## 3. Forms & Controls

- **Semantic Inputs**: Form controls must use accurate semantic types (`type="email"`, `type="tel"`, `type="number"`, `type="search"`, `type="url"`) and appropriate `inputmode`.
- **Labels & Hit Targets**: Form inputs must have explicitly associated `<label>` elements via `htmlFor` matching input `id`, or by wrapping the input. Checkboxes and radio buttons must share a unified clickable hit target with their label text (minimum 44×44px hit area on mobile).
- **Never Block Paste**: Never intercept and block user paste events (`onPaste` with `preventDefault()`) on text, password, or code inputs.
- **Spellcheck Disabling**: Disable spellcheck (`spellCheck={false}`) and autocorrect on fields expecting codes, usernames, emails, serial numbers, or barcodes.
- **Submission States**: 
  - Submit buttons must stay enabled while filling the form, disabling or switching to a loading spinner only *after* submission begins.
  - Display inline error messages adjacent to the invalid input and autofocus the first invalid control upon failed submission.
- **Placeholder Text**: Placeholder text should describe example input rather than replacing real labels, and should conclude with an ellipsis (`…`).

---

## 4. Navigation & State

- **Semantic Links**: Navigation between views or external links must use native `<a>` tags or router `<Link>` components rather than `<div onClick>` or `<button onClick>`, ensuring middle-click and Cmd/Ctrl+click work naturally.
- **URL Synchronization**: Key interface states (filters, search queries, active tabs, pagination) should synchronize with URL query parameters for bookmarkability and shareability.
- **Destructive Actions**: Destructive actions (deletions, resetting data, discarding entries) must require explicit confirmation or support a clear undo window. Never execute destructive operations on a single unconfirmed click.

---

## 5. Performance & React Execution

- **Re-render Optimization**: Avoid unnecessary re-renders in parent tables and dashboard cards when child inputs or live streams update.
- **List Virtualization**: Render large datasets (more than 50-100 items) using virtualization or pagination to maintain a 60fps frame rate.
- **Cumulative Layout Shift (CLS)**: Always specify `width` and `height` or aspect-ratio on images, icons, and placeholder skeletons to prevent layout jumping while assets load.

---

## 6. Critical Anti-Patterns (Automatic Audit Flags)

Flag the following items immediately during reviews:
1. `user-scalable=no` or `maximum-scale=1` in viewport meta (blocks user zoom accessibility).
2. `onPaste` combined with `preventDefault` (breaks password managers and clipboard flows).
3. Universal transition classes like `transition: all` or `transition-all` (causes performance stutters; specify exact properties like `transition-colors`, `transition-opacity`).
4. `outline-none` without an explicit replacement `focus-visible:` ring or border.
5. `<div>` or `<span>` elements acting as buttons or links without `role`, `tabIndex`, or keyboard support.
6. Icon-only buttons lacking an `aria-label` or `title` screen-reader attribute.
7. Hardcoded date/currency formatting instead of localized `Intl.DateTimeFormat` / `Intl.NumberFormat`.
8. Unjustified `autoFocus` attributes that hijack screen reader focus upon page load.
