import type { Activity, ActivitySet, AdminUser, Agent, AgentRequest, AuthResponse, Conversation, UsageDashboard, User } from "./types";

const TOKEN_KEY = "agent-hub:token";
let token = sessionStorage.getItem(TOKEN_KEY);

export function setAuthToken(value?: string) {
  token = value ?? null;
  if (value) sessionStorage.setItem(TOKEN_KEY, value);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export function hasAuthToken(): boolean {
  return Boolean(token);
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? `Falha na solicitação (${response.status})`, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  register: (email: string, password: string) =>
    request<AuthResponse>("/auth/register", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  agents: () => request<Agent[]>("/agents"),
  agentRequests: () => request<AgentRequest[]>("/agents/requests"),
  requestAgent: (name: string, reason: string) =>
    request<AgentRequest>("/agents/requests", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, reason }),
    }),
  createAgent: (name: string, secret: string) =>
    request<Agent>("/agents", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, secret }),
    }),
  adminUsers: () => request<AdminUser[]>("/admin/users"),
  adminAgents: () => request<Agent[]>("/admin/agents"),
  adminAgentRequests: () => request<AgentRequest[]>("/admin/agent-requests"),
  updateAgentRequest: (requestId: string, status: "fulfilled" | "rejected") =>
    request<AgentRequest>(`/admin/agent-requests/${requestId}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  adminUsage: (days = 30) => request<UsageDashboard>(`/admin/usage?days=${days}`),
  assignAgents: (userId: string, agentIds: string[]) =>
    request<AdminUser>(`/admin/users/${userId}/agents`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_ids: agentIds }),
    }),
  createConversation: (agentId: string, userName = "Usuário do Agent Hub") =>
    request<Conversation>("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, user_name: userName }),
    }),
  sendMessage: (conversationId: string, text: string) =>
    request<{ messages: Activity[] }>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
  sendActivity: (conversationId: string, activity: Activity) =>
    request<{ id: string }>(`/conversations/${conversationId}/activities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activity),
    }),
  activities: (conversationId: string, watermark?: string) => {
    const query = watermark ? `?watermark=${encodeURIComponent(watermark)}` : "";
    return request<ActivitySet>(`/conversations/${conversationId}/activities${query}`);
  },
  upload: (conversationId: string, files: File[], text?: string) => {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    if (text) body.append("text", text);
    return request<{ messages: Activity[] }>(
      `/conversations/${conversationId}/attachments`,
      { method: "POST", body },
    );
  },
  endConversation: (conversationId: string) =>
    request<void>(`/conversations/${conversationId}`, { method: "DELETE" }),
};

export function streamUrl(conversationId: string): string {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/conversations/${conversationId}/stream`;
}

export function streamProtocols(): string[] {
  return ["agent-hub", token ?? "missing"];
}
