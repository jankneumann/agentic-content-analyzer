"""
Chat API Routes

Endpoints for AI revision chatbot functionality.
Includes SSE streaming for real-time message responses.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc

from src.models.chat import ChatMessage, Conversation, MessageRole
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ============================================================================
# Request/Response Models
# ============================================================================


class MessageMetadata(BaseModel):
    """Metadata about message generation."""

    model: str | None = None
    token_usage: int | None = Field(None, alias="tokenUsage")
    web_search_used: bool | None = Field(False, alias="webSearchUsed")
    web_search_queries: list[str] | None = Field(None, alias="webSearchQueries")
    processing_time_ms: int | None = Field(None, alias="processingTimeMs")

    class Config:
        populate_by_name = True


class SuggestedAction(BaseModel):
    """Suggested action from the assistant."""

    type: Literal["replace_section", "add_content", "remove_content", "rewrite"]
    section: str | None = None
    section_index: int | None = Field(None, alias="sectionIndex")
    original_content: str | None = Field(None, alias="originalContent")
    suggested_content: str = Field(..., alias="suggestedContent")
    explanation: str

    class Config:
        populate_by_name = True


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: str
    role: str
    content: str
    timestamp: str
    metadata: MessageMetadata | None = None
    suggested_actions: list[SuggestedAction] | None = Field(None, alias="suggestedActions")

    class Config:
        populate_by_name = True
        from_attributes = True


class ConversationResponse(BaseModel):
    """Full conversation response."""

    id: str
    artifact_type: str = Field(..., alias="artifactType")
    artifact_id: str = Field(..., alias="artifactId")
    title: str
    messages: list[ChatMessageResponse]
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    is_active: bool = Field(..., alias="isActive")

    class Config:
        populate_by_name = True
        from_attributes = True


class ConversationListItem(BaseModel):
    """Lightweight conversation for lists."""

    id: str
    artifact_type: str = Field(..., alias="artifactType")
    artifact_id: str = Field(..., alias="artifactId")
    title: str
    message_count: int = Field(..., alias="messageCount")
    last_message_preview: str = Field(..., alias="lastMessagePreview")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    class Config:
        populate_by_name = True


class PaginatedConversationsResponse(BaseModel):
    """Paginated conversations list."""

    items: list[ConversationListItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    artifact_type: str = Field(..., alias="artifact_type")
    artifact_id: str = Field(..., alias="artifact_id")
    initial_message: str | None = Field(None, alias="initial_message")
    title: str | None = None

    class Config:
        populate_by_name = True


class SendMessageRequest(BaseModel):
    """Request to send a message."""

    content: str
    enable_web_search: bool = Field(False, alias="enable_web_search")
    model: str | None = None

    class Config:
        populate_by_name = True


class ApplyActionRequest(BaseModel):
    """Request to apply a suggested action."""

    message_id: str = Field(..., alias="message_id")
    action_index: int = Field(0, alias="action_index")

    class Config:
        populate_by_name = True


class ChatConfigResponse(BaseModel):
    """Chat configuration response."""

    available_models: list[dict]
    default_model: str
    web_search_enabled: bool
    max_message_length: int
    max_history_length: int


# ============================================================================
# Helper Functions
# ============================================================================


def conversation_to_response(conv: Conversation) -> ConversationResponse:
    """Convert Conversation model to response."""
    messages = [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.created_at.isoformat(),
            metadata=MessageMetadata(
                model=msg.model_used,
                token_usage=msg.token_usage,
                web_search_used=msg.web_search_used,
                web_search_queries=msg.web_search_queries,
                processing_time_ms=msg.processing_time_ms,
            )
            if msg.role == MessageRole.ASSISTANT.value
            else None,
            suggested_actions=msg.suggested_actions,
        )
        for msg in conv.messages
    ]

    return ConversationResponse(
        id=conv.id,
        artifact_type=conv.artifact_type,
        artifact_id=str(conv.artifact_id),
        title=conv.title,
        messages=messages,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        is_active=conv.is_active,
    )


def conversation_to_list_item(conv: Conversation) -> ConversationListItem:
    """Convert Conversation model to list item."""
    last_message = conv.messages[-1] if conv.messages else None
    preview = ""
    if last_message:
        preview = last_message.content[:100] + ("..." if len(last_message.content) > 100 else "")

    return ConversationListItem(
        id=conv.id,
        artifact_type=conv.artifact_type,
        artifact_id=str(conv.artifact_id),
        title=conv.title,
        message_count=len(conv.messages),
        last_message_preview=preview,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


async def generate_ai_response(
    conversation: Conversation,
    user_message: str,
    enable_web_search: bool = False,
    model: str | None = None,
) -> tuple[str, MessageMetadata]:
    """Generate AI response for the conversation.

    This is a placeholder that should be replaced with actual LLM integration.
    Returns streaming chunks via SSE.
    """
    # TODO: Replace with actual LLM integration
    # For now, return a mock response
    response = f"I understand you want to improve this {conversation.artifact_type}. "
    response += f"Based on your message: '{user_message[:50]}...', "
    response += "here are my suggestions:\n\n"
    response += "1. Consider being more specific about the key points\n"
    response += "2. The structure could be improved for clarity\n"
    response += "3. Adding more context would help readers understand better"

    metadata = MessageMetadata(
        model=model or "claude-sonnet-4-5",
        token_usage=150,
        web_search_used=enable_web_search,
        processing_time_ms=500,
    )

    return response, metadata


# ============================================================================
# Routes
# ============================================================================


@router.get("/config", response_model=ChatConfigResponse)
async def get_chat_config():
    """Get chat configuration."""
    return ChatConfigResponse(
        available_models=[
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5", "provider": "anthropic"},
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "provider": "anthropic"},
        ],
        default_model="claude-sonnet-4-5",
        web_search_enabled=True,
        max_message_length=2000,
        max_history_length=50,
    )


@router.get("/conversations", response_model=PaginatedConversationsResponse)
async def list_conversations(
    artifact_type: str | None = Query(None),
    artifact_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List conversations with optional filtering."""
    with get_db() as db:
        query = db.query(Conversation).filter(Conversation.is_active.is_(True))

        if artifact_type:
            query = query.filter(Conversation.artifact_type == artifact_type)
        if artifact_id:
            query = query.filter(Conversation.artifact_id == int(artifact_id))

        total = query.count()
        conversations = (
            query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit).all()
        )

        items = [conversation_to_list_item(conv) for conv in conversations]

        return PaginatedConversationsResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + len(items) < total,
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    """Get a single conversation with all messages."""
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation_to_response(conversation)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    with get_db() as db:
        # Generate conversation ID
        conv_id = str(uuid.uuid4())

        # Create conversation
        conversation = Conversation(
            id=conv_id,
            artifact_type=request.artifact_type,
            artifact_id=int(request.artifact_id),
            title=request.title or f"Revision for {request.artifact_type} #{request.artifact_id}",
            is_active=True,
        )
        db.add(conversation)

        # Add initial message if provided
        if request.initial_message:
            user_msg = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role=MessageRole.USER.value,
                content=request.initial_message,
            )
            db.add(user_msg)

            # Generate initial response
            response_content, metadata = await generate_ai_response(
                conversation,
                request.initial_message,
            )

            assistant_msg = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                model_used=metadata.model,
                token_usage=metadata.token_usage,
                processing_time_ms=metadata.processing_time_ms,
                web_search_used=metadata.web_search_used,
            )
            db.add(assistant_msg)

        db.commit()
        db.refresh(conversation)

        return conversation_to_response(conversation)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        db.delete(conversation)
        db.commit()

        return {"status": "deleted"}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """Send a message and stream the response via SSE."""

    async def event_generator():
        with get_db() as db:
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

            if not conversation:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Conversation not found'})}\n\n"
                return

            # Add user message
            user_msg = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role=MessageRole.USER.value,
                content=request.content,
            )
            db.add(user_msg)
            db.commit()

            # Generate message ID for streaming
            msg_id = str(uuid.uuid4())

            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'messageId': msg_id})}\n\n"

            # Generate response (with simulated streaming)
            response_content, metadata = await generate_ai_response(
                conversation,
                request.content,
                enable_web_search=request.enable_web_search,
                model=request.model,
            )

            # Simulate streaming by sending chunks
            words = response_content.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
                await asyncio.sleep(0.02)  # Simulate typing

            # Save assistant message
            assistant_msg = ChatMessage(
                id=msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                model_used=metadata.model,
                token_usage=metadata.token_usage,
                processing_time_ms=metadata.processing_time_ms,
                web_search_used=metadata.web_search_used,
            )
            db.add(assistant_msg)

            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            db.commit()

            # Send end event with metadata
            yield f"data: {json.dumps({'type': 'end', 'metadata': metadata.model_dump(by_alias=True)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversations/{conversation_id}/regenerate")
async def regenerate_last_message(conversation_id: str):
    """Regenerate the last assistant message."""

    async def event_generator():
        with get_db() as db:
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

            if not conversation:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Conversation not found'})}\n\n"
                return

            # Find the last assistant message
            last_assistant = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.role == MessageRole.ASSISTANT.value,
                )
                .order_by(desc(ChatMessage.created_at))
                .first()
            )

            if not last_assistant:
                yield f"data: {json.dumps({'type': 'error', 'error': 'No assistant message to regenerate'})}\n\n"
                return

            # Find the user message that triggered this response
            user_msg = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.role == MessageRole.USER.value,
                    ChatMessage.created_at < last_assistant.created_at,
                )
                .order_by(desc(ChatMessage.created_at))
                .first()
            )

            if not user_msg:
                yield f"data: {json.dumps({'type': 'error', 'error': 'No user message found'})}\n\n"
                return

            # Delete old assistant message
            db.delete(last_assistant)
            db.commit()

            # Generate new message ID
            msg_id = str(uuid.uuid4())

            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'messageId': msg_id})}\n\n"

            # Generate new response
            response_content, metadata = await generate_ai_response(
                conversation,
                user_msg.content,
            )

            # Stream response
            words = response_content.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
                await asyncio.sleep(0.02)

            # Save new assistant message
            assistant_msg = ChatMessage(
                id=msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                model_used=metadata.model,
                token_usage=metadata.token_usage,
                processing_time_ms=metadata.processing_time_ms,
            )
            db.add(assistant_msg)
            conversation.updated_at = datetime.utcnow()
            db.commit()

            # Send end event
            yield f"data: {json.dumps({'type': 'end', 'metadata': metadata.model_dump(by_alias=True)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversations/{conversation_id}/apply-action")
async def apply_action(conversation_id: str, request: ApplyActionRequest):
    """Apply a suggested action from a chat message."""
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Find the message with the action
        message = db.query(ChatMessage).filter(ChatMessage.id == request.message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if not message.suggested_actions:
            raise HTTPException(status_code=400, detail="Message has no suggested actions")

        if request.action_index >= len(message.suggested_actions):
            raise HTTPException(status_code=400, detail="Action index out of range")

        action = message.suggested_actions[request.action_index]

        # TODO: Apply the action to the actual artifact (summary/digest/script)
        # This would involve updating the artifact based on action type

        return {
            "status": "applied",
            "action": action,
            "artifact_type": conversation.artifact_type,
            "artifact_id": conversation.artifact_id,
        }


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None),
):
    """Get messages for a conversation."""
    with get_db() as db:
        query = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id)

        if before:
            before_msg = db.query(ChatMessage).filter(ChatMessage.id == before).first()
            if before_msg:
                query = query.filter(ChatMessage.created_at < before_msg.created_at)

        messages = query.order_by(desc(ChatMessage.created_at)).limit(limit).all()

        # Reverse to get chronological order
        messages = list(reversed(messages))

        return [
            ChatMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at.isoformat(),
                metadata=MessageMetadata(
                    model=msg.model_used,
                    token_usage=msg.token_usage,
                    web_search_used=msg.web_search_used,
                    web_search_queries=msg.web_search_queries,
                    processing_time_ms=msg.processing_time_ms,
                )
                if msg.role == MessageRole.ASSISTANT.value
                else None,
                suggested_actions=msg.suggested_actions,
            )
            for msg in messages
        ]
