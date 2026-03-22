## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-03-22 - Disabled Tooltip Trigger Accessibility
**Learning:** Using the native `disabled` attribute on elements wrapped in Radix UI `TooltipTrigger` combined with focusable spans creates severe screen reader duplicate issues and prevents hover events needed for tooltips.
**Action:** Always avoid the HTML `disabled` attribute on buttons needing tooltips. Instead, use `aria-disabled="true"`, style manually with `opacity-50 cursor-not-allowed` (do not use `pointer-events-none`), and manually prevent the `onClick` event.
