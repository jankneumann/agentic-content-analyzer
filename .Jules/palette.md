## 2025-02-18 - Tooltips on Disabled Buttons
**Learning:** Disabled buttons often have `pointer-events: none` (especially in shadcn/ui), which prevents Tooltips from triggering on hover.
**Action:** Wrap the disabled button in a `span` or `div` (with `tabIndex={0}` if keyboard focus is needed) and place the `TooltipTrigger` on the wrapper, or ensure the button allows pointer events.
