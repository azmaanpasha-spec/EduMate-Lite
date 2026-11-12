from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message
from ..schemas import ConversationDetail, ConversationSummary, MessageOut
from ..services import chat_service

router = APIRouter(prefix="/api/history", tags=["Chat History"])


@router.get("", response_model=list[ConversationSummary])
def list_history(db: Session = Depends(get_db)):
    """All conversations, most recently used first."""
    counts = dict(db.execute(select(Message.conversation_id, func.count(Message.id)).group_by(Message.conversation_id)).all())
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=counts.get(c.id, 0),
        )
        for c in chat_service.list_conversations(db)
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_history(conversation_id: int, db: Session = Depends(get_db)):
    """One conversation with all of its messages."""
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageOut.model_validate(m) for m in conversation.messages],
    )


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    db.delete(conversation)  # messages are deleted too (cascade)
    db.commit()
    return {"deleted": conversation_id}


@router.delete("")
def clear_history(db: Session = Depends(get_db)):
    db.execute(delete(Message))
    deleted = db.execute(delete(Conversation)).rowcount
    db.commit()
    return {"deleted_conversations": deleted}
