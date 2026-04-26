import { expect, type Page, test } from "@playwright/test";

interface LiveRecommendation {
  item_id: string;
  item_type: string;
  rank: number;
  metadata?: Record<string, unknown>;
}

interface LiveChatResponse {
  assistant_message: string;
  recommendations: LiveRecommendation[];
  state?: Record<string, unknown>;
}

const livePlannerEnabled = process.env.LIVE_PLANNER === "1";
const authMode = process.env.LIVE_PLANNER_AUTH_MODE ?? "enabled";
const providerMode = process.env.LIVE_PLANNER_PROVIDER ?? "disabled";
const email =
  process.env.LIVE_PLANNER_EMAIL ??
  `planner-live-${Date.now()}@example.com`;
const password = process.env.LIVE_PLANNER_PASSWORD ?? "PlannerLive123!1";
const plannerPrompt =
  process.env.LIVE_PLANNER_PROMPT ??
  "Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 under 2000 USD";

test.skip(
  !livePlannerEnabled,
  "Live planner verification only runs when LIVE_PLANNER=1 is set.",
);
test.setTimeout(providerMode === "ollama" ? 180_000 : 90_000);

function recommendationName(item: LiveRecommendation): string {
  const candidate = item.metadata?.name ?? item.metadata?.title;
  return typeof candidate === "string" && candidate.trim()
    ? candidate
    : item.item_id;
}

async function authenticate(page: Page) {
  if (authMode === "disabled") {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "traveltom-session",
        JSON.stringify({
          state: {
            authToken: "auth-disabled-live-planner",
            sessionId: `session-live-${crypto.randomUUID()}`,
            hasRemoteSession: false,
          },
          version: 0,
        }),
      );
    });
    await page.goto("/planner");
    await expect(page).toHaveURL(/\/planner$/);
    return;
  }

  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/^Password$/).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Start planning" }).click();

  await Promise.race([
    page.waitForURL(/\/planner$/),
    page.getByRole("alert").waitFor({ state: "visible" }),
  ]);

  if (page.url().endsWith("/planner")) {
    return;
  }

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Enter the planner" }).click();
  await expect(page).toHaveURL(/\/planner$/);
}

async function sendPlannerMessage(
  page: Page,
  message: string,
): Promise<LiveChatResponse> {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/chat") &&
      response.request().method() === "POST",
    { timeout: providerMode === "ollama" ? 120_000 : 75_000 },
  );

  await page.getByLabel("Message input").fill(message);
  await page.getByRole("button", { name: "Send" }).click();

  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as LiveChatResponse;
}

async function expectLatestCards(page: Page, response: LiveChatResponse) {
  const recommendations = response.recommendations ?? [];
  expect(recommendations.length).toBeGreaterThan(0);

  await expectAssistantMessage(page, response);
  await expect(page.getByText("Current Picks")).toBeVisible();
  await expect(
    page
      .getByText(`${recommendations.length} current candidates from this turn`)
      .first(),
  ).toBeVisible();

  await expect(
    page.getByText(recommendationName(recommendations[0])).first(),
  ).toBeVisible();
}

async function expectAssistantMessage(page: Page, response: LiveChatResponse) {
  const firstLine = response.assistant_message.split(/\n| Top picks:/)[0];
  await expect(
    page.locator(".chat-message-content", { hasText: firstLine }).last(),
  ).toBeVisible();
}

test("planner UI verifies live backend recommendation and follow-up continuity", async ({
  page,
}) => {
  await authenticate(page);
  await expect(page.getByText("Start with a trip idea")).toBeVisible();

  const initialResponse = await sendPlannerMessage(page, plannerPrompt);
  await expectLatestCards(page, initialResponse);

  const firstInitialName = recommendationName(initialResponse.recommendations[0]);
  const followUpResponse = await sendPlannerMessage(page, "show me more");

  await expectAssistantMessage(page, followUpResponse);
  expect(followUpResponse.state?.conversation).toBeTruthy();

  if (followUpResponse.recommendations.length > 0) {
    await expectLatestCards(page, followUpResponse);
  } else {
    await expect(
      page.locator(".recommendations-panel .recommendation-card", {
        hasText: firstInitialName,
      }),
    ).toHaveCount(0);
  }
});
