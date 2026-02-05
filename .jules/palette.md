## 2024-05-22 - Accessibility in Action Lists
**Learning:** Icon-only buttons in list views (like "View" and "Review") are common but often lack accessibility labels, making them invisible to screen readers.
**Action:** Always verify `aria-label` or visible text exists for action buttons in tables/lists. Use `title` for tooltip but rely on `aria-label` for a11y.

## 2025-02-12 - Missing ARIA on Icon-Only Buttons
**Learning:** shadcn/ui Button components with `size="icon"` are frequently used without `aria-label`, making them inaccessible to screen readers. This pattern is common in toolbars and chat interfaces.
**Action:** Always check `size="icon"` buttons during code review and add descriptive `aria-label` props.

## 2025-02-14 - Accessibility for Toggle Buttons
**Learning:** Toggle buttons that change icon/text based on state need dynamic `aria-label`s to accurately reflect the action (e.g., "Expand sidebar" vs "Collapse sidebar").
**Action:** Ensure state-switching buttons update their accessible name.

## 2025-02-19 - Current Page Indication in Navigation
**Learning:** Navigation items often rely solely on visual styling (e.g., background color) to indicate the active page, which is insufficient for screen reader users.
**Action:** Always add `aria-current="page"` to the link or button representing the current page in a navigation menu.

## 2025-02-26 - Hidden Labels on Mobile
**Learning:** Buttons that hide their text label on mobile (e.g. `hidden sm:inline`) often become inaccessible icon-only buttons if they don't have an `aria-label`.
**Action:** When hiding text labels responsively, ensure the button retains an accessible name via `aria-label` or `sr-only` text.
