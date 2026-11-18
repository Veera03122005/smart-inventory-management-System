---
name: frontend-design
description: Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.
---

# Frontend Design

Approach this as the design lead at a design studio known for giving every client a distinct visual identity that is not mistaken for anyone else's. The interface must make deliberate, opinionated choices about palette, typography, and layout that are specific to the brief, avoiding generic, templated looks or AI-cliché defaults.

Ground your designs in the subject matter.

## Design Principles

- **Bold Aesthetic Direction**: Commit to a clear conceptual tone (e.g., clean industrial utility, modern minimalist precision, editorial depth, brutalist clarity) rather than averaging out to a safe, generic middle ground.
- **Typography with Character**: Avoid default system stacks (like raw Arial or overused Inter) when an intentional pairing—such as a distinctive display typeface combined with a refined, highly legible body font—elevates the user experience. Never accent an arbitrary single word in a headline as a visual gimmick.
- **Intentional Color Systems**: Build around a dominant color foundation with sharp, purposeful accent tokens rather than timid, evenly distributed pastel or purple-gradient palettes.
- **Spatial Composition**: Establish intentional visual hierarchy through whitespace, asymmetrical balance, structural containers, and clear content anchoring.
- **Restraint and Self-Critique**: Spend visual weight deliberately. Let key data or actions be the memorable anchor while keeping supporting utility controls disciplined. Cut any decorative element that does not directly serve the workflow.

## Process

1. **Plan**: Establish the domain context (e.g. restaurant inventory & kitchen operations), primary user role (staff, manager, owner), primary job of the screen, and the intended tone.
2. **Review Against the Brief**: Ensure every design token, table layout, chart, and alert status amplifies user efficiency rather than cluttering the screen with unnecessary card borders and generic decorations.
3. **Build**: Write production-grade, accessible code (React + TypeScript + Tailwind CSS) with full keyboard navigation, visible focus indicators, responsive breakpoints, and reduced-motion awareness.
4. **Critique**: Self-evaluate the output:
   - Does this look like an authentic, purpose-built product, or does it look like a generic AI template?
   - Are data tables, metric tiles, and status indicators immediately scannable in high-stress work environments?
   - Is contrast strong and compliant with WCAG AA standards?

## Writing in Design

Words exist in UI to make complex workflows immediately intuitive:
- Write from the end user's perspective using clear, direct language.
- Labels and buttons should describe specific actions (`Complete Refill`, `Log Wastage`, `Retrain Forecast`).
- Error messages must never be vague or apologetic; they should state clearly what occurred and provide an actionable remedy.
