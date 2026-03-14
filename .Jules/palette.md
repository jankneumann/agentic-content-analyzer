## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-02-24 - Accessible Disabled Tooltips
**Learning:** Tooltips on native disabled buttons do not trigger hover events, leading to a severe accessibility gap where screen readers and mouse users cannot discover why a button is disabled. Wrapping them in focusable spans causes screen reader duplication issues.
**Action:** For interactive elements with tooltips, avoid the native `disabled` attribute. Use `aria-disabled="true"`, prevent click events manually in the `onClick` handler, and apply visual styling like `opacity-50 cursor-not-allowed`. Avoid `pointer-events-none` so hover events can still trigger the tooltip.
