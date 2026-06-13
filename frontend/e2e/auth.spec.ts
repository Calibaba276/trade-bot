import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("renders the GLASS BOX wordmark", async ({ page }) => {
    await expect(page.getByText("GLASS BOX")).toBeVisible();
  });

  test("has an email and password input", async ({ page }) => {
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
    await expect(page.getByPlaceholder(/password/i)).toBeVisible();
  });

  test("has an authenticate submit button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /authenticate/i }),
    ).toBeVisible();
  });

  test("shows the NGT session clock", async ({ page }) => {
    // The clock label is the trading session name (e.g. ASIAN, LONDON, NY, OFF-HOURS)
    const sessionLabel = page.locator("text=/ASIAN|LONDON|NY|PRE-LONDON|OVERLAP|OFF-HOURS/");
    await expect(sessionLabel).toBeVisible();
  });

  test("preserves entered credentials after typing", async ({ page }) => {
    await page.getByPlaceholder(/email/i).fill("trader@example.com");
    await page.getByPlaceholder(/password/i).fill("hunter2");
    await expect(page.getByPlaceholder(/email/i)).toHaveValue("trader@example.com");
    await expect(page.getByPlaceholder(/password/i)).toHaveValue("hunter2");
  });
});

test.describe("Sign up page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/signup");
  });

  test("renders the GLASS BOX wordmark", async ({ page }) => {
    await expect(page.getByText("GLASS BOX")).toBeVisible();
  });

  test("has email, password and confirm password fields", async ({ page }) => {
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
    const passwordFields = page.getByPlaceholder(/password/i);
    await expect(passwordFields).toHaveCount(2);
  });

  test("has a create account submit button", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /create account/i }),
    ).toBeVisible();
  });
});

test.describe("Unauthenticated redirect", () => {
  test("redirects / to /login when not signed in", async ({ page }) => {
    await page.goto("/");
    await page.waitForURL("**/login");
    expect(page.url()).toContain("/login");
  });
});
