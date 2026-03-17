## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.
## 2025-03-17 - Character Counters
**Learning:** Adding `aria-live="polite"` to a character counter that updates on every keystroke is an accessibility anti-pattern because it causes the screen reader to constantly announce every number change while the user types, overwhelming them.
**Action:** Use `aria-describedby` on the input to link it to the character counter `id`, and provide a clear `aria-label` on the counter, but avoid `aria-live` on frequently updating text inputs.
