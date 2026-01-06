/**
 * Separator Component
 *
 * A visual divider for separating content sections.
 * Built on Radix UI Separator for accessibility.
 *
 * @example
 * // Horizontal separator (default)
 * <Separator />
 *
 * @example
 * // Vertical separator
 * <Separator orientation="vertical" className="h-4" />
 *
 * @example
 * // With custom styling
 * <Separator className="my-4 bg-primary" />
 */

import * as React from "react"
import * as SeparatorPrimitive from "@radix-ui/react-separator"

import { cn } from "@/lib/utils"

const Separator = React.forwardRef<
  React.ComponentRef<typeof SeparatorPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(
  (
    { className, orientation = "horizontal", decorative = true, ...props },
    ref
  ) => (
    <SeparatorPrimitive.Root
      ref={ref}
      decorative={decorative}
      orientation={orientation}
      className={cn(
        "shrink-0 bg-border",
        orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
        className
      )}
      {...props}
    />
  )
)
Separator.displayName = SeparatorPrimitive.Root.displayName

export { Separator }
