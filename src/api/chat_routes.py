"""
Chat API Routes

Endpoints for AI revision chatbot functionality.
Includes SSE streaming for real-time message responses.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.config.models import DEFAULT_MODELS, MODEL_REGISTRY, get_model_config
from src.models.chat import ChatMessage, Conversation, MessageRole
from src.models.digest import Digest
from src.models.newsletter import Newsletter
from src.models.podcast import PodcastScriptRecord
from src.models.summary import NewsletterSummary
from src.services.chat_service import ChatService
from src.services.prompt_service import PromptService
from src.storage.database import get_db
from src.utils.logging import get_logger

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = get_logger(__name__)


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


def get_artifact_content(db: Session, artifact_type: str, artifact_id: int) -> str:
    """Fetch and format artifact content for LLM context.

    Args:
        db: Database session
        artifact_type: Type of artifact (summary, digest, script)
        artifact_id: ID of the artifact

    Returns:
        Formatted content string for injection into system prompt
    """
    if artifact_type == "summary":
        # Get the summary and its associated newsletter
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == artifact_id).first()

        if not summary:
            return "[Summary not found]"

        # Get the associated newsletter
        newsletter = db.query(Newsletter).filter(Newsletter.id == summary.newsletter_id).first()

        # Format newsletter content (limit to ~10000 chars to avoid token overflow)
        newsletter_content = ""
        if newsletter:
            raw_content = newsletter.raw_text or newsletter.raw_html or ""
            newsletter_content = raw_content[:10000]
            if len(raw_content) > 10000:
                newsletter_content += "\n\n[Content truncated...]"

        # Format key themes, insights, etc. as bullet lists
        key_themes = "\n".join(f"- {t}" for t in (summary.key_themes or []))
        strategic_insights = "\n".join(f"- {i}" for i in (summary.strategic_insights or []))
        technical_details = "\n".join(f"- {d}" for d in (summary.technical_details or []))
        actionable_items = "\n".join(f"- {a}" for a in (summary.actionable_items or []))
        notable_quotes = "\n".join(f'- "{q}"' for q in (summary.notable_quotes or []))

        content = f"""### Source Newsletter
**From:** {newsletter.sender if newsletter else 'Unknown'}
**Subject:** {newsletter.title if newsletter else 'Unknown'}
**Date:** {newsletter.published_date if newsletter else 'Unknown'}

{newsletter_content}

---

### Summary Being Reviewed

**Executive Summary:**
{summary.executive_summary}

**Key Themes:**
{key_themes or 'None identified'}

**Strategic Insights:**
{strategic_insights or 'None identified'}

**Technical Details:**
{technical_details or 'None identified'}

**Actionable Items:**
{actionable_items or 'None identified'}

**Notable Quotes:**
{notable_quotes or 'None identified'}
"""
        return content

    elif artifact_type == "digest":
        digest = db.query(Digest).filter(Digest.id == artifact_id).first()

        if not digest:
            return "[Digest not found]"

        # Format strategic insights
        strategic_insights = ""
        if digest.strategic_insights:
            for insight in digest.strategic_insights:
                if isinstance(insight, dict):
                    title = insight.get("title", "")
                    summary = insight.get("summary", "")
                    strategic_insights += f"**{title}**\n{summary}\n\n"
                else:
                    strategic_insights += f"- {insight}\n"

        # Format technical developments
        technical_developments = ""
        if digest.technical_developments:
            for dev in digest.technical_developments:
                if isinstance(dev, dict):
                    title = dev.get("title", "")
                    summary = dev.get("summary", "")
                    technical_developments += f"**{title}**\n{summary}\n\n"
                else:
                    technical_developments += f"- {dev}\n"

        # Format emerging trends
        emerging_trends = ""
        if digest.emerging_trends:
            for trend in digest.emerging_trends:
                if isinstance(trend, dict):
                    title = trend.get("title", "")
                    summary = trend.get("summary", "")
                    emerging_trends += f"**{title}**\n{summary}\n\n"
                else:
                    emerging_trends += f"- {trend}\n"

        content = f"""### Digest Being Reviewed

**Title:** {digest.title}
**Type:** {digest.digest_type}
**Period:** {digest.period_start} to {digest.period_end}
**Newsletter Count:** {digest.newsletter_count}

---

**Executive Overview:**
{digest.executive_overview}

---

**Strategic Insights:**
{strategic_insights or 'None identified'}

**Technical Developments:**
{technical_developments or 'None identified'}

**Emerging Trends:**
{emerging_trends or 'None identified'}
"""
        return content

    elif artifact_type == "script":
        script = db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == artifact_id).first()

        if not script:
            return "[Script not found]"

        # Format script content from script_json
        script_content = ""
        if script.script_json:
            sections = script.script_json.get("sections", [])
            for section in sections:
                section_type = section.get("section_type", "")
                section_title = section.get("title", "")
                script_content += f"\n### {section_type.upper()}: {section_title}\n\n"

                dialogue = section.get("dialogue", [])
                for turn in dialogue:
                    speaker = turn.get("speaker", "").upper()
                    text = turn.get("text", "")
                    script_content += f"**{speaker}:** {text}\n\n"

        # Limit script length to ~15000 chars
        if len(script_content) > 15000:
            script_content = script_content[:15000] + "\n\n[Script truncated...]"

        content = f"""### Podcast Script Being Reviewed

**Title:** {script.title}
**Length:** {script.length}
**Word Count:** {script.word_count}
**Estimated Duration:** {script.estimated_duration_seconds} seconds

---

{script_content}
"""
        return content

    return "[Unknown artifact type]"


async def generate_ai_response_streaming(
    conversation: Conversation,
    user_message: str,
    enable_web_search: bool = False,
    model: str | None = None,
    db: Session | None = None,
) -> AsyncGenerator[tuple[str, MessageMetadata | None], None]:
    """Generate streaming AI response for the conversation.

    Uses ChatService for actual LLM calls with multi-provider support.

    Args:
        conversation: The conversation object
        user_message: The user's message
        enable_web_search: Whether to enable web search
        model: Model to use (defaults to digest_revision model)
        db: Database session for fetching artifact content

    Yields:
        Tuples of (content_chunk, metadata_or_none)
        - Content chunks have metadata=None
        - Final yield has empty content and MessageMetadata
    """
    # Get default model if not specified
    model = model or DEFAULT_MODELS.get("digest_revision", "claude-sonnet-4-5")

    # Build messages from conversation history
    messages: list[dict[str, str]] = []
    for msg in conversation.messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    # Get base system prompt from PromptService
    prompt_service = PromptService()
    base_prompt = prompt_service.get_chat_prompt(conversation.artifact_type)

    # Fetch and inject artifact content if db session is available
    if db is not None:
        artifact_content = get_artifact_content(
            db, conversation.artifact_type, conversation.artifact_id
        )
        system_prompt = f"""{base_prompt}

## Content Being Reviewed

{artifact_content}
"""
    else:
        system_prompt = base_prompt

    # Create chat service
    model_config = get_model_config()
    chat_service = ChatService(model_config)

    logger.info(
        f"Generating chat response: model={model}, artifact={conversation.artifact_type}, "
        f"web_search={enable_web_search}"
    )

    try:
        async for chunk, chat_meta in chat_service.generate_response(
            messages=messages,
            model=model,
            system_prompt=system_prompt,
        ):
            if chat_meta:
                # Final chunk with metadata
                metadata = MessageMetadata(
                    model=chat_meta.model,
                    token_usage=chat_meta.input_tokens + chat_meta.output_tokens,
                    web_search_used=enable_web_search,
                    processing_time_ms=chat_meta.processing_time_ms,
                )
                yield "", metadata
            else:
                yield chunk, None
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        # Yield error as content
        yield f"\n\n[Error: {e!s}]", None
        # Yield minimal metadata
        metadata = MessageMetadata(
            model=model,
            token_usage=0,
            web_search_used=enable_web_search,
            processing_time_ms=0,
        )
        yield "", metadata


async def generate_ai_response(
    conversation: Conversation,
    user_message: str,
    enable_web_search: bool = False,
    model: str | None = None,
    db: Session | None = None,
) -> tuple[str, MessageMetadata]:
    """Generate AI response for the conversation (non-streaming).

    This is a convenience wrapper that collects the full response.
    For streaming, use generate_ai_response_streaming directly.
    """
    content_parts: list[str] = []
    final_metadata: MessageMetadata | None = None

    async for chunk, metadata in generate_ai_response_streaming(
        conversation, user_message, enable_web_search, model, db=db
    ):
        if metadata:
            final_metadata = metadata
        else:
            content_parts.append(chunk)

    if final_metadata is None:
        final_metadata = MessageMetadata(
            model=model or "claude-sonnet-4-5",
            token_usage=0,
            web_search_used=enable_web_search,
            processing_time_ms=0,
        )

    return "".join(content_parts), final_metadata


# ============================================================================
# Routes
# ============================================================================


@router.get("/config", response_model=ChatConfigResponse)
async def get_chat_config() -> ChatConfigResponse:
    """Get chat configuration.

    Returns available models from the model registry.
    """
    # Build model list from registry
    available_models = [
        {
            "id": model_id,
            "name": model_info.name,
            "provider": model_info.family.value,  # claude, gemini, gpt
        }
        for model_id, model_info in MODEL_REGISTRY.items()
    ]

    # Get default from config (digest_revision for chat)
    default_model = DEFAULT_MODELS.get("digest_revision", "claude-sonnet-4-5")

    return ChatConfigResponse(
        available_models=available_models,
        default_model=default_model,
        web_search_enabled=False,  # Web search not implemented yet
        max_message_length=2000,
        max_history_length=50,
    )


@router.get("/conversations", response_model=PaginatedConversationsResponse)
async def list_conversations(
    artifact_type: str | None = Query(None),
    artifact_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedConversationsResponse:
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
async def get_conversation(conversation_id: str) -> ConversationResponse:
    """Get a single conversation with all messages."""
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation_to_response(conversation)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest) -> ConversationResponse:
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
                db=db,
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
async def delete_conversation(conversation_id: str) -> dict[str, str]:
    """Delete a conversation."""
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        db.delete(conversation)
        db.commit()

        return {"status": "deleted"}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: SendMessageRequest) -> StreamingResponse:
    """Send a message and stream the response via SSE."""

    async def event_generator() -> AsyncGenerator[str, None]:
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

            # Stream response using actual LLM
            content_parts: list[str] = []
            final_metadata: MessageMetadata | None = None

            async for chunk, metadata in generate_ai_response_streaming(
                conversation,
                request.content,
                enable_web_search=request.enable_web_search,
                model=request.model,
                db=db,
            ):
                if metadata:
                    final_metadata = metadata
                else:
                    content_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

            # Combine content
            response_content = "".join(content_parts)

            # Ensure we have metadata
            if final_metadata is None:
                final_metadata = MessageMetadata(
                    model=request.model or "claude-sonnet-4-5",
                    token_usage=0,
                    web_search_used=request.enable_web_search,
                    processing_time_ms=0,
                )

            # Save assistant message
            assistant_msg = ChatMessage(
                id=msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                model_used=final_metadata.model,
                token_usage=final_metadata.token_usage,
                processing_time_ms=final_metadata.processing_time_ms,
                web_search_used=final_metadata.web_search_used,
            )
            db.add(assistant_msg)

            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            db.commit()

            # Send end event with metadata
            yield f"data: {json.dumps({'type': 'end', 'metadata': final_metadata.model_dump(by_alias=True)})}\n\n"

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
async def regenerate_last_message(conversation_id: str) -> StreamingResponse:
    """Regenerate the last assistant message."""

    async def event_generator() -> AsyncGenerator[str, None]:
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

            # Stream response using actual LLM
            content_parts: list[str] = []
            final_metadata: MessageMetadata | None = None

            async for chunk, metadata in generate_ai_response_streaming(
                conversation,
                user_msg.content,
                db=db,
            ):
                if metadata:
                    final_metadata = metadata
                else:
                    content_parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

            # Combine content
            response_content = "".join(content_parts)

            # Ensure we have metadata
            if final_metadata is None:
                final_metadata = MessageMetadata(
                    model="claude-sonnet-4-5",
                    token_usage=0,
                    web_search_used=False,
                    processing_time_ms=0,
                )

            # Save new assistant message
            assistant_msg = ChatMessage(
                id=msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=response_content,
                model_used=final_metadata.model,
                token_usage=final_metadata.token_usage,
                processing_time_ms=final_metadata.processing_time_ms,
            )
            db.add(assistant_msg)
            conversation.updated_at = datetime.utcnow()
            db.commit()

            # Send end event
            yield f"data: {json.dumps({'type': 'end', 'metadata': final_metadata.model_dump(by_alias=True)})}\n\n"

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
async def apply_action(conversation_id: str, request: ApplyActionRequest) -> dict[str, Any]:
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
) -> list[ChatMessageResponse]:
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


class DebugContextResponse(BaseModel):
    """Debug context response showing what's sent to the LLM."""

    system_prompt: str
    artifact_content: str
    full_context: str
    artifact_type: str
    artifact_id: int
    message_count: int


@router.get("/conversations/{conversation_id}/context", response_model=DebugContextResponse)
async def get_conversation_context(conversation_id: str) -> DebugContextResponse:
    """Debug endpoint to view what context is sent to the LLM.

    Returns the system prompt, artifact content, and full context that would be
    sent to the LLM when generating a response.
    """
    with get_db() as db:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get base system prompt
        prompt_service = PromptService()
        base_prompt = prompt_service.get_chat_prompt(conversation.artifact_type)

        # Get artifact content
        artifact_content = get_artifact_content(
            db, conversation.artifact_type, conversation.artifact_id
        )

        # Build full context as it would be sent to the LLM
        full_context = f"""{base_prompt}

## Content Being Reviewed

{artifact_content}
"""

        return DebugContextResponse(
            system_prompt=base_prompt,
            artifact_content=artifact_content,
            full_context=full_context,
            artifact_type=conversation.artifact_type,
            artifact_id=conversation.artifact_id,
            message_count=len(conversation.messages),
        )
