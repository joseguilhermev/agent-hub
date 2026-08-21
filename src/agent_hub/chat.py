import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from agent_hub.config import AgentConfig
from agent_hub.database import Database
from agent_hub.directline import DirectLineClient
from agent_hub.schemas import (
    Activity,
    ActivitySet,
    Agent,
    Conversation,
    MessageResponse,
)


@dataclass
class ConversationState:
    agent: AgentConfig
    directline_id: str
    token: str = field(repr=False)
    user_id: str
    owner_id: str | None = None
    watermark: str | None = None
    expires_at: float | None = None
    lock: Lock = field(default_factory=Lock)


class ChatService:
    def __init__(
        self,
        agents: list[AgentConfig] | None = None,
        database: Database | None = None,
    ) -> None:
        self.database = database
        self.agents = {agent.id: agent for agent in (agents or [])}
        self.conversations: dict[str, ConversationState] = {}
        self._lock = Lock()

    def create_conversation(
        self, agent_id: str, user_name: str, owner_id: str | None = None
    ) -> Conversation:
        agent = self._get_agent(agent_id, owner_id)
        if agent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

        user_id = f"dl_{uuid4().hex}"
        client = DirectLineClient(agent.secret)
        token_data = client.generate_token(user_id, user_name)
        directline = client.start_conversation(str(token_data["token"]))
        expires_in = directline.get("expires_in")
        state = ConversationState(
            agent=agent,
            directline_id=str(directline["conversationId"]),
            token=str(directline["token"]),
            user_id=user_id,
            owner_id=owner_id,
            expires_at=(
                time.monotonic() + float(expires_in)
                if expires_in is not None
                else None
            ),
        )
        client.send_start_conversation_event(
            state.directline_id, state.token, state.user_id
        )
        greeting = self._wait_for_messages(client, state, timeout=5)

        conversation_id = uuid4().hex
        with self._lock:
            self.conversations[conversation_id] = state
        result = Conversation(
            id=conversation_id,
            agent=Agent(id=agent.id, name=agent.name),
            messages=self._to_activities(greeting),
        )
        self._record_usage(
            agent.id, owner_id, conversation_id, "conversation",
            output_items=len(result.messages),
        )
        return result

    def send_message(
        self,
        conversation_id: str,
        text: str,
        owner_id: str | None = None,
        timeout: float = 30,
    ) -> MessageResponse:
        state = self.get_conversation(conversation_id, owner_id)

        started_at = time.monotonic()
        client = DirectLineClient(state.agent.secret)
        with state.lock:
            self._refresh_token(client, state)
            client.send_message(
                state.directline_id, state.token, state.user_id, text
            )
            activities = self._wait_for_messages(client, state, timeout)

        result = MessageResponse(messages=self._to_activities(activities))
        self._record_usage(
            state.agent.id, owner_id, conversation_id, "message",
            input_chars=len(text), output_items=len(result.messages),
            duration_ms=round((time.monotonic() - started_at) * 1000),
        )
        return result

    def send_activity(
        self,
        conversation_id: str,
        activity: dict[str, Any],
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        state = self.get_conversation(conversation_id, owner_id)
        payload = dict(activity)
        payload["from"] = {"id": state.user_id}
        client = DirectLineClient(state.agent.secret)
        with state.lock:
            self._refresh_token(client, state)
            result = client.send_activity(
                state.directline_id, state.token, payload
            )
        self._record_usage(
            state.agent.id, owner_id, conversation_id, "activity",
            input_chars=len(str(activity.get("text") or "")),
        )
        return result

    def get_activities(
        self,
        conversation_id: str,
        watermark: str | None = None,
        owner_id: str | None = None,
    ) -> ActivitySet:
        state = self.get_conversation(conversation_id, owner_id)
        client = DirectLineClient(state.agent.secret)
        with state.lock:
            self._refresh_token(client, state)
            result = client.get_activities(
                state.directline_id,
                state.token,
                watermark if watermark is not None else state.watermark,
            )
            if result.get("watermark") is not None:
                state.watermark = str(result["watermark"])
        return ActivitySet(
            activities=self._to_activities(
                [
                    activity
                    for activity in result.get("activities", [])
                    if activity.get("from", {}).get("id") != state.user_id
                ]
            ),
            watermark=result.get("watermark"),
        )

    def upload_files(
        self,
        conversation_id: str,
        files: list[tuple[str, bytes, str]],
        text: str | None = None,
        owner_id: str | None = None,
        timeout: float = 120,
    ) -> MessageResponse:
        state = self.get_conversation(conversation_id, owner_id)
        started_at = time.monotonic()
        client = DirectLineClient(state.agent.secret)
        activity = (
            {"type": "message", "from": {"id": state.user_id}, "text": text}
            if text
            else None
        )
        with state.lock:
            self._refresh_token(client, state)
            client.upload_files(
                state.directline_id,
                state.token,
                state.user_id,
                files,
                activity,
            )
            activities = self._wait_for_messages(client, state, timeout)
        result = MessageResponse(messages=self._to_activities(activities))
        self._record_usage(
            state.agent.id, owner_id, conversation_id, "attachment",
            input_chars=len(text or ""), output_items=len(result.messages),
            attachment_count=len(files),
            attachment_bytes=sum(len(content) for _, content, _ in files),
            duration_ms=round((time.monotonic() - started_at) * 1000),
        )
        return result

    def _record_usage(
        self, agent_id: str, owner_id: str | None, conversation_id: str,
        event_type: str, *, input_chars: int = 0, output_items: int = 0,
        attachment_count: int = 0, attachment_bytes: int = 0,
        duration_ms: int = 0,
    ) -> None:
        if self.database is None or owner_id is None:
            return
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO agent_usage
                   (agent_id, user_id, conversation_id, event_type, input_chars,
                    output_items, attachment_count, attachment_bytes, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, owner_id, conversation_id, event_type, input_chars,
                 output_items, attachment_count, attachment_bytes, duration_ms),
            )

    def get_stream_url(self, conversation_id: str, owner_id: str | None = None) -> str:
        state = self.get_conversation(conversation_id, owner_id)
        client = DirectLineClient(state.agent.secret)
        with state.lock:
            self._refresh_token(client, state)
            result = client.reconnect(
                state.directline_id, state.token, state.watermark
            )
            if result.get("token"):
                state.token = str(result["token"])
        return str(result["streamUrl"])

    def update_watermark(
        self, conversation_id: str, watermark: str, owner_id: str | None = None
    ) -> None:
        self.get_conversation(conversation_id, owner_id).watermark = watermark

    def end_conversation(self, conversation_id: str, owner_id: str | None = None) -> None:
        state = self.get_conversation(conversation_id, owner_id)
        client = DirectLineClient(state.agent.secret)
        with state.lock:
            self._refresh_token(client, state)
            client.send_activity(
                state.directline_id,
                state.token,
                {"type": "endOfConversation", "from": {"id": state.user_id}},
            )
        with self._lock:
            self.conversations.pop(conversation_id, None)

    def get_conversation(
        self, conversation_id: str, owner_id: str | None = None
    ) -> ConversationState:
        state = self.conversations.get(conversation_id)
        if state is None or (owner_id is not None and state.owner_id != owner_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        return state

    def _get_agent(self, agent_id: str, owner_id: str | None) -> AgentConfig | None:
        if self.database is None:
            return self.agents.get(agent_id)
        if owner_id is None:
            return None
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT agents.id, agents.name, agents.encrypted_secret
                   FROM agents JOIN user_agents ON user_agents.agent_id = agents.id
                   WHERE agents.id = ? AND user_agents.user_id = ?""",
                (agent_id, owner_id),
            ).fetchone()
        if row is None:
            return None
        return AgentConfig(
            id=row["id"],
            name=row["name"],
            secret=self.database.decrypt(row["encrypted_secret"]),
        )

    @staticmethod
    def _to_activities(activities: list[dict[str, Any]]) -> list[Activity]:
        return [
            Activity.model_validate(activity)
            for activity in activities
            if activity.get("type")
        ]

    @staticmethod
    def _refresh_token(
        client: DirectLineClient,
        state: ConversationState,
    ) -> None:
        if state.expires_at is None or time.monotonic() < state.expires_at - 300:
            return
        result = client.refresh_token(state.token)
        state.token = str(result["token"])
        expires_in = result.get("expires_in")
        state.expires_at = (
            time.monotonic() + float(expires_in)
            if expires_in is not None
            else None
        )

    @staticmethod
    def _wait_for_messages(
        client: DirectLineClient,
        state: ConversationState,
        timeout: float,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        received: list[dict[str, Any]] = []
        last_activity_at: float | None = None

        while time.monotonic() < deadline:
            activity_set = client.get_activities(
                state.directline_id, state.token, state.watermark
            )
            if activity_set.get("watermark") is not None:
                state.watermark = str(activity_set["watermark"])

            new_activities = [
                activity
                for activity in activity_set.get("activities", [])
                if activity.get("from", {}).get("id") != state.user_id
            ]
            if new_activities:
                received.extend(new_activities)
                if any(
                    activity.get("type") not in {"event", "typing"}
                    for activity in new_activities
                ):
                    last_activity_at = time.monotonic()
            if any(
                activity.get("type") == "endOfConversation"
                or (
                    activity.get("type") == "event"
                    and activity.get("name") == "turn.complete"
                )
                for activity in new_activities
            ):
                break
            if last_activity_at and time.monotonic() - last_activity_at >= 0.75:
                break
            time.sleep(0.5)

        return received
