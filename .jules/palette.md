## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.
## 2026-03-12 - [Added ARIA Controls for Collapsible Elements]
**Learning:** Collapsible trigger elements (like 'Show all' buttons) should explicitly link to their controlled content using `aria-controls` alongside `aria-expanded`, enabling screen reader users to understand what part of the interface is being revealed or hidden.
**Action:** Always add `aria-controls="[element-id]"` to the toggle button, paired with a matching `id="[element-id]"` on the conditionally rendered container.
## 2025-03-26 - Keyboard Navigation for Custom Interactive Elements
**Learning:** Custom interactive elements (e.g. inline `<button>` components used for toggling content) often lack default focus indicators when clicked or navigated via keyboard, severely hindering accessibility for users relying on keyboard navigation.
**Action:** Always add explicit focus-visible styles (e.g., `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`) along with a border radius (`rounded-sm`) to custom interactive elements to ensure they provide clear visual feedback during keyboard navigation.

## 2025-03-29 - Disabled States with Tooltips
**Learning:** Adding a focusable `<span>` wrapper around a disabled button to enable Radix UI tooltips causes the disabled element to become incorrectly reachable via keyboard navigation and introduces an accessibility anti-pattern. Furthermore, relying on `pointer-events-none` breaks the tooltip functionality.
**Action:** Do not use `<span>` wrappers or `pointer-events-none` for disabled buttons with tooltips. Instead, keep the bare button with `aria-disabled="true"`, conditionally manually intercept the `onClick` event to return early if disabled, and apply explicit `opacity-50 cursor-not-allowed` styles. To prevent confusing hover feedback on the disabled button, always suppress hover styles explicitly based on the button variant (e.g., `hover:bg-transparent hover:text-inherit` for ghost buttons, `hover:bg-primary hover:text-primary-foreground` for default buttons).
## 2025-04-10 - Screen Reader Redundancy on Icon Buttons
**Learning:** Nesting a `<span className="sr-only">Label</span>` inside an icon-only button creates a more cluttered DOM and sometimes redundant announcements for screen readers if visual tooltips are also present.
**Action:** Always prefer applying `aria-label="Label"` directly to the `<button>` element itself for icon-only buttons instead of nesting visually hidden spans.
