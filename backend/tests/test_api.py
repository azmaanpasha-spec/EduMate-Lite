"""
Backend tests for EduMate Lite. Run from the backend folder:  pytest -v
"""

from app.config import get_settings
from app.services.ai_service import AIService, AIServiceError, classify_api_error
from app.services.chat_service import make_title
from app.services.quiz_service import parse_questions

from .conftest import make_quiz_json

import pytest


# ----------------------------- Startup & health -----------------------------
def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "EduMate" in r.text
    assert client.get("/css/style.css").status_code == 200
    assert client.get("/js/app.js").status_code == 200


def test_health_reports_status_without_secrets(client_without_ai):
    r = client_without_ai.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["ai"]["configured"] is False
    assert data["ai"]["model"]
    assert "key" not in str(data).lower().replace("configured", "")


def test_database_tables_created(client):
    from sqlalchemy import inspect

    from app.database import engine

    tables = set(inspect(engine).get_table_names())
    assert {"conversations", "messages", "quiz_results"} <= tables


# ----------------------------- Chat -----------------------------
def test_chat_creates_conversation_and_saves_messages(client, fake_ai):
    r = client.post("/api/chat", json={"message": "What is photosynthesis?"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "What is photosynthesis?"
    assert data["user_message"]["role"] == "user"
    assert data["assistant_message"]["content"] == "Fake answer #1"
    assert data["assistant_message"]["timestamp"].endswith(("Z", "+00:00"))

    # The EduMate system prompt is used
    assert "You are EduMate" in fake_ai.calls[0]["system"]

    detail = client.get(f"/api/history/{data['conversation_id']}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_chat_sends_conversation_context(client, fake_ai):
    first = client.post("/api/chat", json={"message": "Explain recursion"}).json()
    client.post("/api/chat", json={"message": "Give me an example", "conversation_id": first["conversation_id"]})

    sent = fake_ai.calls[1]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[0]["content"] == "Explain recursion"
    assert sent[-1]["content"] == "Give me an example"


def test_chat_context_window_is_limited(client, fake_ai):
    limit = get_settings().chat_context_messages
    conv = client.post("/api/chat", json={"message": "message 0"}).json()["conversation_id"]
    for i in range(1, limit + 3):
        client.post("/api/chat", json={"message": f"message {i}", "conversation_id": conv})

    last_call = fake_ai.calls[-1]["messages"]
    assert len(last_call) <= limit
    assert last_call[0]["role"] == "user"  # window always starts with a user message
    assert last_call[-1]["content"] == f"message {limit + 2}"


def test_chat_rejects_empty_and_too_long_messages(client):
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422
    too_long = "a" * (get_settings().max_message_length + 1)
    r = client.post("/api/chat", json={"message": too_long})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_chat_unknown_conversation_returns_404(client):
    r = client.post("/api/chat", json={"message": "hi", "conversation_id": 999})
    assert r.status_code == 404


def test_ai_failure_returns_friendly_error_and_saves_nothing(client, fake_ai):
    fake_ai.error = AIServiceError("rate_limited", "Too many requests, please wait.", 429)
    r = client.post("/api/chat", json={"message": "Hello"})
    assert r.status_code == 429
    assert r.json() == {"detail": "Too many requests, please wait.", "error_code": "rate_limited"}
    assert client.get("/api/history").json() == []


def test_missing_api_key_gives_setup_message(client_without_ai):
    r = client_without_ai.post("/api/chat", json={"message": "Hello"})
    assert r.status_code == 503
    body = r.json()
    assert body["error_code"] == "ai_not_configured"
    assert "GEMINI_API_KEY" in body["detail"]
    # The rest of the app keeps working
    assert client_without_ai.get("/api/history").status_code == 200


def test_regenerate_replaces_last_answer(client, fake_ai):
    conv = client.post("/api/chat", json={"message": "What is an atom?"}).json()["conversation_id"]
    fake_ai.replies = ["A better answer"]
    r = client.post("/api/chat/regenerate", json={"conversation_id": conv})
    assert r.status_code == 200
    assert r.json()["content"] == "A better answer"

    messages = client.get(f"/api/history/{conv}").json()["messages"]
    assert [m["content"] for m in messages] == ["What is an atom?", "A better answer"]
    # The AI was asked the same question again
    assert fake_ai.calls[-1]["messages"][-1]["content"] == "What is an atom?"


def test_regenerate_failure_keeps_old_answer(client, fake_ai):
    conv = client.post("/api/chat", json={"message": "Question"}).json()["conversation_id"]
    fake_ai.error = AIServiceError("ai_timeout", "Timed out", 504)
    assert client.post("/api/chat/regenerate", json={"conversation_id": conv}).status_code == 504
    messages = client.get(f"/api/history/{conv}").json()["messages"]
    assert messages[-1]["content"] == "Fake answer #1"


# ----------------------------- History -----------------------------
def test_history_list_order_and_counts(client):
    a = client.post("/api/chat", json={"message": "First chat"}).json()["conversation_id"]
    b = client.post("/api/chat", json={"message": "Second chat"}).json()["conversation_id"]
    client.post("/api/chat", json={"message": "Follow up", "conversation_id": a})

    history = client.get("/api/history").json()
    assert [c["id"] for c in history] == [a, b]  # most recently updated first
    assert history[0]["message_count"] == 4


def test_delete_conversation(client):
    conv = client.post("/api/chat", json={"message": "To be deleted"}).json()["conversation_id"]
    assert client.delete(f"/api/history/{conv}").status_code == 200
    assert client.get(f"/api/history/{conv}").status_code == 404
    assert client.delete(f"/api/history/{conv}").status_code == 404

    # Messages were removed too (cascade)
    from app.database import SessionLocal
    from app.models import Message

    with SessionLocal() as db:
        assert db.query(Message).filter_by(conversation_id=conv).count() == 0


def test_clear_history(client):
    client.post("/api/chat", json={"message": "One"})
    client.post("/api/chat", json={"message": "Two"})
    r = client.delete("/api/history")
    assert r.json() == {"deleted_conversations": 2}
    assert client.get("/api/history").json() == []


def test_history_persists_across_restart(client):
    conv = client.post("/api/chat", json={"message": "Remember me"}).json()["conversation_id"]
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as restarted:  # new app lifespan, same database file
        assert restarted.get(f"/api/history/{conv}").json()["title"] == "Remember me"


def test_title_generation():
    assert make_title("  What   is\nphotosynthesis? ") == "What is photosynthesis?"
    long_title = make_title("Explain " + "very " * 30 + "long question")
    assert len(long_title) <= 53 and long_title.endswith("...")


# ----------------------------- Summarizer -----------------------------
LONG_TEXT = " ".join(["Photosynthesis converts light energy into chemical energy in plants."] * 5)


def test_summarize_short_and_detailed(client, fake_ai):
    fake_ai.replies = ["- point one\n- point two", "## Overview\nDetailed text"]
    short = client.post("/api/summarize", json={"text": LONG_TEXT, "length": "short"})
    assert short.status_code == 200
    assert short.json()["summary"].startswith("- point one")
    assert short.json()["original_words"] == len(LONG_TEXT.split())
    assert "SHORT" in fake_ai.calls[0]["messages"][0]["content"]
    assert LONG_TEXT in fake_ai.calls[0]["messages"][0]["content"]

    detailed = client.post("/api/summarize", json={"text": LONG_TEXT, "length": "detailed"})
    assert detailed.json()["length"] == "detailed"
    assert "DETAILED" in fake_ai.calls[1]["messages"][0]["content"]


def test_summarize_validation(client):
    assert client.post("/api/summarize", json={"text": "", "length": "short"}).status_code == 422
    assert client.post("/api/summarize", json={"text": "too short text", "length": "short"}).status_code == 422
    assert client.post("/api/summarize", json={"text": LONG_TEXT, "length": "medium"}).status_code == 422
    huge = "word " * (get_settings().max_summary_text_length // 5 + 10)
    assert client.post("/api/summarize", json={"text": huge}).status_code == 422


# ----------------------------- Quiz -----------------------------
QUIZ_BODY = {"subject": "Physics", "topic": "Newton's laws", "num_questions": 5, "difficulty": "easy"}


def test_quiz_generate_hides_answers(client, fake_ai):
    fake_ai.replies = [make_quiz_json(5)]
    r = client.post("/api/quiz/generate", json=QUIZ_BODY)
    assert r.status_code == 200
    data = r.json()
    assert len(data["questions"]) == 5
    assert all(len(q["options"]) == 4 for q in data["questions"])
    assert "answer_index" not in r.text and "explanation" not in r.text
    assert fake_ai.calls[0]["json"] is True


def test_quiz_generate_validation(client):
    for bad in (
        {**QUIZ_BODY, "num_questions": 7},
        {**QUIZ_BODY, "difficulty": "expert"},
        {**QUIZ_BODY, "topic": "  "},
    ):
        assert client.post("/api/quiz/generate", json=bad).status_code == 422


def test_quiz_generate_retries_on_bad_ai_output(client, fake_ai):
    fake_ai.replies = ["this is not json", make_quiz_json(5)]
    assert client.post("/api/quiz/generate", json=QUIZ_BODY).status_code == 200
    assert len(fake_ai.calls) == 2


def test_quiz_generate_fails_cleanly_on_repeated_bad_output(client, fake_ai):
    fake_ai.replies = ['{"questions": []}', "nope"]
    r = client.post("/api/quiz/generate", json=QUIZ_BODY)
    assert r.status_code == 502
    assert r.json()["error_code"] == "invalid_ai_response"


def test_quiz_scoring_and_result_saved(client, fake_ai):
    fake_ai.replies = [make_quiz_json(5, answer_index=2)]
    quiz = client.post("/api/quiz/generate", json=QUIZ_BODY).json()

    answers = [2, 2, 2, 0, None]  # 3 correct, 1 wrong, 1 skipped
    r = client.post("/api/quiz/submit", json={"quiz_id": quiz["quiz_id"], "answers": answers})
    assert r.status_code == 200
    res = r.json()
    assert res["total_questions"] == 5
    assert res["correct_answers"] == 3
    assert res["incorrect_answers"] == 2
    assert res["unanswered"] == 1
    assert res["score_percentage"] == 60.0
    assert res["review"][3]["is_correct"] is False and res["review"][3]["correct_index"] == 2
    assert res["review"][0]["explanation"] == "Explanation 1."

    from app.database import SessionLocal
    from app.models import QuizResult

    with SessionLocal() as db:
        saved = db.get(QuizResult, res["result_id"])
        assert saved.correct_answers == 3 and saved.score_percentage == 60.0
        assert saved.topic == "Physics - Newton's laws"

    # A quiz can only be submitted once
    again = client.post("/api/quiz/submit", json={"quiz_id": quiz["quiz_id"], "answers": answers})
    assert again.status_code == 404


def test_quiz_submit_validation(client, fake_ai):
    fake_ai.replies = [make_quiz_json(5)]
    quiz = client.post("/api/quiz/generate", json=QUIZ_BODY).json()
    assert client.post("/api/quiz/submit", json={"quiz_id": quiz["quiz_id"], "answers": [0, 1]}).status_code == 422
    assert client.post("/api/quiz/submit", json={"quiz_id": quiz["quiz_id"], "answers": [0, 1, 2, 3, 4]}).status_code == 422
    assert client.post("/api/quiz/submit", json={"quiz_id": "unknown", "answers": [0] * 5}).status_code == 404


def test_parse_questions_cleans_and_validates():
    raw = '```json\n{"questions": [{"question": "Q?", "options": ["A) one", "B) two", "C) three", "D) four"], "answer_index": 0, "explanation": "E"}]}\n```'
    questions = parse_questions(raw, 1)
    assert questions[0].options == ["one", "two", "three", "four"]

    with pytest.raises(ValueError):
        parse_questions('{"questions": [{"question": "Q?", "options": ["a", "a", "b", "c"], "answer_index": 0, "explanation": "E"}]}', 1)
    with pytest.raises(ValueError):
        parse_questions('{"questions": [{"question": "Q?", "options": ["a", "b", "c", "d"], "answer_index": 5, "explanation": "E"}]}', 1)


# ----------------------------- AI error mapping -----------------------------
def test_ai_service_without_key_raises_setup_error():
    with pytest.raises(AIServiceError) as exc:
        AIService("", "any-model").generate("system", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "ai_not_configured"
    assert exc.value.status_code == 503


@pytest.mark.parametrize(
    "code,status,message,expected",
    [
        (400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", "invalid_api_key"),
        (403, "PERMISSION_DENIED", "Permission denied", "invalid_api_key"),
        (429, "RESOURCE_EXHAUSTED", "Rate limit exceeded, retry shortly", "rate_limited"),
        (429, "RESOURCE_EXHAUSTED", "You exceeded your current quota, please check your plan and billing details. "
         "Quota exceeded for metric: generate_content_free_tier_requests, limit: 15. Please retry in 30s.", "rate_limited"),
        (429, "RESOURCE_EXHAUSTED", "You exceeded your current quota. Quota exceeded for metric: "
         "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quota_exceeded"),
        (404, "NOT_FOUND", "models/xyz is not found", "model_not_found"),
        (503, "UNAVAILABLE", "The model is overloaded", "ai_unavailable"),
        (504, "DEADLINE_EXCEEDED", "Deadline expired before operation could complete.", "ai_timeout"),
        (400, "INVALID_ARGUMENT", "Request contains an invalid argument", "ai_request_rejected"),
    ],
)
def test_classify_api_error(code, status, message, expected):
    err = classify_api_error(code, status, message, "test-model")
    assert err.code == expected
    assert "Traceback" not in err.message


def test_network_and_timeout_errors_are_friendly(monkeypatch):
    import httpx

    service = AIService("fake-key", "test-model", timeout_seconds=1)
    client = service._get_client()

    def boom_timeout(**_kwargs):
        raise httpx.ReadTimeout("timed out")

    def boom_network(**_kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(client.models, "generate_content", boom_timeout)
    with pytest.raises(AIServiceError) as exc:
        service.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "ai_timeout"

    monkeypatch.setattr(client.models, "generate_content", boom_network)
    with pytest.raises(AIServiceError) as exc:
        service.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "network_error"


def test_empty_ai_response_is_rejected(monkeypatch):
    class EmptyResponse:
        text = None
        prompt_feedback = None

    service = AIService("fake-key", "test-model")
    monkeypatch.setattr(service._get_client().models, "generate_content", lambda **_k: EmptyResponse())
    with pytest.raises(AIServiceError) as exc:
        service.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "invalid_ai_response"


# ----------------------------- Model fallback -----------------------------
class _Resp:
    def __init__(self, text):
        self.text = text
        self.prompt_feedback = None


def _fake_generate(results, calls):
    """Returns the next queued result per call; exceptions are raised."""
    def generate_content(model, contents, config):
        calls.append(model)
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return _Resp(result)
    return generate_content


def test_fallback_model_used_when_main_model_overloaded(monkeypatch):
    from google.genai import errors as genai_errors

    overloaded = genai_errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    service = AIService("fake-key", "main-model", fallback_models=["backup-model"], thinking_level="low")
    calls = []
    monkeypatch.setattr(service._get_client().models, "generate_content", _fake_generate([overloaded, "backup answer"], calls))
    assert service.generate("s", [{"role": "user", "content": "hi"}]) == "backup answer"
    assert calls == ["main-model", "backup-model"]


def test_no_fallback_for_invalid_api_key(monkeypatch):
    from google.genai import errors as genai_errors

    bad_key = genai_errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}})
    service = AIService("fake-key", "main-model", fallback_models=["backup-model"])
    calls = []
    monkeypatch.setattr(service._get_client().models, "generate_content", _fake_generate([bad_key], calls))
    with pytest.raises(AIServiceError) as exc:
        service.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "invalid_api_key"
    assert calls == ["main-model"]


def test_all_models_failing_returns_last_friendly_error(monkeypatch):
    import httpx

    service = AIService("fake-key", "main-model", fallback_models=["backup-model"])
    calls = []
    monkeypatch.setattr(service._get_client().models, "generate_content",
                        _fake_generate([httpx.ReadTimeout("t"), httpx.ReadTimeout("t")], calls))
    with pytest.raises(AIServiceError) as exc:
        service.generate("s", [{"role": "user", "content": "hi"}])
    assert exc.value.code == "ai_timeout"
    assert calls == ["main-model", "backup-model"]


def test_summary_word_limit_is_shorter_than_original():
    from app.routes.summarize import word_limit

    for words in (20, 186, 1000, 4000):
        assert word_limit(words, "short") < max(words, 31)
        assert word_limit(words, "short") < word_limit(words, "detailed")
    assert word_limit(186, "detailed") == 93
