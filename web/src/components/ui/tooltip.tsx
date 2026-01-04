/**
 * Tooltip Component
 *
 * Displays additional information on hover/focus.
 * Built on Radix UI Tooltip for accessibility and positioning.
 *
 * @example
 * <TooltipProvider>
 *   <Tooltip>
 *     <TooltipTrigger asChild>
 *       <Button variant="icon">
 *         <Icon />
 *       </Button>
 *     </TooltipTrigger>
 *     <TooltipContent>
 *       <p>Tooltip text</p>
 *     </TooltipContent>
 *   </Tooltip>
 * </TooltipProvider>
 */

import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"

import { cn } from "@/lib/utils"

/**
 * TooltipProvider - Wraps the app to enable tooltips
 *
 * Should be placed near the root of your application.
 * Controls the delay before tooltips appear.
 */
const TooltipProvider = TooltipPrimitive.Provider

/**
 * Tooltip - Container for trigger and content
 */
const Tooltip = TooltipPrimitive.Root

/**
 * TooltipTrigger - Element that triggers the tooltip
 *
 * Use asChild to merge with your own element.
 */
const TooltipTrigger = TooltipPrimitive.Trigger

/**
 * TooltipContent - The tooltip popup content
 *
 * Automatically positioned based on available space.
 */
const TooltipContent = React.forwardRef<
  React.ComponentRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        // Base styles
        "z-50 overflow-hidden rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground",
        // Animation
        "animate-in fade-in-0 zoom-in-95",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
        // Position-based slide animations
        "data-[side=bottom]:slide-in-from-top-2",
        "data-[side=left]:slide-in-from-right-2",
        "data-[side=right]:slide-in-from-left-2",
        "data-[side=top]:slide-in-from-bottom-2",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
