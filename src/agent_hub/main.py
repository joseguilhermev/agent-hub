import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from agent_hub.directline import DirectLineClient

PROMPTS = (
    "olá introduza você mesmo",
    "Me de um arquivo word escrito hello word",
    "Quais tipos de arquivo você consegue receber",
)


def wait_for_agent(
    client: DirectLineClient,
    conversation_id: str,
    token: str,
    user_id: str,
    watermark: str | None,
    timeout: float = 30,
) -> tuple[str | None, list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout
    received: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        activity_set = client.get_activities(conversation_id, token, watermark)
        next_watermark = activity_set.get("watermark")
        if next_watermark is not None:
            watermark = str(next_watermark)

        new_activities = [
            activity
            for activity in activity_set.get("activities", [])
            if activity.get("from", {}).get("id") != user_id
        ]
        if new_activities:
            received.extend(new_activities)
            turn_finished = any(
                activity.get("type") == "endOfConversation"
                or (
                    activity.get("type") == "event"
                    and activity.get("name") == "turn.complete"
                )
                for activity in new_activities
            )
            if turn_finished:
                break

        time.sleep(1)

    return watermark, received


def safe_json(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {name: safe_json(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [safe_json(item, key) for item in value]
    if isinstance(value, str):
        normalized_key = key.lower()
        if any(word in normalized_key for word in ("token", "secret", "authorization")):
            return "<redacted>"
        if normalized_key in {"contenturl", "streamurl"}:
            if value.startswith("data:"):
                return "data:<redacted>"
            parsed = urlsplit(value)
            query = "<redacted>" if parsed.query else ""
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return value


def print_activities(
    activities: list[dict[str, Any]],
    show_json: bool = False,
) -> None:
    if not activities:
        print("Agent: no response before timeout")
        return

    for activity in activities:
        activity_type = activity.get("type", "unknown")
        sender = activity.get("from", {}).get("name", "agent")
        keys = ", ".join(sorted(activity))
        print(f"{sender} [{activity_type}; fields: {keys}]")

        if text := activity.get("text"):
            print(text)

        attachments = activity.get("attachments", [])
        for attachment in attachments:
            print(f"Attachment: {attachment.get('contentType', 'unknown')}")

        if name := activity.get("name"):
            print(f"Event: {name}")

        if show_json:
            print(json.dumps(safe_json(activity), ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a Copilot Studio agent through Direct Line"
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="optional file to upload before sending the prompts",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print complete activity JSON with signed URL queries redacted",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file is not None and not args.file.is_file():
        raise SystemExit(f"File not found: {args.file}")

    load_dotenv()
    secret = os.getenv("SECRET", "").strip()
    if not secret:
        raise SystemExit("Missing SECRET in .env")

    user_id = f"dl_{uuid4().hex}"
    client = DirectLineClient(secret)

    try:
        token_response = client.generate_token(user_id, "Direct Line Test")
        print(f"Token created; expires in {token_response.get('expires_in')} seconds")

        conversation = client.start_conversation(str(token_response["token"]))
        conversation_id = str(conversation["conversationId"])
        token = str(conversation["token"])
        print(f"Conversation: {conversation_id}")

        watermark: str | None = None
        client.send_start_conversation_event(conversation_id, token, user_id)
        watermark, greeting = wait_for_agent(
            client,
            conversation_id,
            token,
            user_id,
            watermark,
            timeout=10,
        )
        if greeting:
            print("\nGreeting")
            print_activities(greeting, args.json)

        if args.file is not None:
            uploaded = client.upload_file(
                conversation_id,
                token,
                user_id,
                args.file,
            )
            print(f"\nUploaded {args.file.name}; activity: {uploaded.get('id')}")
            watermark, upload_response = wait_for_agent(
                client,
                conversation_id,
                token,
                user_id,
                watermark,
                timeout=120,
            )
            print_activities(upload_response, args.json)

        for prompt in PROMPTS:
            print(f"\nUser: {prompt}")
            client.send_message(conversation_id, token, user_id, prompt)
            watermark, response = wait_for_agent(
                client,
                conversation_id,
                token,
                user_id,
                watermark,
            )
            print_activities(response, args.json)
    except httpx.HTTPStatusError as error:
        detail = error.response.text.strip()
        message = f"Direct Line returned HTTP {error.response.status_code}"
        if detail:
            message = f"{message}: {detail}"
        raise SystemExit(message) from None
    except httpx.RequestError as error:
        raise SystemExit(f"Direct Line request failed: {error}") from None
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
