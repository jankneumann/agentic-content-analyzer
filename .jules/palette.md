## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-02-24 - Screen Reader Tooltip Issues on Disabled Buttons
**Learning:** Wrapping disabled buttons in a focusable `<span>` element (e.g., `<span tabIndex={0}>`) solely to trigger a Radix UI Tooltip on hover creates severe accessibility issues. Screen readers will focus the span, reading it as an interactive element without context, and then may read the nested button, causing confusion and duplicate announcements. Additionally, using `disabled:pointer-events-none` prevents tooltips from showing altogether.
**Action:** When adding tooltips to disabled buttons, avoid the HTML `disabled` attribute and instead use `aria-disabled={true}`. Handle the click prevention manually (e.g., `onClick={canSubmit ? handleSubmit : undefined}`) and apply disabled styling manually (like `opacity-50 cursor-not-allowed`). Do not use `pointer-events-none` so the tooltip still triggers on hover, and never wrap the button in an arbitrary focusable span.
