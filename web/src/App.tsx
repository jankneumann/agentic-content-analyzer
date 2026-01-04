/**
 * App Component
 *
 * Root component for the Newsletter Aggregator Web UI.
 * This is a placeholder that demonstrates the setup is working.
 * It will be replaced with the full application layout in Phase 1.2.
 */

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Newspaper, Sparkles, Radio, BarChart3 } from "lucide-react"

/**
 * Pipeline step configuration for display
 */
const pipelineSteps = [
  {
    name: "Newsletters",
    description: "Ingest from Gmail and RSS feeds",
    icon: Newspaper,
    status: "ready" as const,
  },
  {
    name: "Summaries",
    description: "AI-powered content extraction",
    icon: Sparkles,
    status: "ready" as const,
  },
  {
    name: "Themes",
    description: "Knowledge graph analysis",
    icon: BarChart3,
    status: "ready" as const,
  },
  {
    name: "Podcasts",
    description: "Generate audio digests",
    icon: Radio,
    status: "ready" as const,
  },
]

function App() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center px-4">
          <h1 className="text-xl font-semibold">
            Newsletter Aggregator
          </h1>
          <Badge variant="secondary" className="ml-3">
            v0.1.0
          </Badge>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Welcome Card */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Welcome to Newsletter Aggregator</CardTitle>
            <CardDescription>
              An agentic AI solution for aggregating and summarizing AI
              newsletters into daily and weekly digests.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              This UI is under development. The project setup is complete with:
            </p>
            <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
              <li>Vite + React + TypeScript</li>
              <li>Tailwind CSS v4 with custom theme</li>
              <li>shadcn/ui components</li>
              <li>ESLint + Prettier configuration</li>
              <li>TypeScript types for all backend models</li>
            </ul>
          </CardContent>
        </Card>

        {/* Pipeline Steps */}
        <h2 className="mb-4 text-lg font-semibold">Pipeline Steps</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {pipelineSteps.map((step) => (
            <Card key={step.name} className="relative">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <step.icon className="h-5 w-5 text-muted-foreground" />
                  <Badge
                    variant={step.status === "ready" ? "default" : "secondary"}
                  >
                    {step.status}
                  </Badge>
                </div>
                <CardTitle className="text-base">{step.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {step.description}
                </p>
                <Button className="mt-4 w-full" variant="outline" size="sm">
                  View
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="mt-8 flex gap-4">
          <Button>
            <Newspaper className="mr-2 h-4 w-4" />
            Ingest Newsletters
          </Button>
          <Button variant="outline">
            <Sparkles className="mr-2 h-4 w-4" />
            Generate Digest
          </Button>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-4">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          Phase 1.1 Complete - Project Setup
        </div>
      </footer>
    </div>
  )
}

export default App
