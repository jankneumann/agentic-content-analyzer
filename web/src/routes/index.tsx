/**
 * Dashboard Page (Index Route)
 *
 * The home page of the application showing:
 * - Pipeline status overview
 * - Recent activity
 * - Quick actions
 *
 * Route: /
 */

import { createRoute } from "@tanstack/react-router"
import {
  Newspaper,
  Sparkles,
  FileText,
  Radio,
  ArrowRight,
  BarChart3,
  Mic,
} from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer, PageSection } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

/**
 * Route definition for the index page
 */
export const IndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardPage,
})

/**
 * Pipeline step configuration
 */
const pipelineSteps = [
  {
    name: "Newsletters",
    description: "Ingested from Gmail and RSS",
    icon: Newspaper,
    count: 0,
    status: "idle" as const,
    href: "/newsletters",
  },
  {
    name: "Summaries",
    description: "AI-generated extractions",
    icon: Sparkles,
    count: 0,
    status: "idle" as const,
    href: "/summaries",
  },
  {
    name: "Themes",
    description: "Knowledge graph analysis",
    icon: BarChart3,
    count: 0,
    status: "idle" as const,
    href: "/themes",
  },
  {
    name: "Digests",
    description: "Aggregated reports",
    icon: FileText,
    count: 0,
    status: "idle" as const,
    href: "/digests",
  },
  {
    name: "Scripts",
    description: "Podcast dialogue",
    icon: Mic,
    count: 0,
    status: "idle" as const,
    href: "/scripts",
  },
  {
    name: "Podcasts",
    description: "Generated audio",
    icon: Radio,
    count: 0,
    status: "idle" as const,
    href: "/podcasts",
  },
]

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: "idle" | "processing" | "error" }) {
  const variants = {
    idle: { label: "Ready", variant: "secondary" as const },
    processing: { label: "Processing", variant: "default" as const },
    error: { label: "Error", variant: "destructive" as const },
  }

  const { label, variant } = variants[status]
  return <Badge variant={variant}>{label}</Badge>
}

/**
 * Dashboard page component
 */
function DashboardPage() {
  return (
    <PageContainer
      title="Dashboard"
      description="Overview of your newsletter aggregation pipeline"
      actions={
        <div className="flex gap-2">
          <Button variant="outline">
            <Newspaper className="mr-2 h-4 w-4" />
            Ingest
          </Button>
          <Button>
            <Sparkles className="mr-2 h-4 w-4" />
            Generate Digest
          </Button>
        </div>
      }
    >
      {/* Pipeline Status */}
      <PageSection
        title="Pipeline Status"
        description="Current state of each processing step"
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {pipelineSteps.map((step) => (
            <Card key={step.name} className="relative overflow-hidden">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <step.icon className="h-5 w-5 text-muted-foreground" />
                  <StatusBadge status={step.status} />
                </div>
                <CardTitle className="text-base">{step.name}</CardTitle>
                <CardDescription>{step.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold">{step.count}</span>
                  <Button variant="ghost" size="sm" asChild>
                    <a href={step.href}>
                      View
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageSection>

      {/* Quick Actions */}
      <PageSection
        title="Quick Actions"
        description="Common tasks you might want to perform"
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Button variant="outline" className="h-auto flex-col gap-2 p-4">
            <Newspaper className="h-6 w-6" />
            <span>Ingest Gmail</span>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4">
            <Newspaper className="h-6 w-6" />
            <span>Ingest RSS</span>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4">
            <FileText className="h-6 w-6" />
            <span>Create Daily Digest</span>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4">
            <Radio className="h-6 w-6" />
            <span>Generate Podcast</span>
          </Button>
        </div>
      </PageSection>

      {/* Recent Activity Placeholder */}
      <PageSection
        title="Recent Activity"
        description="Latest updates in your pipeline"
      >
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <p>No recent activity to display.</p>
            <p className="mt-1 text-sm">
              Start by ingesting newsletters from Gmail or RSS feeds.
            </p>
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
