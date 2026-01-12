/**
 * Route Tree Configuration
 *
 * This file defines the route tree structure for TanStack Router.
 * Using manual routing with createRoute (not file-based routing).
 */

import { Route as rootRoute } from "./routes/__root"
import { IndexRoute } from "./routes/index"
import { NewslettersRoute } from "./routes/newsletters"
import { ContentsRoute } from "./routes/contents"
import { SummariesRoute } from "./routes/summaries"
import { ThemesRoute } from "./routes/themes"
import { DigestsRoute } from "./routes/digests"
import { ScriptsRoute } from "./routes/scripts"
import { PodcastsRoute } from "./routes/podcasts"
import { ReviewRoute } from "./routes/review"
import { SummaryReviewRoute } from "./routes/review/summary.$id"
import { DigestReviewRoute } from "./routes/review/digest.$id"
import { ScriptReviewRoute } from "./routes/review/script.$id"
import { SettingsRoute } from "./routes/settings"

/**
 * Build the route tree by connecting children to root
 *
 * Review routes have nested children:
 * - /review (index)
 * - /review/summary/:id (summary review)
 * - /review/digest/:id (digest review)
 * - /review/script/:id (script review)
 */
const ReviewRouteWithChildren = ReviewRoute.addChildren([
  SummaryReviewRoute,
  DigestReviewRoute,
  ScriptReviewRoute,
])

export const routeTree = rootRoute.addChildren([
  IndexRoute,
  NewslettersRoute,
  ContentsRoute,
  SummariesRoute,
  ThemesRoute,
  DigestsRoute,
  ScriptsRoute,
  PodcastsRoute,
  ReviewRouteWithChildren,
  SettingsRoute,
])

/**
 * Export root route for child routes to reference
 */
export { rootRoute }
