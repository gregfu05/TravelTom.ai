# Accessibility and i18n

## Accessibility

Minimum checks:

- Keyboard navigation for chat input and list items.
- Visible focus states.
- ARIA labels for buttons and form fields.
- Color contrast ratio of at least 4.5:1.
- Announce new assistant messages with `aria-live`.

## i18n stance

- MVP: single locale (en-US).
- Use a simple string map and avoid hard-coded text in components.
- Final: integrate an i18n library (e.g., i18next) and add locale switch.

