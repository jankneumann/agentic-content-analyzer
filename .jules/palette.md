## 2024-05-22 - Accessibility in Action Lists
**Learning:** Icon-only buttons in list views (like "View" and "Review") are common but often lack accessibility labels, making them invisible to screen readers.
**Action:** Always verify `aria-label` or visible text exists for action buttons in tables/lists. Use `title` for tooltip but rely on `aria-label` for a11y.
