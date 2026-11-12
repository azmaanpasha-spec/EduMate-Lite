"""
Application configuration.

All settings are read from environment variables or a `.env` file.
The `.env` file is looked up in the `backend/` folder first and then in the
project root, so either location works.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../EduMate-Lite/backend
PROJECT_DIR = BACKEND_DIR.parent  # .../EduMate-Lite
FRONTEND_DIR = PROJECT_DIR / "frontend"

# Used only when GEMINI_MODEL is left empty in .env
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


class Settings(BaseSettings):
    # --- AI provider ---
    gemini_api_key: str = ""
    gemini_model: str = ""
    # Comma-separated models tried when the main model is overloaded or unavailable
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    # minimal / low / medium / high, or empty for the model default. "low" answers faster.
    gemini_thinking_level: str = "low"
    # Per model attempt. Worst case = timeout x (1 + number of fallback models)
    ai_timeout_seconds: int = 30

    # --- Database ---
    database_url: str = "sqlite:///./edumate.db"

    # --- App ---
    app_env: str = "development"

    # How many recent messages are sent to Gemini as conversation context
    chat_context_messages: int = 12

    # Input limits (characters)
    max_message_length: int = 4000
    max_summary_text_length: int = 20000

    # Later files win, so backend/.env overrides a root .env
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]

    @property
    def model_name(self) -> str:
        return self.gemini_model.strip() or DEFAULT_GEMINI_MODEL


@lru_cache
def get_settings() -> Settings:
    return Settings()
