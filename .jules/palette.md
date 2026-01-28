## 2024-05-22 - Accessibility in Action Lists
**Learning:** Icon-only buttons in list views (like "View" and "Review") are common but often lack accessibility labels, making them invisible to screen readers.
**Action:** Always verify `aria-label` or visible text exists for action buttons in tables/lists. Use `title` for tooltip but rely on `aria-label` for a11y.

## 2025-02-12 - Missing ARIA on Icon-Only Buttons
**Learning:** shadcn/ui Button components with `size="icon"` are frequently used without `aria-label`, making them inaccessible to screen readers. This pattern is common in toolbars and chat interfaces.
**Action:** Always check `size="icon"` buttons during code review and add descriptive `aria-label` props.

## 2026-01-28 - Dynamic ARIA Labels for Toggles
**Learning:** Collapsible sidebars that switch between icon-only and text modes require dynamic `aria-label`s. When collapsed, the visual text is gone, so an explicit label like "Expand sidebar" is mandatory.
**Action:** Use ternary operators for `aria-label` on toggle buttons: `aria-label={isCollapsed ? "Expand" : "Collapse"}`.
