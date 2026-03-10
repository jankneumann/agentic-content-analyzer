## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-02-23 - Accessibility of Tooltips on Disabled Elements
**Learning:** Wrapping disabled buttons in a focusable `span` to trigger tooltips causes severe screen reader duplicate issues and breaks semantic keyboard navigation, as the `disabled` attribute removes the button from the tab order while the wrapper remains.
**Action:** Remove the `disabled` attribute from the interactive element and replace it with `aria-disabled="true"`. Apply manual click prevention and disabled styling (`opacity-50 cursor-not-allowed`) so the button remains naturally focusable, allowing the tooltip to activate organically without confusing screen readers.
