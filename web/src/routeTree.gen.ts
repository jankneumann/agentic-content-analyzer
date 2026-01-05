/**
 * Route Tree Configuration
 *
 * This file defines the route tree structure for TanStack Router.
 * Using manual routing with createRoute (not file-based routing).
 */

import { Route as rootRoute } from "./routes/__root"
import { IndexRoute } from "./routes/index"
import { NewslettersRoute } from "./routes/newsletters"
import { SummariesRoute } from "./routes/summaries"
import { ThemesRoute } from "./routes/themes"
import { DigestsRoute } from "./routes/digests"
import { ScriptsRoute } from "./routes/scripts"
import { PodcastsRoute } from "./routes/podcasts"
import { ReviewRoute } from "./routes/review"
import { SettingsRoute } from "./routes/settings"

/**
 * Build the route tree by connecting children to root
 */
export const routeTree = rootRoute.addChildren([
  IndexRoute,
  NewslettersRoute,
  SummariesRoute,
  ThemesRoute,
  DigestsRoute,
  ScriptsRoute,
  PodcastsRoute,
  ReviewRoute,
  SettingsRoute,
])

/**
 * Export root route for child routes to reference
 */
export { rootRoute }
