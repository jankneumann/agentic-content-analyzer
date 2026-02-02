## 2025-05-15 - BackgroundTasksIndicator Tooltip Context
**Learning:** `BackgroundTasksIndicator` is rendered in `__root.tsx` outside the `AppShell`, meaning it does not inherit the global `TooltipProvider`.
**Action:** Always wrap tooltips in this component (or other root-level overlays) with a local `TooltipProvider`, or move the global provider up the tree in `__root.tsx`.
