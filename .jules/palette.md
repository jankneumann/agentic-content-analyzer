## 2025-02-12 - Missing ARIA on Icon-Only Buttons
**Learning:** shadcn/ui Button components with `size="icon"` are frequently used without `aria-label`, making them inaccessible to screen readers. This pattern is common in toolbars and chat interfaces.
**Action:** Always check `size="icon"` buttons during code review and add descriptive `aria-label` props.
