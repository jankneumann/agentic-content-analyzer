/**
 * Login Page E2E Tests
 *
 * Tests the owner authentication login flow including:
 * - Password form rendering and submission
 * - Error handling (invalid password, rate limiting)
 * - Redirect behavior (returnTo parameter, post-login navigation)
 * - Keyboard submission (Enter key)
 *
 * Since VITE_AUTH_ENABLED is not set in the E2E dev server, these tests
 * intercept Vite-served source modules to patch isAuthEnabled() to return true.
 * All API calls are mocked via page.route() -- no real backend needed.
 */

import { test, expect } from "../fixtures"

// ─── Helpers ──────────────────────────────────────────────────

/**
 * Patch isAuthEnabled() to return true in the Vite dev server.
 *
 * In dev mode, Vite serves each source file as an individual ES module.
 * We intercept the auth module and replace the isAuthEnabled function body
 * so the login page renders its form instead of redirecting to /.
 *
 * This also patches the __root.tsx beforeLoad to enforce the auth guard,
 * enabling redirect-to-login tests.
 */
async function enableAuth(page: import("@playwright/test").Page): Promise<void> {
  await page.route("**/src/lib/api/auth.ts*", async (route) => {
    const response = await route.fetch()
    let body = await response.text()
    // Replace the env check with a hard-coded true
    body = body.replace(
      /import\.meta\.env\.VITE_AUTH_ENABLED\s*===\s*["']true["']/g,
      "true"
    )
    await route.fulfill({ response, body })
  })
}

/**
 * Mock the session endpoint to return an unauthenticated response.
 */
async function mockSessionUnauthenticated(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.route("**/api/v1/auth/session*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: false }),
    })
  )
}

/**
 * Mock the session endpoint to return an authenticated response.
 */
async function mockSessionAuthenticated(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.route("**/api/v1/auth/session*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: true }),
    })
  )
}

/**
 * Mock a successful login response.
 */
async function mockLoginSuccess(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.route("**/api/v1/auth/login*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: true }),
    })
  )
}

/**
 * Mock a failed login response (wrong password).
 */
async function mockLoginFailure(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.route("**/api/v1/auth/login*", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid password" }),
    })
  )
}

/**
 * Mock a rate-limited login response.
 */
async function mockLoginRateLimited(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.route("**/api/v1/auth/login*", (route) =>
    route.fulfill({
      status: 429,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Too many attempts. Please try again later.",
      }),
    })
  )
}

// ─── Tests ────────────────────────────────────────────────────

test.describe("Login Page", () => {
  test("visit / without session redirects to /login", async ({
    page,
    apiMocks,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    // Mock default API endpoints so the app shell doesn't error
    await apiMocks.mockAllDefaults()

    await page.goto("/")

    await page.waitForURL("**/login*")
    expect(page.url()).toContain("/login")
  })

  test("login page renders password field and submit button", async ({
    page,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)

    await page.goto("/login")

    // Verify the heading
    await expect(
      page.getByRole("heading", { name: "Newsletter Aggregator" })
    ).toBeVisible()

    // Verify the descriptive text
    await expect(
      page.getByText("Enter your password to continue")
    ).toBeVisible()

    // Verify password field is visible
    const passwordField = page.getByLabel("Password")
    await expect(passwordField).toBeVisible()
    await expect(passwordField).toHaveAttribute("type", "password")

    // Verify submit button is visible
    await expect(
      page.getByRole("button", { name: "Sign in" })
    ).toBeVisible()

    // Verify there is no email or username field
    await expect(page.getByLabel("Email")).not.toBeVisible()
    await expect(page.getByLabel("Username")).not.toBeVisible()
  })

  test("submit correct password redirects to home", async ({
    page,
    apiMocks,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    await mockLoginSuccess(page)

    await page.goto("/login")

    // Fill password and submit
    await page.getByLabel("Password").fill("correct-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    // After successful login, mock session as authenticated for the redirect
    // Route registration is LIFO -- the last registered route wins.
    // Re-register session route to return authenticated after login.
    await mockSessionAuthenticated(page)
    await apiMocks.mockAllDefaults()

    await page.waitForURL("**/")
    // Should be at root, not /login
    expect(page.url()).not.toContain("/login")
  })

  test("submit wrong password shows error message", async ({ page }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    await mockLoginFailure(page)

    await page.goto("/login")

    // Fill password and submit
    await page.getByLabel("Password").fill("wrong-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    // Verify error message appears
    await expect(page.getByRole("alert")).toBeVisible()
    await expect(page.getByText("Invalid password")).toBeVisible()

    // Should still be on /login
    expect(page.url()).toContain("/login")
  })

  test("rate limited login shows too many attempts message", async ({
    page,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    await mockLoginRateLimited(page)

    await page.goto("/login")

    // Fill password and submit
    await page.getByLabel("Password").fill("any-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    // Verify rate limit error appears
    await expect(page.getByRole("alert")).toBeVisible()
    await expect(
      page.getByText("Too many attempts. Please try again later.")
    ).toBeVisible()

    // Should still be on /login
    expect(page.url()).toContain("/login")
  })

  test("Enter key submits the form", async ({ page }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    await mockLoginFailure(page)

    await page.goto("/login")

    // Fill password and press Enter (instead of clicking submit)
    await page.getByLabel("Password").fill("test-password")
    await page.getByLabel("Password").press("Enter")

    // Verify the form was submitted (error message appears for failed login)
    await expect(page.getByRole("alert")).toBeVisible()
    await expect(page.getByText("Invalid password")).toBeVisible()
  })

  test("returnTo parameter preserved after successful login", async ({
    page,
    apiMocks,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)
    await mockLoginSuccess(page)

    // Navigate to /login with a returnTo parameter
    await page.goto("/login?returnTo=/digests")

    // Fill password and submit
    await page.getByLabel("Password").fill("correct-password")
    await page.getByRole("button", { name: "Sign in" }).click()

    // After login, mock session as authenticated and set up default mocks
    await mockSessionAuthenticated(page)
    await apiMocks.mockAllDefaults()

    // Should redirect to the returnTo URL
    await page.waitForURL("**/digests*")
    expect(page.url()).toContain("/digests")
  })

  test("submit button is disabled when password field is empty", async ({
    page,
  }) => {
    await enableAuth(page)
    await mockSessionUnauthenticated(page)

    await page.goto("/login")

    // Submit button should be disabled with empty password
    const submitButton = page.getByRole("button", { name: "Sign in" })
    await expect(submitButton).toBeDisabled()

    // After typing, button should be enabled
    await page.getByLabel("Password").fill("something")
    await expect(submitButton).toBeEnabled()

    // Clearing the field should disable button again
    await page.getByLabel("Password").clear()
    await expect(submitButton).toBeDisabled()
  })
})
