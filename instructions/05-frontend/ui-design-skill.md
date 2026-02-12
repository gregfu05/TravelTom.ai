# Frontend UI Design Skill

Use this guide for any frontend UI work in TravelTom to keep designs visually strong, intentional, and consistent across screens.

## Outcome target

- Ship interfaces that feel premium, clear, and conversion-oriented for travel planning.
- Avoid generic layouts and default component-library look.
- Keep visual quality high without compromising accessibility or performance.

## Required workflow

1. Define one clear visual direction before writing UI code.
2. Establish design tokens first (color, typography, spacing, radius, shadow, motion).
3. Build hierarchy-heavy layouts that make the primary action obvious.
4. Add restrained but meaningful motion (entry, state change, feedback).
5. Validate mobile and desktop behavior before considering the task done.
6. Run accessibility checks (keyboard flow, focus visibility, contrast, labels, aria-live where needed).

## Visual direction rules

- Use a cohesive theme per surface; do not mix unrelated visual styles.
- Prefer expressive typography pairings over default sans-only stacks.
- Use depth intentionally: layered surfaces, subtle gradients, and controlled shadows.
- Design with clear rhythm: consistent spacing scale, aligned edges, and predictable section density.
- Make CTAs and next actions unmistakable through contrast, shape, and position.

## TravelTom UI quality bar

- Chat view: clear message hierarchy, comfortable reading width, high-contrast input and send action.
- Recommendation cards: strong imagery area, scannable metadata, visible ranking/explanation, obvious save action.
- Shortlist and itinerary: dense but legible information architecture with sticky actions where useful.
- Booking stub: standout CTA treatment with immediate interaction feedback.

## Motion and interaction

- Use short transitions (150ms to 300ms) with easing that feels responsive.
- Animate only to support understanding (state change, hierarchy, progress).
- Avoid decorative motion that delays task completion.

## Accessibility and responsiveness

- Preserve minimum 4.5:1 contrast for text.
- Ensure full keyboard navigation and visible focus states.
- Respect reduced-motion preferences.
- Confirm layouts at common widths: 360px, 768px, 1024px, 1440px.

## Definition of done for frontend UI tasks

- A clear visual direction is evident and consistent.
- Typography, color, spacing, and motion are tokenized (not hard-coded ad hoc).
- Empty/loading/error/success states are visually and behaviorally complete.
- The UI is responsive, accessible, and production-ready.
