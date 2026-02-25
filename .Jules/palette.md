## 2025-02-23 - Explaining Disabled States
**Learning:** Users often encounter disabled buttons without understanding why they are inactive, leading to confusion and frustration.
**Action:** Always wrap disabled interactive elements (like buttons) in a Tooltip that explains the reason for the disabled state, especially for complex actions like "Generate Preview" where multiple conditions might prevent usage.

## 2025-05-20 - Accessible Form Controls in Custom Wrappers
**Learning:** Custom form row wrappers (like `SettingRow`) often break implicit label associations. Radix UI components (Select, Slider, Switch) need explicit `aria-labelledby` or `id` matching to be accessible, especially when the label is rendered by the wrapper.
**Action:** Always pass a unique `controlId` to custom form wrappers and explicitly associate it with the inner control using `htmlFor`, `id`, `aria-labelledby`, or `aria-describedby`.

## 2025-05-20 - Manual TanStack Router Configuration
**Learning:** When using TanStack Router in manual mode (without the Vite plugin),  can cause type errors if the route tree is not perfectly synced. It's safer to use  for manually defined routes to avoid dependency on generated types.
**Action:** Use  for manual route definitions and ensure all routes are explicitly added to .

## 2025-05-20 - Manual TanStack Router Configuration
**Learning:** When using TanStack Router in manual mode (without the Vite plugin), `createFileRoute` can cause type errors if the route tree is not perfectly synced. It's safer to use `createRoute` for manually defined routes to avoid dependency on generated types.
**Action:** Use `createRoute` for manual route definitions and ensure all routes are explicitly added to `routeTree.gen.ts`.
