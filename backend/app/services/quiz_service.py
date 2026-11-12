"""
MCQ quiz logic: asking Gemini for questions, validating them and scoring answers.

Correct answers are kept on the server (in memory) and are only sent to the
browser after the quiz is submitted, so the score is always calculated by
the backend and cannot be faked from the browser.
"""

import json
import logging
import re
import uuid
from collections import OrderedDict

from pydantic import BaseModel, ValidationError, field_validator

from .ai_service import AIService, AIServiceError

logger = logging.getLogger("edumate.quiz")

QUIZ_SYSTEM_PROMPT = """You are EduMate, an academic assistant that writes high-quality multiple-choice questions for college students.
Questions must be factually correct, clearly worded and have exactly one correct option.
Always reply with valid JSON only, no Markdown and no extra text."""

LETTERS = "ABCD"


class MCQ(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str

    @field_validator("question", "explanation")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("options")
    @classmethod
    def four_unique_options(cls, options: list[str]) -> list[str]:
        # Remove "A) " / "B. " style prefixes the model sometimes adds
        cleaned = [re.sub(r"^\s*[A-Da-d][\).:-]\s+", "", str(o)).strip() for o in options]
        if len(cleaned) != 4 or any(not o for o in cleaned):
            raise ValueError("exactly four non-empty options are required")
        if len({o.lower() for o in cleaned}) != 4:
            raise ValueError("options must be different")
        return cleaned

    @field_validator("answer_index")
    @classmethod
    def valid_index(cls, value: int) -> int:
        if not 0 <= value <= 3:
            raise ValueError("answer_index must be between 0 and 3")
        return value


def build_prompt(subject: str, topic: str, count: int, difficulty: str) -> str:
    return f"""Create {count} {difficulty} multiple-choice questions.
Subject: {subject}
Topic: {topic}

Return a JSON object with this exact shape:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0, "explanation": "..."}}]}}

Rules:
- Exactly {count} questions, each with exactly 4 different options.
- "answer_index" is the 0-based index (0-3) of the single correct option.
- Vary the position of the correct option between questions.
- "explanation" is 1-2 sentences explaining why the answer is correct.
- Do not put letters like "A)" in front of the options."""


def _extract_json(text: str):
    text = text.strip()
    # Strip ```json ... ``` fences if the model added them anyway
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def parse_questions(raw_text: str, count: int) -> list[MCQ]:
    """Validate the AI output. Raises ValueError if it is not usable."""
    try:
        data = _extract_json(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response was not valid JSON") from exc

    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("AI response did not contain a question list")

    questions = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            questions.append(MCQ(**item))
        except (ValidationError, TypeError):
            continue  # skip a single broken question

    if len(questions) < count:
        raise ValueError(f"only {len(questions)} valid questions out of {count}")
    return questions[:count]


def generate_questions(ai: AIService, subject: str, topic: str, count: int, difficulty: str) -> list[MCQ]:
    """Ask the AI for questions. Retries once if the output is malformed."""
    prompt = build_prompt(subject, topic, count, difficulty)
    last_error = ""
    for _attempt in range(2):
        raw = ai.generate(QUIZ_SYSTEM_PROMPT, [{"role": "user", "content": prompt}], json_output=True)
        try:
            return parse_questions(raw, count)
        except ValueError as exc:
            last_error = str(exc)
            logger.warning("Invalid quiz output from AI: %s", last_error)
    raise AIServiceError(
        "invalid_ai_response",
        "The AI returned questions in an unexpected format. Please try generating the quiz again.",
        502,
    )


# ---------------------------------------------------------------------------
# Active quizzes are kept in memory until they are submitted.
# ---------------------------------------------------------------------------
MAX_ACTIVE_QUIZZES = 200
_active_quizzes: "OrderedDict[str, dict]" = OrderedDict()


def store_quiz(subject: str, topic: str, difficulty: str, questions: list[MCQ]) -> str:
    quiz_id = uuid.uuid4().hex
    _active_quizzes[quiz_id] = {
        "subject": subject,
        "topic": topic,
        "difficulty": difficulty,
        "questions": questions,
    }
    while len(_active_quizzes) > MAX_ACTIVE_QUIZZES:
        _active_quizzes.popitem(last=False)  # forget the oldest quiz
    return quiz_id


def get_quiz(quiz_id: str) -> dict | None:
    return _active_quizzes.get(quiz_id)


def remove_quiz(quiz_id: str) -> None:
    _active_quizzes.pop(quiz_id, None)


def score_quiz(questions: list[MCQ], answers: list[int | None]) -> dict:
    """Compare the student's answers with the correct ones."""
    review = []
    correct = 0
    for q, selected in zip(questions, answers):
        is_correct = selected == q.answer_index
        correct += is_correct
        review.append(
            {
                "question": q.question,
                "options": q.options,
                "selected_index": selected,
                "correct_index": q.answer_index,
                "is_correct": is_correct,
                "explanation": q.explanation,
            }
        )
    total = len(questions)
    unanswered = sum(1 for a in answers if a is None)
    return {
        "total_questions": total,
        "correct_answers": correct,
        "incorrect_answers": total - correct,
        "unanswered": unanswered,
        "score_percentage": round(correct / total * 100, 1) if total else 0.0,
        "review": review,
    }
