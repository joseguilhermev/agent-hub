import time
import unittest
from unittest.mock import Mock, patch

from agent_hub.chat import ChatService, ConversationState
from agent_hub.config import AgentConfig


class ChatServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AgentConfig(id="agent", name="Agent", secret="secret")
        self.service = ChatService([self.agent])
        self.state = ConversationState(
            agent=self.agent,
            directline_id="directline-id",
            token="token",
            user_id="dl_user",
        )
        self.service.conversations["conversation"] = self.state

    @patch("agent_hub.chat.DirectLineClient")
    def test_generic_activity_preserves_payload_and_controls_sender(
        self, client_type: Mock
    ) -> None:
        client = client_type.return_value
        client.send_activity.return_value = {"id": "activity-id"}
        activity = {
            "type": "invoke",
            "name": "adaptiveCard/action",
            "value": {"action": {"type": "Action.Execute"}},
            "channelData": {"custom": True},
            "from": {"id": "spoofed"},
        }

        result = self.service.send_activity("conversation", activity)

        self.assertEqual(result, {"id": "activity-id"})
        sent = client.send_activity.call_args.args[2]
        self.assertEqual(sent["from"], {"id": "dl_user"})
        self.assertEqual(sent["value"], activity["value"])
        self.assertEqual(sent["channelData"], activity["channelData"])

    @patch("agent_hub.chat.DirectLineClient")
    def test_expiring_token_is_refreshed(self, client_type: Mock) -> None:
        client = client_type.return_value
        client.refresh_token.return_value = {
            "token": "new-token",
            "expires_in": 1800,
        }
        client.get_activities.return_value = {
            "activities": [],
            "watermark": "1",
        }
        self.state.expires_at = time.monotonic()

        result = self.service.get_activities("conversation")

        client.refresh_token.assert_called_once_with("token")
        self.assertEqual(self.state.token, "new-token")
        self.assertEqual(result.watermark, "1")

    @patch("agent_hub.chat.DirectLineClient")
    def test_reconnect_returns_private_stream_url(self, client_type: Mock) -> None:
        client = client_type.return_value
        client.reconnect.return_value = {
            "token": "reconnected-token",
            "streamUrl": "wss://example.test/stream",
        }

        result = self.service.get_stream_url("conversation")

        self.assertEqual(result, "wss://example.test/stream")
        self.assertEqual(self.state.token, "reconnected-token")

    @patch("agent_hub.chat.DirectLineClient")
    def test_end_conversation_forwards_activity_and_removes_state(
        self, client_type: Mock
    ) -> None:
        client = client_type.return_value

        self.service.end_conversation("conversation")

        activity = client.send_activity.call_args.args[2]
        self.assertEqual(activity["type"], "endOfConversation")
        self.assertNotIn("conversation", self.service.conversations)

    def test_rich_activity_is_not_reduced(self) -> None:
        activity = {
            "type": "message",
            "text": "Choose",
            "speak": "Choose an option",
            "inputHint": "expectingInput",
            "suggestedActions": {
                "actions": [{"type": "imBack", "title": "Yes", "value": "yes"}]
            },
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {"type": "AdaptiveCard", "version": "1.5"},
                }
            ],
        }

        result = self.service._to_activities([activity])[0].model_dump(
            by_alias=True
        )

        self.assertEqual(result["speak"], activity["speak"])
        self.assertEqual(result["inputHint"], activity["inputHint"])
        self.assertEqual(result["suggestedActions"], activity["suggestedActions"])
        self.assertEqual(result["attachments"], activity["attachments"])

    @patch("agent_hub.chat.DirectLineClient")
    def test_polling_hides_the_server_controlled_user_activity(
        self, client_type: Mock
    ) -> None:
        client_type.return_value.get_activities.return_value = {
            "activities": [
                {"id": "user", "type": "message", "from": {"id": "dl_user"}},
                {"id": "agent", "type": "message", "from": {"id": "bot"}},
            ],
            "watermark": "2",
        }

        result = self.service.get_activities("conversation")

        self.assertEqual([activity.id for activity in result.activities], ["agent"])


if __name__ == "__main__":
    unittest.main()
