import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/v1/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "token-123",
        token_type: "bearer",
        expires_in: 3600,
        idle_timeout_in: 900,
        user: {
          id: "user-1",
          email: "traveler@example.com",
        },
      }),
    });
  });

  await page.route("**/api/v1/chat", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "session-remote",
        message_id: "message-2",
        assistant_message: "Great choice. Top picks: details below",
        recommendations: [
          {
            item_id: "dest-lisbon",
            item_type: "destination",
            score: 0.94,
            rank: 1,
            explanation: "Culture and food fit.",
            metadata: {
              name: "Lisbon",
              city: "Lisbon",
              map_url: "https://example.com/map",
            },
          },
        ],
        state: {},
      }),
    });
  });

  await page.route("**/api/v1/chat/*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "session-remote",
        state: {},
        messages: [],
        recommendations: [],
      }),
    });
  });
});

test("planner route redirects to login, then logs in and completes one chat turn", async ({
  page,
}) => {
  await page.goto("/planner");

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Pick up your next trip where you left it." })).toBeVisible();

  await page.getByLabel("Email").fill("traveler@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Enter the planner" }).click();

  await expect(page).toHaveURL(/\/planner$/);
  await expect(page.getByText("Start with a trip idea")).toBeVisible();

  await page.getByLabel("Message input").fill("Plan Lisbon for me");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Great choice.")).toBeVisible();
  await expect(page.getByText("Recommended options")).toBeVisible();
  await expect(page.getByText("Lisbon").first()).toBeVisible();
});
