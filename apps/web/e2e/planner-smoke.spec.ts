import { expect, type Page, test } from "@playwright/test";

async function stubSharedRoutes(page: Page) {
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
}

async function loginToPlanner(page: Page) {
  await page.goto("/planner");

  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Pick up your next trip where you left it." }),
  ).toBeVisible();

  await page.getByLabel("Email").fill("traveler@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Enter the planner" }).click();

  await expect(page).toHaveURL(/\/planner$/);
  await expect(page.getByText("Start with a trip idea")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await stubSharedRoutes(page);
});

test("planner route redirects to login, then logs in and completes one chat turn", async ({
  page,
}) => {
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
            item_id: "activity-lisbon-1",
            item_type: "activity",
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

  await loginToPlanner(page);

  await page.getByLabel("Message input").fill("Plan Lisbon for me");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Great choice.")).toBeVisible();
  await expect(page.getByText("Recommended options")).toBeVisible();
  await expect(page.getByText("Lisbon").first()).toBeVisible();
});

test("planner retries a failed chat turn without duplicating the user message", async ({
  page,
}) => {
  let chatAttempts = 0;

  await page.route("**/api/v1/chat", async (route) => {
    chatAttempts += 1;

    if (chatAttempts === 1) {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "chat_processing_failed",
            message: "Failed to process chat message",
            trace_id: "trace-retry-1",
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "session-remote",
        message_id: "message-2",
        assistant_message: "Recovered response",
        recommendations: [],
        state: {},
      }),
    });
  });

  await loginToPlanner(page);

  await page.getByLabel("Message input").fill("Need hotels");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByRole("alert")).toContainText("Failed to process chat message");
  await page.getByRole("button", { name: "Retry last message" }).click();

  await expect(page.getByText("Recovered response")).toBeVisible();
  await expect(page.locator(".chat-message-content", { hasText: "Need hotels" })).toHaveCount(1);
  expect(chatAttempts).toBe(2);
});
