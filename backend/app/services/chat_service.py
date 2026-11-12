"""
Chat logic: building context for Gemini and saving conversations.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Conversation, Message, utc_now
from .ai_service import AIService

CHAT_SYSTEM_PROMPT = """You are EduMate, a friendly and intelligent academic assistant designed for college students.
Your purpose is to make learning easier.

You must:
1. Answer academic questions accurately.
2. Explain difficult topics in simple language.
3. Provide relevant real-life examples.
4. Explain technical concepts step by step.
5. Help with programming, mathematics, science and general academic subjects.
6. Summarize educational information.
7. Generate practice questions when requested.
8. Help students prepare for examinations.
9. Understand follow-up questions using conversation context.
10. Admit uncertainty instead of inventing information.

Use clear headings and bullet points where appropriate.
Avoid unnecessarily complicated terminology.
Adapt the length of your answers to the user's question.
Always maintain a polite and encouraging tone.

Format your answers in Markdown. Put code inside fenced code blocks with the language name."""

TITLE_MAX_LENGTH = 50


def make_title(first_message: str) -> str:
    """Create a short conversation title from the student's first message."""
    title = " ".join(first_message.split())  # collapse whitespace / newlines
    if len(title) > TITLE_MAX_LENGTH:
        title = title[:TITLE_MAX_LENGTH].rsplit(" ", 1)[0].rstrip(" ,.;:") + "..."
    return title or "New conversation"


def recent_context(messages: list[Message], limit: int) -> list[dict]:
    """Return only the last `limit` messages, starting with a user message."""
    window = messages[-limit:] if limit > 0 else []
    while window and window[0].role != "user":
        window = window[1:]  # Gemini conversations should start with the user
    return [{"role": m.role, "content": m.content} for m in window]


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def send_message(db: Session, ai: AIService, text: str, conversation_id: int | None):
    """Ask the AI and save both messages. Returns (conversation, user_msg, assistant_msg).

    The AI is called BEFORE anything is saved, so if the AI fails the
    database is left unchanged and the student can simply retry.
    """
    settings = get_settings()
    conversation = get_conversation(db, conversation_id) if conversation_id else None

    history = recent_context(conversation.messages, settings.chat_context_messages - 1) if conversation else []
    reply = ai.generate(CHAT_SYSTEM_PROMPT, history + [{"role": "user", "content": text}])

    if conversation is None:
        conversation = Conversation(title=make_title(text))
        db.add(conversation)
        db.flush()  # assigns conversation.id

    user_msg = Message(conversation_id=conversation.id, role="user", content=text)
    db.add(user_msg)
    db.flush()  # keeps message ids in order: user first, then assistant
    assistant_msg = Message(conversation_id=conversation.id, role="assistant", content=reply)
    db.add(assistant_msg)
    conversation.updated_at = utc_now()
    db.commit()
    return conversation, user_msg, assistant_msg


def regenerate_last_reply(db: Session, ai: AIService, conversation: Conversation) -> Message | None:
    """Replace the last assistant reply with a freshly generated one.

    Returns None if the conversation has no user message to answer.
    """
    settings = get_settings()
    messages = list(conversation.messages)
    if messages and messages[-1].role == "assistant":
        old_reply = messages.pop()
    else:
        old_reply = None
    if not messages or messages[-1].role != "user":
        return None

    context = recent_context(messages, settings.chat_context_messages)
    reply = ai.generate(CHAT_SYSTEM_PROMPT, context, temperature=0.9)

    # Only remove the old reply once the new one has arrived successfully
    if old_reply is not None:
        db.delete(old_reply)
    new_msg = Message(conversation_id=conversation.id, role="assistant", content=reply)
    db.add(new_msg)
    conversation.updated_at = utc_now()
    db.commit()
    return new_msg


def list_conversations(db: Session) -> list[Conversation]:
    return list(db.scalars(select(Conversation).order_by(Conversation.updated_at.desc(), Conversation.id.desc())))
