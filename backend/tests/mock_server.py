"""
FOR TESTING THE USER INTERFACE ONLY - not part of the real application.

Starts EduMate with a mock AI (no API key, no network) and a separate
database, so every button can be clicked through in the browser.
Every mock reply is clearly labelled "[Mock AI]" so it can never be
mistaken for a real Gemini answer.

    cd backend
    .venv\\Scripts\\python tests\\mock_server.py      ->  http://127.0.0.1:8001
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.gettempdir()) / "edumate-mock.db").replace("\\", "/")
os.environ["GEMINI_API_KEY"] = "mock"  # only so the UI does not show the setup banner
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402
import time  # noqa: E402

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402
from app.services.ai_service import get_ai_service  # noqa: E402


class MockAI:
    configured = True

    def generate(self, system_prompt, messages, json_output=False, temperature=0.7):
        time.sleep(0.8)  # lets the loading animations be seen
        last = messages[-1]["content"]
        if json_output:
            count = 10 if "Create 10" in last else 5
            return json.dumps({"questions": [
                {
                    "question": f"[Mock AI] Sample question {i + 1}: which option is correct?",
                    "options": ["Option one", "Option two", "Option three", "Option four"],
                    "answer_index": i % 4,
                    "explanation": f"[Mock AI] Option {['one', 'two', 'three', 'four'][i % 4]} is the mock answer.",
                } for i in range(count)
            ]})
        if "Text to summarize" in last:
            return "**[Mock AI] summary**\n\n- First key point\n- Second key point\n- Third key point"
        history = len(messages) // 2
        return (
            f"## [Mock AI] reply\n\nYou asked: *{last[:80]}*\n\n"
            f"- Messages of context received: **{len(messages)}** ({history} earlier exchanges)\n"
            f"- Temperature: `{temperature}`\n\n"
            "```python\ndef hello():\n    return '<b>not bold</b>'\n```\n\n"
            "| Column | Value |\n|---|---|\n| HTML test | <script>alert(1)</script> |"
        )


app.dependency_overrides[get_ai_service] = lambda: MockAI()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
