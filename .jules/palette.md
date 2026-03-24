## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.
## 2026-03-12 - [Added ARIA Controls for Collapsible Elements]
**Learning:** Collapsible trigger elements (like 'Show all' buttons) should explicitly link to their controlled content using `aria-controls` alongside `aria-expanded`, enabling screen reader users to understand what part of the interface is being revealed or hidden.
**Action:** Always add `aria-controls="[element-id]"` to the toggle button, paired with a matching `id="[element-id]"` on the conditionally rendered container.
