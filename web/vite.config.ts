import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import type { OutputChunk } from 'rollup'
import type { Plugin } from 'vite'

type ReleaseIdentity = {
  revision: string
  revision_source:
    | 'railway_commit_sha'
    | 'github_sha'
    | 'verified_detached_sha'
    | 'local_development'
}

const COMMIT_SHA = /^[0-9a-f]{40}$/

function platformReleaseIdentity(): ReleaseIdentity | undefined {
  const candidates = [
    ['RAILWAY_GIT_COMMIT_SHA', 'railway_commit_sha'],
    ['GITHUB_SHA', 'github_sha'],
  ] as const
  for (const [variable, revision_source] of candidates) {
    const revision = process.env[variable]
    if (revision === undefined) continue
    if (!COMMIT_SHA.test(revision)) {
      throw new Error(`${variable} must be a lowercase 40-character commit SHA`)
    }
    return { revision, revision_source }
  }
}

function stampedReleaseIdentity(): ReleaseIdentity | undefined {
  const stampPath = path.resolve(__dirname, 'release-build.json')
  if (!existsSync(stampPath)) return
  const parsed: unknown = JSON.parse(readFileSync(stampPath, 'utf8'))
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    Object.keys(parsed).sort().join(',') !== 'revision,revision_source,schema_version' ||
    !('schema_version' in parsed) ||
    parsed.schema_version !== 1 ||
    !('revision' in parsed) ||
    typeof parsed.revision !== 'string' ||
    !COMMIT_SHA.test(parsed.revision) ||
    !('revision_source' in parsed) ||
    parsed.revision_source !== 'verified_detached_sha'
  ) {
    throw new Error('release-build.json is not a valid verified detached-SHA stamp')
  }
  return {
    revision: parsed.revision,
    revision_source: parsed.revision_source,
  }
}

function releaseIdentity(): ReleaseIdentity {
  return (
    platformReleaseIdentity() ??
    stampedReleaseIdentity() ?? {
      revision: 'development',
      revision_source: 'local_development',
    }
  )
}

function releaseMetadataPlugin(): Plugin {
  const identity = releaseIdentity()
  return {
    name: 'aca-release-metadata',
    transformIndexHtml() {
      return [
        {
          tag: 'meta',
          attrs: { name: 'release-revision', content: identity.revision },
          injectTo: 'head',
        },
        {
          tag: 'meta',
          attrs: {
            name: 'release-revision-source',
            content: identity.revision_source,
          },
          injectTo: 'head',
        },
      ]
    },
    generateBundle(_options, bundle) {
      const javascript = Object.values(bundle)
        .filter((output): output is OutputChunk => output.type === 'chunk')
        .map((chunk) => {
          const bytes = Buffer.from(chunk.code)
          return {
            path: `/${chunk.fileName}`,
            size_bytes: bytes.byteLength,
            sha256: createHash('sha256').update(bytes).digest('hex'),
          }
        })
        .sort((left, right) => left.path.localeCompare(right.path))
      this.emitFile({
        type: 'asset',
        fileName: 'release-assets.json',
        source: JSON.stringify({
          schema_version: 1,
          ...identity,
          javascript,
        }),
      })
    },
  }
}

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
  test: {
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
  },
  plugins: [
    releaseMetadataPlugin(),
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
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
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
