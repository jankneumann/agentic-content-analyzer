## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-03-07 - Explicit Type for Action Buttons
**Learning:** Native `<button>` elements embedded in complex UI components (like inline removable tags or copy buttons) often miss explicit `type="button"` declarations and keyboard focus indicators, which can inadvertently trigger form submissions and degrade keyboard accessibility.
**Action:** Always ensure any non-submit `<button>` explicitly declares `type="button"` and includes `focus-visible` styles (e.g., `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm`) so it functions safely and remains keyboard navigable.
