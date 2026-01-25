# UX Design Guidelines

This document captures UX patterns and lessons learned for the frontend application.

## Dialog Design Patterns

### Resizable Dialogs

For detail view dialogs that display variable-length content, use a resizable pattern:

```tsx
<DialogContent className="w-[50vw] min-w-[600px] max-w-[95vw] h-[70vh] min-h-[400px] max-h-[95vh] resize flex flex-col overflow-hidden">
  <DialogHeader className="shrink-0">...</DialogHeader>
  <ScrollArea className="flex-1 min-h-0">...</ScrollArea>
  <DialogFooter className="shrink-0">...</DialogFooter>
</DialogContent>
```

**Key CSS Properties:**

| Property | Purpose |
|----------|---------|
| `w-[50vw]` | Initial width (50% viewport) - room to expand |
| `min-w-[600px]` | Minimum usable width |
| `max-w-[95vw]` | Maximum width (~2x initial for resize room) |
| `h-[70vh]` | Initial height |
| `min-h-[400px]` | Minimum usable height |
| `max-h-[95vh]` | Maximum height |
| `resize` | Enable CSS resize handle |
| `flex flex-col` | Flexbox for dynamic content area |
| `overflow-hidden` | Prevent double scrollbars |

**Critical: `min-h-0` on Flex Children**

Without `min-h-0`, flex children won't shrink below their content's minimum height:

```tsx
// Wrong - ScrollArea won't shrink properly
<ScrollArea className="flex-1">

// Correct - allows shrinking below content size
<ScrollArea className="flex-1 min-h-0">
```

### Tailwind Breakpoint Specificity

When overriding base component classes, match the breakpoint specificity:

```tsx
// Base dialog.tsx has: sm:max-w-lg

// Won't override (unprefixed loses to sm: prefix)
className="max-w-[95vw]"

// Will override (same breakpoint specificity)
className="sm:max-w-[95vw]"

// Better: remove sm:max-w-lg from base component
```

**Solution:** We removed `sm:max-w-lg` from the base Dialog component so individual dialogs can set their own max-width without breakpoint conflicts.

## List View Patterns

### Action Buttons Position

Place action buttons to the **left of the title** in list rows:

```tsx
<TableCell>
  <div className="flex items-start gap-2">
    {/* Actions first */}
    <div className="flex items-center gap-1 shrink-0 pt-0.5">
      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onView}>
        <Eye className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
        <Link to="/review/$id" params={{ id }}>
          <FileSearch className="h-4 w-4" />
        </Link>
      </Button>
    </div>
    {/* Title - clickable */}
    <div className="flex-1 cursor-pointer" onClick={onView}>
      <div className="font-medium line-clamp-1">{title}</div>
    </div>
  </div>
</TableCell>
```

**Benefits:**
- Consistent action location reduces mouse travel
- Improves scannability - users know where to find actions
- Follows Fitts's Law - larger clickable titles are easier to hit

### Clickable Titles

Make titles clickable as an additional way to trigger the primary action (usually "view"):

```tsx
<div
  className="flex-1 cursor-pointer"
  onClick={onView}
  role="button"
  tabIndex={0}
  onKeyDown={(e) => e.key === "Enter" && onView()}
>
  {title}
</div>
```

**Accessibility:** Include `role="button"`, `tabIndex={0}`, and keyboard handler for Enter key.

## Component Architecture

### When to Share vs. Separate

**Share (via CSS classes)** when behavior is simple:
- Resizable container layout
- Header/footer positioning
- Scroll area behavior

**Keep separate** when content differs significantly:
- Different data structures (markdown vs. structured data vs. dialogue)
- Unique UI elements (tabs, badges, speaker turns)
- Different action workflows

**Example - Our Four Detail Dialogs:**

| Dialog | Content Type | Unique Elements |
|--------|--------------|-----------------|
| Summaries | Structured lists | Theme badges, bullet lists |
| Contents | Raw markdown | ReactMarkdown, parser metadata |
| Digests | Multi-section | Tabs, sources grid |
| Scripts | Dialogue | Speaker badges, section cards |

All share the same resize/flex pattern via CSS classes, but each has its own content rendering logic.

### Composition Over Abstraction

For simple shared behavior, prefer CSS classes over extracted components:

```tsx
// Good: shared via CSS classes (explicit, easy to customize)
<DialogContent className="w-[50vw] ... flex flex-col">

// Consider extraction only when:
// - Adding complex shared behavior (keyboard shortcuts, print mode)
// - Same pattern used in 5+ places
// - Behavior requires JS logic, not just styling
```

## Responsive Design

### Viewport-Based Sizing

Use viewport units for dialogs to scale with screen size:

```tsx
// Percentage of viewport
className="w-[50vw] h-[70vh]"

// With pixel constraints for usability
className="w-[50vw] min-w-[600px] max-w-[95vw]"
```

### Fixed vs. Flexible Elements

In flex layouts, mark fixed-size elements explicitly:

```tsx
<div className="flex flex-col h-full">
  <header className="shrink-0">Fixed header</header>
  <main className="flex-1 min-h-0 overflow-auto">Grows to fill</main>
  <footer className="shrink-0">Fixed footer</footer>
</div>
```

## Common Gotchas

### CSS Resize Limitations

1. **Needs overflow**: `resize` only works with `overflow: auto|scroll|hidden`
2. **Needs room to grow**: Initial size must be less than max size
3. **Handle position**: Resize handle is always bottom-right corner

### Radix Dialog Centering

Radix dialogs use `translate(-50%, -50%)` for centering. This works well with resize because the dialog stays centered as it grows.

### ScrollArea Height

shadcn/ui ScrollArea needs explicit height to scroll:

```tsx
// Won't scroll (no height constraint)
<ScrollArea><LongContent /></ScrollArea>

// Will scroll (explicit height)
<ScrollArea className="h-[400px]"><LongContent /></ScrollArea>

// Will scroll (flex child fills parent)
<ScrollArea className="flex-1 min-h-0"><LongContent /></ScrollArea>
```
