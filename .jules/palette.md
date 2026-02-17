## 2025-02-18 - Standardized Search Input Pattern
**Learning:** Search inputs across the app lacked clear buttons and keyboard accessibility (Escape to clear), making them cumbersome for keyboard and mobile users.
**Action:** Use the new `SearchInput` component in `web/src/components/ui/search-input.tsx` for all search fields. It handles clearing, keyboard shortcuts, and visual consistency automatically.

## 2025-02-18 - Search Input Usability
**Learning:** Search inputs in data-heavy management interfaces (like prompt settings) significantly benefit from an explicit "Clear" button and keyboard shortcut (Escape). Users often type filters, review results, and then want to immediately clear the filter to see the full list again. Without these controls, they must manually backspace, which is tedious.
**Action:** Always implement a clear button (accessible via keyboard/screen reader) and handle the `Escape` key for any search or filter input component. ensure the clear button has `aria-label` and `type="button"`.
