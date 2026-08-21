import json

import httpx
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from agent_hub.dependencies import auth_service, service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.websocket("/{conversation_id}/stream")
async def stream_activities(websocket: WebSocket, conversation_id: str) -> None:
    protocols = [
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
    ]
    if len(protocols) != 2 or protocols[0] != "agent-hub":
        await websocket.close(code=1008, reason="Authentication required")
        return
    try:
        user = auth_service.authenticate(protocols[1])
    except HTTPException as error:
        await websocket.close(code=1008, reason=str(error.detail))
        return
    await websocket.accept(subprotocol="agent-hub")
    try:
        stream_url = await run_in_threadpool(
            service.get_stream_url, conversation_id, user.id
        )
        if stream_url.startswith("https://"):
            stream_url = f"wss://{stream_url.removeprefix('https://')}"
        elif stream_url.startswith("http://"):
            stream_url = f"ws://{stream_url.removeprefix('http://')}"
        async with connect(stream_url) as upstream:
            async for message in upstream:
                if message:
                    text = message.decode() if isinstance(message, bytes) else message
                    payload = json.loads(text)
                    if payload.get("watermark") is not None:
                        service.update_watermark(
                            conversation_id, str(payload["watermark"]), user.id
                        )
                    state = service.get_conversation(conversation_id, user.id)
                    payload["activities"] = [
                        activity
                        for activity in payload.get("activities", [])
                        if activity.get("from", {}).get("id") != state.user_id
                    ]
                    await websocket.send_json(payload)
    except WebSocketDisconnect:
        return
    except HTTPException as error:
        await websocket.close(code=1008, reason=str(error.detail))
    except (ConnectionClosed, httpx.HTTPError, json.JSONDecodeError, KeyError):
        await websocket.close(code=1011, reason="Agent stream unavailable")
