import { test, expect } from "@playwright/test";

/**
 * Sanity E2E — codified version of the manual QA-only sweep
 * (docs/qa/2026-05-04-qa-report.md). Five journeys, all backend-free.
 *
 * Brand-strip rule (spec docs/superpowers/specs/2026-05-04-subject-canonical-tree.md §6):
 * the strings "Springboard", "Academy", "RBSE", "NCERT" must NEVER appear
 * in any student-facing route. Admin routes are exempt by design.
 */

const STUDENT_BRAND_LEAKS = ["Springboard", "Academy", "RBSE", "NCERT"];

test.describe("J1 /chat empty state", () => {
  test("shows the four starter prompts and brand-free scope options", async ({ page }) => {
    await page.goto("/chat");

    // The assistant intro
    await expect(page.getByRole("heading", { name: /Ask anything/i })).toBeVisible();

    // Four example prompts — pinned in /chat empty state
    await expect(page.getByRole("button", { name: /Why is Aravalli called the planning region/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /What is Mawath rainfall\?/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Which districts have arid climate per Koppen\?/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Name the highest peak of Aravalli with its district/i })).toBeVisible();

    // Send button must be disabled when textarea is empty
    const sendButton = page.getByRole("button", { name: "Send" });
    await expect(sendButton).toBeDisabled();

    // Scope dropdown — brand-free labels per spec
    const scope = page.getByRole("combobox", { name: /Scope/i });
    await expect(scope).toBeVisible();
    const optionTexts = await scope.locator("option").allTextContents();
    expect(optionTexts).toEqual(["All subjects", "Current subject", "Current selection"]);

    await assertNoBrandLeak(page);
  });
});

test.describe("J2 /library index", () => {
  test("renders one subject card and click navigates to the subject page", async ({ page }) => {
    await page.goto("/library");

    const card = page.getByRole("link", { name: /Rajasthan Geography/i });
    await expect(card).toBeVisible();

    await assertNoBrandLeak(page);

    await card.click();
    await expect(page).toHaveURL(/\/library\/rajasthan_geography/);
  });
});

test.describe("J3 /library/rajasthan_geography canvas", () => {
  test("renders without brand leaks (radial canvas central node, header)", async ({ page }) => {
    await page.goto("/library/rajasthan_geography");

    // Header pill should show the brand-free subject name
    await expect(page.getByText("Rajasthan Geography").first()).toBeVisible();

    // Wait for client hydration of the radial canvas
    await page.waitForLoadState("networkidle");

    await assertNoBrandLeak(page);
  });

  test("legacy book-keyed slug redirects to subject-canonical", async ({ page }) => {
    const resp = await page.goto("/library/springboard_rajasthan_geography");
    await expect(page).toHaveURL(/\/library\/rajasthan_geography$/);
    expect(resp?.status()).toBeLessThan(400);
  });

  test("unknown slug falls back to /library", async ({ page }) => {
    await page.goto("/library/this-slug-does-not-exist");
    await expect(page).toHaveURL(/\/library\/?$/);
  });
});

test.describe("J4 /tests new-test modal", () => {
  test("opens the modal, lists leaves, breadcrumb has no subject duplication", async ({ page }) => {
    await page.goto("/tests");

    // Empty state has two "New test" buttons (header + EmptyState card).
    // The header one inside <main> doesn't get role=banner; both open the
    // same modal so click whichever the locator hits first.
    await page.getByRole("button", { name: "New test" }).first().click();

    await expect(page.getByText(/Generate a mock test/i)).toBeVisible();

    // The modal lists leaves; we expect at least 10 (Springboard book has 34)
    const leafButtons = page.locator('button[type="button"]:has(p.font-medium)');
    await expect(leafButtons.first()).toBeVisible();
    expect(await leafButtons.count()).toBeGreaterThanOrEqual(10);

    // Breadcrumb dedup — the first leaf row's secondary line must NOT
    // start with two consecutive "Rajasthan Geography" tokens.
    const firstSecondaryLine = await leafButtons.first().locator("p.text-\\[11px\\]").textContent();
    expect(firstSecondaryLine).toBeTruthy();
    expect(firstSecondaryLine!.startsWith("Rajasthan Geography · Rajasthan Geography")).toBeFalsy();

    await assertNoBrandLeak(page);
  });
});

test.describe("J5 Sidebar collapse persistence", () => {
  test("collapse state survives a page reload (localStorage-backed)", async ({ page }) => {
    await page.goto("/chat");

    // Initial state: expanded — verify by presence of nav label text
    await expect(page.getByRole("link", { name: "Chat" })).toBeVisible();

    // Click the collapse toggle (aria-label = "Collapse sidebar")
    await page.getByRole("button", { name: "Collapse sidebar" }).click();

    // After collapse: the toggle becomes "Expand sidebar"
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();

    // Verify localStorage
    const flag = await page.evaluate(() =>
      window.localStorage.getItem("gemma-tutor-sidebar-collapsed"),
    );
    expect(flag).toBe("1");

    // Reload — should remain collapsed
    await page.reload();
    await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
  });
});

/**
 * Spec rule: zero brand strings in any student-facing route.
 * Admin routes (/admin/ingest) intentionally retain publisher placeholders,
 * so this helper is only invoked from non-admin journeys.
 */
async function assertNoBrandLeak(page: import("@playwright/test").Page) {
  const body = await page.locator("body").innerText();
  for (const brand of STUDENT_BRAND_LEAKS) {
    expect(body, `student-facing route contains forbidden brand string "${brand}"`).not.toContain(brand);
  }
}
