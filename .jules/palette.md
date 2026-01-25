## 2024-05-22 - Accessibility in Action Lists
**Learning:** Icon-only buttons in list views (like "View" and "Review") are common but often lack accessibility labels, making them invisible to screen readers.
**Action:** Always verify `aria-label` or visible text exists for action buttons in tables/lists. Use `title` for tooltip but rely on `aria-label` for a11y.

## 2025-02-12 - Missing ARIA on Icon-Only Buttons
**Learning:** shadcn/ui Button components with `size="icon"` are frequently used without `aria-label`, making them inaccessible to screen readers. This pattern is common in toolbars and chat interfaces.
**Action:** Always check `size="icon"` buttons during code review and add descriptive `aria-label` props.
