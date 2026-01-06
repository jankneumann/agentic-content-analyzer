import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

/**
 * Vite Configuration for Newsletter Aggregator Web UI
 *
 * This configuration sets up:
 * - React with Fast Refresh for hot module replacement
 * - Tailwind CSS v4 via the official Vite plugin
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

  build: {
    // Output directory for production build
    outDir: 'dist',

    // Generate source maps for debugging production issues
    sourcemap: true,
  },
})
