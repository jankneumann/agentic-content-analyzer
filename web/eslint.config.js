/**
 * ESLint Configuration for Newsletter Aggregator Web UI
 *
 * This configuration sets up linting for TypeScript React code with:
 * - TypeScript-aware linting rules
 * - React Hooks rules (exhaustive deps, rules of hooks)
 * - React Refresh for Fast Refresh compatibility
 * - Prettier integration for consistent formatting
 *
 * Uses the new flat config format (ESLint 9+).
 */

import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import eslintConfigPrettier from "eslint-config-prettier"

export default tseslint.config(
  // Ignore build output
  { ignores: ["dist"] },

  // Main configuration for TypeScript React files
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      // Base JavaScript recommended rules
      js.configs.recommended,
      // TypeScript recommended rules (type-aware)
      ...tseslint.configs.recommended,
      // Prettier config (disables formatting rules that conflict with Prettier)
      eslintConfigPrettier,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      // React Hooks plugin for hooks-specific rules
      "react-hooks": reactHooks,
      // React Refresh plugin for Fast Refresh compatibility
      "react-refresh": reactRefresh,
    },
    rules: {
      // React Hooks rules
      ...reactHooks.configs.recommended.rules,

      // React Refresh: only export components from files
      // This ensures Fast Refresh works correctly
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      // TypeScript specific rules
      // Allow unused variables that start with underscore (common convention)
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],

      // Prefer const over let when variable is never reassigned
      "prefer-const": "error",

      // Require explicit return types on exported functions (documentation)
      // Disabled for now to reduce friction during initial development
      // "@typescript-eslint/explicit-function-return-type": "warn",
    },
  }
)
