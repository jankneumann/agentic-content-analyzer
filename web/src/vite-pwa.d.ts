/**
 * Type declarations for vite-plugin-pwa virtual modules
 *
 * vite-plugin-pwa provides virtual modules that need type declarations
 * for TypeScript to understand the imports.
 *
 * @see https://vite-pwa-org.netlify.app/guide/register-service-worker.html
 */

declare module "virtual:pwa-register/react" {
  import type { Dispatch, SetStateAction } from "react"

  export interface RegisterSWOptions {
    /**
     * Called once the service worker is registered (every time the page loads).
     * @param swUrl URL of the service worker
     * @param registration ServiceWorkerRegistration object
     */
    onRegisteredSW?: (
      swUrl: string,
      registration: ServiceWorkerRegistration | undefined
    ) => void

    /**
     * Called if there is an error during service worker registration.
     * @param error The error that occurred
     */
    onRegisterError?: (error: Error) => void

    /**
     * Called when there is a new content available from the service worker.
     * @param registration ServiceWorkerRegistration object
     */
    onNeedRefresh?: () => void

    /**
     * Called when the service worker is offline ready.
     */
    onOfflineReady?: () => void
  }

  export interface UseRegisterSWReturn {
    /**
     * Whether a new service worker is waiting to be activated.
     * Tuple: [needRefresh, setNeedRefresh]
     */
    needRefresh: [boolean, Dispatch<SetStateAction<boolean>>]

    /**
     * Whether the app is ready for offline use.
     * Tuple: [offlineReady, setOfflineReady]
     */
    offlineReady: [boolean, Dispatch<SetStateAction<boolean>>]

    /**
     * Updates the service worker. Pass true to reload the page.
     * @param reloadPage Whether to reload the page after update
     */
    updateServiceWorker: (reloadPage?: boolean) => Promise<void>
  }

  /**
   * React hook for registering the service worker.
   * @param options Configuration options
   * @returns Object with needRefresh, offlineReady, and updateServiceWorker
   */
  export function useRegisterSW(options?: RegisterSWOptions): UseRegisterSWReturn
}
