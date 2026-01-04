/**
 * Card Components
 *
 * A set of card components for displaying content in a contained, elevated surface.
 * Cards are used throughout the UI for grouping related information.
 *
 * @example
 * // Basic card with all parts
 * <Card>
 *   <CardHeader>
 *     <CardTitle>Card Title</CardTitle>
 *     <CardDescription>Card description goes here</CardDescription>
 *   </CardHeader>
 *   <CardContent>
 *     <p>Main content of the card</p>
 *   </CardContent>
 *   <CardFooter>
 *     <Button>Action</Button>
 *   </CardFooter>
 * </Card>
 *
 * @example
 * // Simple card
 * <Card className="p-4">
 *   <p>Simple content</p>
 * </Card>
 */

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Card - The main container component
 *
 * Provides a rounded, bordered container with subtle shadow.
 * Use as the outer wrapper for card content.
 */
const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      // Base styles: rounded corners, border, background, and shadow
      "rounded-xl border bg-card text-card-foreground shadow",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

/**
 * CardHeader - Container for title and description
 *
 * Provides consistent spacing for the top section of a card.
 * Typically contains CardTitle and optionally CardDescription.
 */
const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      // Flex column with gap for title/description spacing
      "flex flex-col space-y-1.5 p-6",
      className
    )}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

/**
 * CardTitle - The main heading of the card
 *
 * Rendered as an h3 for semantic HTML.
 * Styled for prominence with larger text and bold weight.
 */
const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      // Semibold, with tight leading for multi-line titles
      "font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

/**
 * CardDescription - Supporting text below the title
 *
 * Rendered as a paragraph with muted text color.
 * Use for additional context about the card's content.
 */
const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      // Smaller text with muted color for secondary information
      "text-sm text-muted-foreground",
      className
    )}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

/**
 * CardContent - Main body area of the card
 *
 * Container for the primary content of the card.
 * Has horizontal and bottom padding (top padding removed for connection with header).
 */
const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      // Padding on sides and bottom; no top padding to connect with header
      "p-6 pt-0",
      className
    )}
    {...props}
  />
))
CardContent.displayName = "CardContent"

/**
 * CardFooter - Bottom area for actions
 *
 * Typically contains buttons or links related to the card.
 * Items are displayed in a row by default.
 */
const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      // Flex row for action buttons, no top padding
      "flex items-center p-6 pt-0",
      className
    )}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
