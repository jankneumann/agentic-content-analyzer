## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-03-25 - Accessible Tooltips on Disabled Buttons
**Learning:** Wrapping disabled buttons in focusable `span` elements (e.g., `<span tabIndex={0}><Button disabled /></span>`) to make Radix UI tooltips work creates severe duplicate announcements for screen reader users. The HTML `disabled` attribute also drops the element from the tab order, and using `pointer-events-none` prevents the hover events required to trigger the tooltip.
**Action:** Do not use the HTML `disabled` attribute or `pointer-events-none` on buttons that need tooltips. Instead, use `aria-disabled="true"`, conditionally apply `opacity-50 cursor-not-allowed` styling, and handle click prevention manually in the `onClick` handler.
