import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, WebSocketDisconnect, status
from fastapi.testclient import TestClient

from agent_hub.api import app
from agent_hub.auth import AuthenticatedUser
from agent_hub.dependencies import get_current_user, get_service
from agent_hub.schemas import ActivitySet, MessageResponse


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = Mock()
        self.service.agents = {}
        app.dependency_overrides[get_service] = lambda: self.service
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id="user-id", email="user@example.com"
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_routes_and_validation(self) -> None:
        self.assertIn("Agent Hub", self.client.get("/").text)
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/agents").json(), [])
        response = self.client.post(
            "/conversations/id/messages", json={"text": ""}
        )
        self.assertEqual(response.status_code, 422)

    def test_generic_activity(self) -> None:
        self.service.send_activity.return_value = {"id": "activity-id"}

        response = self.client.post(
            "/conversations/id/activities",
            json={
                "type": "event",
                "name": "location",
                "value": {"latitude": -23.5, "longitude": -46.6},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": "activity-id"})

    def test_poll_activities(self) -> None:
        self.service.get_activities.return_value = ActivitySet(
            activities=[{"type": "typing"}], watermark="42"
        )

        response = self.client.get(
            "/conversations/id/activities", params={"watermark": "41"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["watermark"], "42")
        self.assertEqual(response.json()["activities"][0]["type"], "typing")

    def test_multipart_upload(self) -> None:
        self.service.upload_files.return_value = MessageResponse(messages=[])

        response = self.client.post(
            "/conversations/id/attachments",
            data={"text": "Review this"},
            files=[
                ("files", ("one.txt", b"one", "text/plain")),
                ("files", ("two.txt", b"two", "text/plain")),
            ],
        )

        self.assertEqual(response.status_code, 200)
        uploads = self.service.upload_files.call_args.args[1]
        self.assertEqual([upload[0] for upload in uploads], ["one.txt", "two.txt"])

    @patch("agent_hub.routes.stream.service")
    @patch("agent_hub.routes.stream.auth_service")
    def test_missing_conversation_closes_websocket(
        self, stream_auth: Mock, stream_service: Mock
    ) -> None:
        stream_auth.authenticate.return_value = AuthenticatedUser(
            id="user-id", email="user@example.com"
        )
        stream_service.get_stream_url.side_effect = HTTPException(
            status.HTTP_404_NOT_FOUND, "Conversation not found"
        )

        with self.client.websocket_connect(
            "/conversations/missing/stream", subprotocols=["agent-hub", "token"]
        ) as socket:
            with self.assertRaises(WebSocketDisconnect) as raised:
                socket.receive_json()

        self.assertEqual(raised.exception.code, 1008)
        self.assertEqual(raised.exception.reason, "Conversation not found")


if __name__ == "__main__":
    unittest.main()
