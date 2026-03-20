## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2024-05-19 - Link Character Counters to Input Elements
**Learning:** Text inputs with explicit character limits (e.g., chat inputs, feedback forms) should always link the character count display element to the input field using `aria-describedby` so screen readers can announce the constraint automatically when the field receives focus.
**Action:** When adding character counters to textareas or inputs, ensure the counter has a unique `id` and the input references it via `aria-describedby`.
