/**
 * Route Tree Configuration
 *
 * This file defines the route tree structure for TanStack Router.
 * Using manual routing with createRoute (not file-based routing).
 */

import { Route as rootRoute } from "./routes/__root"
import { IndexRoute } from "./routes/index"
import { ContentsRoute } from "./routes/contents"
import { IngestRoute } from "./routes/ingest"
import { SummariesRoute } from "./routes/summaries"
import { ThemesRoute } from "./routes/themes"
import { DigestsRoute } from "./routes/digests"
import { ScriptsRoute } from "./routes/scripts"
import { PodcastsRoute } from "./routes/podcasts"
import { AudioDigestsRoute } from "./routes/audio-digests"
import { ReviewRoute } from "./routes/review"
import { SummaryReviewRoute } from "./routes/review/summary.$id"
import { DigestReviewRoute } from "./routes/review/digest.$id"
import { ScriptReviewRoute } from "./routes/review/script.$id"
import { SettingsRoute } from "./routes/settings"
import { SettingsPromptsRoute } from "./routes/settings/prompts"
import { SettingsModelsRoute } from "./routes/settings/models"
import { SettingsVoiceRoute } from "./routes/settings/voice"
import { SettingsNotificationsRoute } from "./routes/settings/notifications"
import { StatusRoute } from "./routes/status"
import { TaskHistoryRoute } from "./routes/task-history"
import { LoginRoute } from "./routes/login"

/**
 * Build the route tree by connecting children to root
 *
 * Review routes have nested children:
 * - /review (index)
 * - /review/summary/:id (summary review)
 * - /review/digest/:id (digest review)
 * - /review/script/:id (script review)
 *
 * Settings routes have nested children:
 * - /settings (redirects to /settings/prompts)
 * - /settings/prompts
 * - /settings/models
 * - /settings/voice
 * - /settings/notifications
 */
const ReviewRouteWithChildren = ReviewRoute.addChildren([
  SummaryReviewRoute,
  DigestReviewRoute,
  ScriptReviewRoute,
])

const SettingsRouteWithChildren = SettingsRoute.addChildren([
  SettingsPromptsRoute,
  SettingsModelsRoute,
  SettingsVoiceRoute,
  SettingsNotificationsRoute,
])

export const routeTree = rootRoute.addChildren([
  IndexRoute,
  ContentsRoute,
  IngestRoute,
  SummariesRoute,
  ThemesRoute,
  DigestsRoute,
  ScriptsRoute,
  PodcastsRoute,
  AudioDigestsRoute,
  ReviewRouteWithChildren,
  TaskHistoryRoute,
  SettingsRouteWithChildren,
  StatusRoute,
  LoginRoute,
])

/**
 * Export root route for child routes to reference
 */
export { rootRoute }
