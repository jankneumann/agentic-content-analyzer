## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-03-06 - Tooltips on Disabled Buttons
**Learning:** Wrapping a disabled `<button>` inside a focusable `<span>` so it can trigger a Radix UI tooltip creates severe duplication issues for screen readers. The screen reader announces the span and then the disabled button, creating confusing and repetitive navigation.
**Action:** Never wrap disabled buttons in focusable spans for tooltips. Instead, remove the HTML `disabled` attribute from the button, use `aria-disabled="true"`, and handle the click prevention (`e.preventDefault()`) and disabled styling (e.g. `opacity-50 cursor-not-allowed`) manually. This ensures the button remains natively focusable to trigger the tooltip while remaining properly disabled without screen reader duplicates.
