/**
 * Button Component
 *
 * A versatile button component built with class-variance-authority (cva).
 * This component is part of the shadcn/ui library and follows its patterns.
 *
 * @example
 * // Default button
 * <Button>Click me</Button>
 *
 * @example
 * // Button variants
 * <Button variant="destructive">Delete</Button>
 * <Button variant="outline">Cancel</Button>
 * <Button variant="secondary">Secondary</Button>
 * <Button variant="ghost">Ghost</Button>
 * <Button variant="link">Link</Button>
 *
 * @example
 * // Button sizes
 * <Button size="sm">Small</Button>
 * <Button size="lg">Large</Button>
 * <Button size="icon"><Icon /></Button>
 *
 * @example
 * // As a different element (using asChild)
 * <Button asChild>
 *   <a href="/link">Link styled as button</a>
 * </Button>
 */

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Button variants configuration using class-variance-authority
 *
 * cva() creates a function that generates class names based on props.
 * This pattern enables:
 * - Type-safe variant props
 * - Consistent styling across the app
 * - Easy customization via className prop
 */
const buttonVariants = cva(
  // Base classes applied to all buttons
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      /**
       * Visual style variants
       * - default: Primary action (filled background)
       * - destructive: Dangerous actions like delete
       * - outline: Secondary action with border
       * - secondary: Less prominent action
       * - ghost: Minimal, transparent background
       * - link: Looks like a hyperlink
       */
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      /**
       * Size variants
       * - default: Standard size for most use cases
       * - sm: Compact buttons for dense UIs
       * - lg: Large buttons for prominent CTAs
       * - icon: Square button for icon-only content
       */
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    // Default values when no variant/size is specified
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

/**
 * Button props interface
 *
 * Extends native button attributes and adds:
 * - variant: Visual style (default, destructive, outline, etc.)
 * - size: Button size (default, sm, lg, icon)
 * - asChild: When true, renders children as the button element
 * - isLoading: When true, shows a loading spinner and disables the button
 */
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /**
   * When true, the Button will render its children using Radix's Slot component.
   * This allows the button styles to be applied to a child element (like an <a> tag).
   *
   * @example
   * <Button asChild>
   *   <Link to="/page">Navigate</Link>
   * </Button>
   */
  asChild?: boolean
  /**
   * When true, shows a loading spinner and disables the button.
   * - If size="icon", replaces children with spinner
   * - Otherwise, prepends spinner to children
   */
  isLoading?: boolean
}

/**
 * Button component
 *
 * A polymorphic button that can render as a native button or any other element
 * when using the asChild prop.
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      isLoading = false,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    // When asChild is true, use Slot to pass styles to the child element
    // Otherwise, render a native button
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading && !asChild ? (
          size === "icon" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {children}
            </>
          )
        ) : (
          children
        )}
      </Comp>
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
