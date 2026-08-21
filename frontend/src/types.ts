export interface Agent {
  id: string;
  name: string;
}

export interface AgentRequest {
  id: string;
  user_id: string;
  user_email: string;
  name: string;
  reason: string;
  status: "pending" | "fulfilled" | "rejected";
  created_at: number;
}

export interface User {
  id: string;
  email: string;
  role: "admin" | "user";
}

export interface AdminUser extends User {
  agent_ids: string[];
}

export interface AgentUsageSummary {
  agent_id: string;
  agent_name: string;
  conversations: number;
  interactions: number;
  users: number;
  input_chars: number;
  output_items: number;
  attachment_count: number;
  attachment_bytes: number;
  average_duration_ms: number;
  last_used_at?: number;
}

export interface AgentUsageEvent {
  id: number;
  agent_id: string;
  agent_name: string;
  user_email: string;
  conversation_id?: string;
  event_type: "conversation" | "message" | "activity" | "attachment";
  input_chars: number;
  output_items: number;
  attachment_count: number;
  attachment_bytes: number;
  duration_ms: number;
  created_at: number;
}

export interface UsageDashboard {
  days: number;
  total_conversations: number;
  total_interactions: number;
  active_users: number;
  input_chars: number;
  output_items: number;
  attachment_bytes: number;
  agents: AgentUsageSummary[];
  recent: AgentUsageEvent[];
}

export interface AuthResponse {
  token: string;
  token_type: "bearer";
  user: User;
}

export interface Attachment {
  contentType?: string;
  contentUrl?: string;
  name?: string;
  size?: number;
  content?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface CardAction {
  type: string;
  title?: string;
  value?: unknown;
  image?: string;
  [key: string]: unknown;
}

export interface Activity {
  id?: string;
  type: string;
  text?: string;
  name?: string;
  timestamp?: string;
  from?: { id?: string; name?: string; role?: string };
  value?: unknown;
  attachments?: Attachment[];
  suggestedActions?: { actions?: CardAction[] };
  inputHint?: string;
  [key: string]: unknown;
}

export interface Conversation {
  id: string;
  agent: Agent;
  messages: Activity[];
}

export interface ActivitySet {
  activities: Activity[];
  watermark?: string;
}

export interface LocalMessage extends Activity {
  localId: string;
  role: "agent" | "user" | "system";
  status?: "sending" | "sent" | "failed";
  streaming?: boolean;
}
