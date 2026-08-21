import { expect, test } from "@playwright/test";

const agents = [
  { id: "support", name: "Support" },
  { id: "sales", name: "Sales" },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("agent-hub:token", "test-token");
    class QuietWebSocket {
      static OPEN = 1;
      readyState = 1;
      onopen: (() => void) | null = null;
      onmessage = null;
      onclose = null;
      onerror = null;
      constructor() { setTimeout(() => this.onopen?.(), 0); }
      close() {}
      send() {}
      addEventListener() {}
      removeEventListener() {}
    }
    Object.defineProperty(window, "WebSocket", { value: QuietWebSocket });
  });
  await page.route("**/auth/me", (route) => route.fulfill({ json: { id: "user-id", email: "user@example.com", role: "user" } }));
  await page.route("**/agents", (route) => route.fulfill({ json: agents }));
  await page.route("**/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const body = route.request().postDataJSON();
    const agent = agents.find((item) => item.id === body.agent_id)!;
    await route.fulfill({
      status: 201,
      json: {
        id: `${agent.id}-conversation`,
        agent,
        messages: [{ id: "greeting", type: "message", text: "Como posso ajudar?", timestamp: "2026-08-20T13:00:00Z" }],
      },
    });
  });
});

test("selects an agent and opens a conversation", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Escolha um agente" })).toBeVisible();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Escolher um agente" }).click();
  }
  await page.getByRole("button", { name: /support disponível/i }).click();
  await expect(page.getByText("Como posso ajudar?")).toBeVisible();
  await expect(page.getByLabel("Mensagem para Support")).toBeVisible();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `test-results/${testInfo.project.name}-conversation.png`, fullPage: true });
});
