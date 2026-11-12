from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ChatRequest, ChatResponse, MessageOut, RegenerateRequest
from ..services import chat_service
from ..services.ai_service import AIService, get_ai_service

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db), ai: AIService = Depends(get_ai_service)):
    """Send a message to EduMate. Omit `conversation_id` to start a new conversation."""
    if req.conversation_id is not None and chat_service.get_conversation(db, req.conversation_id) is None:
        raise HTTPException(404, "Conversation not found. It may have been deleted.")

    conversation, user_msg, assistant_msg = chat_service.send_message(db, ai, req.message, req.conversation_id)
    return ChatResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg),
    )


@router.post("/regenerate", response_model=MessageOut)
def regenerate(req: RegenerateRequest, db: Session = Depends(get_db), ai: AIService = Depends(get_ai_service)):
    """Generate a new answer for the last question in a conversation."""
    conversation = chat_service.get_conversation(db, req.conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found. It may have been deleted.")

    new_msg = chat_service.regenerate_last_reply(db, ai, conversation)
    if new_msg is None:
        raise HTTPException(400, "There is no question in this conversation to answer again.")
    return MessageOut.model_validate(new_msg)
