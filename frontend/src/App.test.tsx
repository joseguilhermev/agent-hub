import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api";
import { App } from "./App";

vi.mock("./api", () => {
  class MockApiError extends Error {
    constructor(message: string, readonly status: number) {
      super(message);
    }
  }
  return {
    ApiError: MockApiError,
    api: {
      login: vi.fn(),
      register: vi.fn(),
      me: vi.fn(() => Promise.resolve({ id: "user-id", email: "user@example.com" })),
      logout: vi.fn(() => Promise.resolve()),
      createAgent: vi.fn(),
      requestAgent: vi.fn(),
      agents: vi.fn(),
      createConversation: vi.fn(),
      sendMessage: vi.fn(),
      sendActivity: vi.fn(),
      activities: vi.fn(),
      upload: vi.fn(),
      endConversation: vi.fn(),
    },
    hasAuthToken: vi.fn(() => true),
    setAuthToken: vi.fn(),
    streamProtocols: vi.fn(() => ["agent-hub", "token"]),
    streamUrl: vi.fn(() => "ws://example.test/stream"),
  };
});

class QuietWebSocket {
  onopen: (() => void) | null = null;
  onmessage = null;
  onclose = null;
  onerror = null;
  constructor() { setTimeout(() => this.onopen?.(), 0); }
  close() {}
}

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.stubGlobal("WebSocket", QuietWebSocket);
    Element.prototype.scrollTo = vi.fn();
  });

  it("recreates and retries a backend conversation lost after restart", async () => {
    sessionStorage.setItem("agent-hub:sessions:v1", JSON.stringify({
      support: { conversationId: "stale", messages: [] },
    }));
    vi.mocked(api.agents).mockResolvedValue([{ id: "support", name: "Support" }]);
    vi.mocked(api.createConversation).mockResolvedValue({
      id: "fresh",
      agent: { id: "support", name: "Support" },
      messages: [],
    });
    vi.mocked(api.sendMessage)
      .mockRejectedValueOnce(new ApiError("Conversation not found", 404))
      .mockResolvedValueOnce({ messages: [] });

    render(<App />);
    const agentName = await screen.findByText("Support");
    fireEvent.click(agentName.closest("button")!);
    const composer = await screen.findByLabelText("Mensagem para Support");
    fireEvent.change(composer, { target: { value: "Hello" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => expect(api.sendMessage).toHaveBeenLastCalledWith("fresh", "Hello"));
    expect(api.createConversation).toHaveBeenCalledWith("support");
    expect(composer).toHaveValue("");
  });

  it("starts a new conversation without waiting for old conversation cleanup", async () => {
    vi.mocked(api.agents).mockResolvedValue([{ id: "support", name: "Support" }]);
    vi.mocked(api.createConversation)
      .mockResolvedValueOnce({
        id: "first",
        agent: { id: "support", name: "Support" },
        messages: [],
      })
      .mockResolvedValueOnce({
        id: "second",
        agent: { id: "support", name: "Support" },
        messages: [],
      });
    vi.mocked(api.endConversation).mockReturnValue(new Promise(() => undefined));

    render(<App />);
    fireEvent.click((await screen.findByText("Support")).closest("button")!);
    await screen.findByLabelText("Mensagem para Support");
    fireEvent.click(screen.getByRole("button", { name: "Nova conversa" }));

    await waitFor(() => expect(api.createConversation).toHaveBeenCalledTimes(2));
    expect(api.endConversation).toHaveBeenCalledWith("first");
  });

  it("lets a user request a new agent", async () => {
    vi.mocked(api.agents).mockResolvedValue([]);
    vi.mocked(api.requestAgent).mockResolvedValue({
      id: "request-id", user_id: "user-id", user_email: "user@example.com",
      name: "Analista de contratos", reason: "Revisar contratos", status: "pending", created_at: 1,
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Solicitar novo agente" }));
    fireEvent.change(screen.getByLabelText("Nome ou função do agente"), { target: { value: "Analista de contratos" } });
    fireEvent.change(screen.getByLabelText("Como ele ajudaria você?"), { target: { value: "Revisar contratos" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar solicitação" }));

    await screen.findByText("Seu pedido está em análise");
    expect(api.requestAgent).toHaveBeenCalledWith("Analista de contratos", "Revisar contratos");
  });
});
