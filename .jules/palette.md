## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.
## 2024-03-24 - [Fix Tooltip Accessibility Anti-Pattern]
**Learning:** Adding a focusable span wrapper (with `tabIndex`) around a disabled button to make tooltips work creates duplicate entries for screen readers, leading to poor accessibility. In addition, using `pointer-events-none` prevents hover events, which breaks the tooltips.
**Action:** Use `aria-disabled` instead of `disabled` on the button, manually prevent click propagation in `onClick`, and use Tailwind styling like `opacity-50 cursor-not-allowed` instead of `pointer-events-none`. This allows the tooltip to trigger via hover and keyboard focus without duplicate screen reader announcements.
