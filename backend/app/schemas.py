"""
Pydantic models that describe the JSON sent to and returned from the API.
FastAPI uses them to validate requests automatically.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from .config import get_settings

_settings = get_settings()

# SQLite does not store time zones; all our times are saved in UTC,
# so mark them as UTC before sending them to the browser.
UTCDateTime = Annotated[datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc))]


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


# ----------------------------- Chat -----------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., max_length=_settings.max_message_length)
    conversation_id: int | None = None

    _check = field_validator("message")(_strip_required)


class RegenerateRequest(BaseModel):
    conversation_id: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    timestamp: UTCDateTime


class ChatResponse(BaseModel):
    conversation_id: int
    title: str
    user_message: MessageOut
    assistant_message: MessageOut


# ----------------------------- History -----------------------------
class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: UTCDateTime
    updated_at: UTCDateTime
    message_count: int


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: UTCDateTime
    updated_at: UTCDateTime
    messages: list[MessageOut]


# ----------------------------- Summarizer -----------------------------
class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_settings.max_summary_text_length)
    length: Literal["short", "detailed"] = "short"

    @field_validator("text")
    @classmethod
    def enough_text(cls, value: str) -> str:
        value = value.strip()
        if len(value.split()) < 20:
            raise ValueError("please provide at least 20 words to summarize")
        return value


class SummarizeResponse(BaseModel):
    summary: str
    length: str
    original_words: int
    summary_words: int


# ----------------------------- Quiz -----------------------------
class QuizGenerateRequest(BaseModel):
    subject: str = Field(..., max_length=100)
    topic: str = Field(..., max_length=200)
    num_questions: Literal[5, 10] = 5
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    _check = field_validator("subject", "topic")(_strip_required)


class QuizQuestionOut(BaseModel):
    number: int
    question: str
    options: list[str]


class QuizGenerateResponse(BaseModel):
    quiz_id: str
    subject: str
    topic: str
    difficulty: str
    questions: list[QuizQuestionOut]


class QuizSubmitRequest(BaseModel):
    quiz_id: str = Field(..., min_length=1, max_length=64)
    # One entry per question: the chosen option index (0-3) or null if skipped
    answers: list[int | None]

    @field_validator("answers")
    @classmethod
    def valid_answers(cls, answers: list[int | None]) -> list[int | None]:
        for a in answers:
            if a is not None and not 0 <= a <= 3:
                raise ValueError("each answer must be between 0 and 3 or null")
        return answers


class QuizReviewItem(BaseModel):
    question: str
    options: list[str]
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str


class QuizSubmitResponse(BaseModel):
    result_id: int
    topic: str
    difficulty: str
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered: int
    score_percentage: float
    review: list[QuizReviewItem]
