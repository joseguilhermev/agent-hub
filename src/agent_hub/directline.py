import json
import mimetypes
from pathlib import Path
from typing import Any, cast

import httpx

BASE_URL = "https://directline.botframework.com/v3/directline"


class DirectLineClient:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def _headers(self, credential: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {credential}",
        }

    def generate_token(self, user_id: str, user_name: str) -> dict[str, Any]:
        url = f"{BASE_URL}/tokens/generate"

        response = httpx.post(
            url,
            headers=self._headers(self.secret),
            json={"user": {"id": user_id, "name": user_name}},
            timeout=30,
        )
        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    def start_conversation(self, credential: str) -> dict[str, Any]:
        url = f"{BASE_URL}/conversations"

        response = httpx.post(
            url,
            headers=self._headers(credential),
            timeout=30,
        )

        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    def refresh_token(self, token: str) -> dict[str, Any]:
        response = httpx.post(
            f"{BASE_URL}/tokens/refresh",
            headers=self._headers(token),
            timeout=30,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def reconnect(
        self,
        conversation_id: str,
        token: str,
        watermark: str | None = None,
    ) -> dict[str, Any]:
        params = {"watermark": watermark} if watermark is not None else None
        response = httpx.get(
            f"{BASE_URL}/conversations/{conversation_id}",
            headers=self._headers(token),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def get_activities(
        self,
        conversation_id: str,
        token: str,
        watermark: str | None = None,
    ) -> dict[str, Any]:
        url = f"{BASE_URL}/conversations/{conversation_id}/activities"

        params: dict[str, str] = {}

        if watermark is not None:
            params["watermark"] = watermark

        response = httpx.get(
            url,
            headers=self._headers(token),
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    def send_activity(
        self,
        conversation_id: str,
        token: str,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{BASE_URL}/conversations/{conversation_id}/activities"

        response = httpx.post(
            url,
            headers=self._headers(token),
            json=activity,
            timeout=30,
        )

        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    def send_message(
        self,
        conversation_id: str,
        token: str,
        user_id: str,
        text: str,
    ) -> dict[str, Any]:
        activity = {
            "type": "message",
            "from": {
                "id": user_id,
            },
            "text": text,
        }

        return self.send_activity(
            conversation_id,
            token,
            activity,
        )

    def upload_file(
        self,
        conversation_id: str,
        token: str,
        user_id: str,
        file_path: str | Path,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        content_types = {
            ".xls": "application/vnd.ms-excel",
            ".xlsx": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        }
        content_type = content_types.get(path.suffix.lower())
        if content_type is None:
            content_type = mimetypes.guess_type(path.name)[0]
        if content_type is None:
            content_type = "application/octet-stream"

        filename = (
            path.name.replace('"', "_")
            .replace("\r", "")
            .replace("\n", "")
        )
        headers = self._headers(token)
        headers.update(
            {
                "Content-Type": content_type,
                "Content-Disposition": f'name="file"; filename="{filename}"',
            }
        )

        response = httpx.post(
            f"{BASE_URL}/conversations/{conversation_id}/upload",
            headers=headers,
            params={"userId": user_id},
            content=path.read_bytes(),
            timeout=60,
        )
        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    def upload_files(
        self,
        conversation_id: str,
        token: str,
        user_id: str,
        files: list[tuple[str, bytes, str]],
        activity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parts: list[tuple[str, tuple[str, bytes, str]]] = [
            ("file", (filename, content, content_type))
            for filename, content, content_type in files
        ]
        if activity is not None:
            parts.append(
                (
                    "activity",
                    (
                        "activity.json",
                        json.dumps(activity).encode(),
                        "application/vnd.microsoft.bot.message",
                    ),
                )
            )

        response = httpx.post(
            f"{BASE_URL}/conversations/{conversation_id}/upload",
            headers=self._headers(token),
            params={"userId": user_id},
            files=parts,
            timeout=120,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def send_start_conversation_event(
        self,
        conversation_id: str,
        token: str,
        user_id: str,
    ) -> dict[str, Any]:
        return self.send_activity(
            conversation_id,
            token,
            {
                "type": "event",
                "from": {"id": user_id},
                "name": "startConversation",
            },
        )
