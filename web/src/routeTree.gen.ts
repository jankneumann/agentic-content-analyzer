/**
 * Route Tree Configuration
 *
 * This file defines the route tree structure for TanStack Router.
 * Routes are connected using the _addFileChildren pattern.
 */

import { Route as rootRoute } from "./routes/__root"
import { Route as IndexRoute } from "./routes/index"
import { Route as NewslettersRoute } from "./routes/newsletters"
import { Route as SummariesRoute } from "./routes/summaries"
import { Route as ThemesRoute } from "./routes/themes"
import { Route as DigestsRoute } from "./routes/digests"
import { Route as ScriptsRoute } from "./routes/scripts"
import { Route as PodcastsRoute } from "./routes/podcasts"
import { Route as ReviewRoute } from "./routes/review"
import { Route as SettingsRoute } from "./routes/settings"

/**
 * Declare route module augmentations for type safety
 */
declare module "@tanstack/react-router" {
  interface FileRoutesByPath {
    "/": {
      parentRoute: typeof rootRoute
    }
    "/newsletters": {
      parentRoute: typeof rootRoute
    }
    "/summaries": {
      parentRoute: typeof rootRoute
    }
    "/themes": {
      parentRoute: typeof rootRoute
    }
    "/digests": {
      parentRoute: typeof rootRoute
    }
    "/scripts": {
      parentRoute: typeof rootRoute
    }
    "/podcasts": {
      parentRoute: typeof rootRoute
    }
    "/review": {
      parentRoute: typeof rootRoute
    }
    "/settings": {
      parentRoute: typeof rootRoute
    }
  }
}

/**
 * Build the route tree by connecting children to root
 */
export const routeTree = rootRoute._addFileChildren([
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
