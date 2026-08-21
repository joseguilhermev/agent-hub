import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from agent_hub.dependencies import CurrentUser, Service
from agent_hub.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivitySet,
    Conversation,
    ConversationCreate,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=Conversation, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate, chat: Service, user: CurrentUser
) -> Conversation:
    try:
        return chat.create_conversation(body.agent_id, body.user_name, user.id)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: str, body: MessageCreate, chat: Service, user: CurrentUser
) -> MessageResponse:
    try:
        return chat.send_message(conversation_id, body.text, user.id)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error


@router.get("/{conversation_id}/activities", response_model=ActivitySet)
def get_activities(
    conversation_id: str,
    chat: Service,
    user: CurrentUser,
    watermark: str | None = None,
) -> ActivitySet:
    try:
        return chat.get_activities(conversation_id, watermark, user.id)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error


@router.post("/{conversation_id}/activities", response_model=ActivityResponse)
def send_activity(
    conversation_id: str,
    body: ActivityCreate,
    chat: Service,
    user: CurrentUser,
) -> ActivityResponse:
    try:
        result = chat.send_activity(
            conversation_id,
            body.model_dump(by_alias=True, exclude_none=True),
            user.id,
        )
        return ActivityResponse(id=str(result["id"]))
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error


@router.post("/{conversation_id}/attachments")
async def upload_attachments(
    conversation_id: str,
    chat: Service,
    user: CurrentUser,
    files: list[UploadFile] = File(),
    text: str | None = Form(default=None),
) -> MessageResponse:
    uploads = [
        (
            file.filename or "attachment",
            await file.read(),
            file.content_type or "application/octet-stream",
        )
        for file in files
    ]
    try:
        return await run_in_threadpool(
            chat.upload_files, conversation_id, uploads, text, user.id
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_conversation(
    conversation_id: str, chat: Service, user: CurrentUser
) -> None:
    try:
        chat.end_conversation(conversation_id, user.id)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Agent provider is unavailable"
        ) from error
