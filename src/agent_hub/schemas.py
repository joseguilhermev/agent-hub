from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import EmailStr


class Agent(BaseModel):
    id: str
    name: str


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    secret: str = Field(min_length=1, max_length=2_000)


class AgentRequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2_000)


class AgentRequest(BaseModel):
    id: str
    user_id: str
    user_email: EmailStr
    name: str
    reason: str
    status: str
    created_at: int


class AgentRequestUpdate(BaseModel):
    status: str = Field(pattern="^(fulfilled|rejected)$")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1_000)


class User(BaseModel):
    id: str
    email: EmailStr
    role: str


class AdminUser(User):
    agent_ids: list[str] = Field(default_factory=list)


class AgentAssignment(BaseModel):
    agent_ids: list[str]


class AgentUsageSummary(BaseModel):
    agent_id: str
    agent_name: str
    conversations: int
    interactions: int
    users: int
    input_chars: int
    output_items: int
    attachment_count: int
    attachment_bytes: int
    average_duration_ms: int
    last_used_at: int | None


class AgentUsageEvent(BaseModel):
    id: int
    agent_id: str
    agent_name: str
    user_email: EmailStr
    conversation_id: str | None
    event_type: str
    input_chars: int
    output_items: int
    attachment_count: int
    attachment_bytes: int
    duration_ms: int
    created_at: int


class UsageDashboard(BaseModel):
    days: int
    total_conversations: int
    total_interactions: int
    active_users: int
    input_chars: int
    output_items: int
    attachment_bytes: int
    agents: list[AgentUsageSummary]
    recent: list[AgentUsageEvent]


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: User


class ConversationCreate(BaseModel):
    agent_id: str
    user_name: str = Field(default="Agent Hub user", min_length=1, max_length=200)


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class Activity(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: str
    text: str | None = None
    name: str | None = None
    value: Any = None
    channel_data: Any = Field(default=None, alias="channelData")
    suggested_actions: dict[str, Any] | None = Field(
        default=None, alias="suggestedActions"
    )
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ActivityCreate(Activity):
    type: str = Field(min_length=1)


class Conversation(BaseModel):
    id: str
    agent: Agent
    messages: list[Activity] = Field(default_factory=list)


class MessageResponse(BaseModel):
    messages: list[Activity]


class ActivityResponse(BaseModel):
    id: str


class ActivitySet(BaseModel):
    activities: list[Activity] = Field(default_factory=list)
    watermark: str | None = None
