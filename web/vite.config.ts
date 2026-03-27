import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

/**
 * Vite Configuration for ACA (AI Content Analyzer) Web UI
 *
 * This configuration sets up:
 * - React with Fast Refresh for hot module replacement
 * - Tailwind CSS v4 via the official Vite plugin
 * - PWA support via vite-plugin-pwa with offline fallback
 * - Path aliases (@/) for cleaner imports
 * - API proxy to FastAPI backend during development
 *
 * @see https://vite.dev/config/
 */
export default defineConfig({
  plugins: [
    // React plugin provides Fast Refresh and JSX transformation
    react(),
    // Tailwind CSS v4 Vite plugin for CSS processing
    tailwindcss(),
    // PWA plugin for offline support and installability
    VitePWA({
      // Auto-update service worker when new version available
      registerType: 'autoUpdate',
      // Include these assets in the precache
      includeAssets: ['favicon.ico', 'icons/*.png', 'icons/*.svg'],
      // Web app manifest configuration
      manifest: {
        name: 'ACA — AI Content Analyzer',
        short_name: 'ACA',
        description: 'AI-powered content analysis and digests',
        theme_color: '#1a1a1a',
        background_color: '#1a1a1a',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-192-maskable.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: '/icons/icon-512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      // Workbox configuration for service worker behavior
      workbox: {
        // Cache these file types
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Show offline page when navigating to uncached routes
        navigateFallback: '/offline.html',
        // Don't use fallback for API routes
        navigateFallbackDenylist: [/^\/api\//],
        // Runtime caching strategies
        runtimeCaching: [
          {
            // Cache images with CacheFirst strategy
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'image-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 86400, // 24 hours
              },
            },
          },
        ],
      },
    }),
  ],

  resolve: {
    alias: {
      // Path alias: import from '@/components/...' instead of '../../components/...'
      // This makes imports cleaner and refactoring easier
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    // Development server port
    port: 5173,

    // Cross-origin isolation headers required for SharedArrayBuffer
    // (used by @remotion/whisper-web WASM inference)
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin',
    },

    // Proxy API requests to FastAPI backend
    // This avoids CORS issues during development
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Rewrite not needed since FastAPI routes start with /api
      },
    },
  },

  optimizeDeps: {
    // Exclude @remotion/whisper-web from dep optimization — it loads WASM
    exclude: ['@remotion/whisper-web'],
  },

  build: {
    // Output directory for production build
    outDir: 'dist',

    // Generate source maps for debugging production issues
    sourcemap: true,
  },
})
