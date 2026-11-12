"""
Test setup.

- A temporary SQLite database is used, so tests never touch edumate.db.
- The real Gemini service is replaced with FakeAI, so tests need no API key,
  no network and cost nothing.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# These must be set BEFORE the app is imported
_tmp_dir = tempfile.mkdtemp(prefix="edumate-test-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp_dir) / "test.db").replace("\\", "/")
os.environ["GEMINI_API_KEY"] = ""  # the real AI is never used by default
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_service import AIServiceError, get_ai_service  # noqa: E402


def make_quiz_json(count: int, answer_index: int = 1) -> str:
    return json.dumps(
        {
            "questions": [
                {
                    "question": f"Sample question {i + 1}?",
                    "options": [f"Option A{i}", f"Option B{i}", f"Option C{i}", f"Option D{i}"],
                    "answer_index": answer_index,
                    "explanation": f"Explanation {i + 1}.",
                }
                for i in range(count)
            ]
        }
    )


class FakeAI:
    """Stands in for AIService. Records every call so tests can inspect them."""

    configured = True

    def __init__(self):
        self.calls = []
        self.replies = []  # queued replies; if empty a default reply is used
        self.error: AIServiceError | None = None

    def generate(self, system_prompt, messages, json_output=False, temperature=0.7):
        self.calls.append({"system": system_prompt, "messages": messages, "json": json_output})
        if self.error:
            raise self.error
        if self.replies:
            return self.replies.pop(0)
        return f"Fake answer #{len(self.calls)}"


@pytest.fixture
def fake_ai():
    return FakeAI()


@pytest.fixture
def client(fake_ai):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_ai_service] = lambda: fake_ai
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_without_ai():
    """Uses the REAL AIService with no API key configured."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
