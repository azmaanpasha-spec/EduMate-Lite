"""
AI service: the ONLY module that talks to Google Gemini.

Every other part of the app calls `AIService.generate(...)`. Any problem
(missing key, bad key, rate limit, timeout, ...) is converted into an
`AIServiceError` with a student-friendly message, so the API never leaks
raw stack traces or secrets to the browser.
"""

import logging

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ..config import get_settings

logger = logging.getLogger("edumate.ai")


class AIServiceError(Exception):
    """A problem with the AI provider, with a message that is safe to show users."""

    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


NOT_CONFIGURED_MESSAGE = (
    "The AI assistant is not configured yet. Add your Gemini API key as "
    "GEMINI_API_KEY in the backend/.env file and restart the server. "
    "You can get a free key at https://aistudio.google.com/apikey"
)


def classify_api_error(code: int, status: str | None, message: str | None, model: str) -> AIServiceError:
    """Turn an HTTP error from Gemini into a friendly AIServiceError."""
    msg = (message or "").lower()
    status = (status or "").upper()

    if code in (401, 403) or "api key" in msg or "api_key" in msg:
        return AIServiceError(
            "invalid_api_key",
            "Your Gemini API key was rejected. Please check GEMINI_API_KEY in backend/.env "
            "and restart the server.",
            502,
        )
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        # Gemini uses 429 both for per-minute limits and for exhausted daily quota.
        # Daily quota messages mention a per-day metric (or a limit of 0).
        if any(w in msg for w in ("perday", "per_day", "per day", "daily", "limit: 0")):
            return AIServiceError(
                "quota_exceeded",
                "The daily Gemini API quota for this key has been used up. Please try again "
                "after the quota resets, or use a different API key.",
                429,
            )
        return AIServiceError(
            "rate_limited",
            "EduMate is receiving too many requests right now. Please wait about a minute and try again.",
            429,
        )
    if code == 404:
        return AIServiceError(
            "model_not_found",
            f"The AI model '{model}' is not available for this API key. Set a valid model name "
            "as GEMINI_MODEL in backend/.env (for example gemini-3.5-flash) and restart.",
            502,
        )
    if code == 504 or status == "DEADLINE_EXCEEDED":
        return AIServiceError(
            "ai_timeout",
            "The AI took too long to respond. Please try again (shorter questions are faster).",
            504,
        )
    if code >= 500:
        return AIServiceError(
            "ai_unavailable",
            "The Gemini AI service is temporarily unavailable. Please try again in a moment.",
            503,
        )
    return AIServiceError(
        "ai_request_rejected",
        "The AI could not process this request. Try rephrasing or shortening your input.",
        502,
    )


# Errors where trying another model can help (overloaded, slow or rate-limited model)
RETRYABLE_CODES = {"ai_unavailable", "ai_timeout", "rate_limited", "quota_exceeded", "model_not_found"}


class AIService:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
        fallback_models: list[str] | None = None,
        thinking_level: str = "",
    ):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        # Tried in order if the main model is overloaded or unavailable
        self.fallback_models = [m for m in (fallback_models or []) if m and m != model]
        self.thinking_level = (thinking_level or "").strip().upper()
        self._client: genai.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> genai.Client:
        if not self.configured:
            raise AIServiceError("ai_not_configured", NOT_CONFIGURED_MESSAGE, 503)
        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=self.timeout_seconds * 1000,  # milliseconds
                    # No automatic retries: we switch to a fallback model instead,
                    # which recovers faster when a model is overloaded.
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        json_output: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Send a conversation to Gemini and return the reply text.

        `messages` is a list of {"role": "user" | "assistant", "content": str}.
        If the main model fails with a temporary problem, the fallback models
        are tried one after another.
        """
        client = self._get_client()

        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json" if json_output else None,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level) if self.thinking_level else None,
        )

        last_error: AIServiceError | None = None
        for model in [self.model, *self.fallback_models]:
            try:
                text = self._call(client, model, contents, config)
                if model != self.model:
                    logger.info("Answered by fallback model %s", model)
                return text
            except AIServiceError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_CODES:
                    raise  # e.g. invalid API key: another model will not help
                logger.warning("Model %s failed (%s), trying next model", model, exc.code)
        raise last_error  # every model failed

    def _call(self, client: genai.Client, model: str, contents, config) -> str:
        """One request to one model. Converts every failure into AIServiceError."""
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
        except genai_errors.APIError as exc:
            logger.warning("Gemini API error %s %s: %s", exc.code, exc.status, (exc.message or "")[:200])
            raise classify_api_error(exc.code or 0, exc.status, exc.message, model) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Gemini request timed out (%s)", model)
            raise AIServiceError(
                "ai_timeout",
                "The AI took too long to respond. Please try again (shorter questions are faster).",
                504,
            ) from exc
        except httpx.TransportError as exc:
            logger.warning("Network error contacting Gemini: %s", type(exc).__name__)
            raise AIServiceError(
                "network_error",
                "Could not reach the Gemini AI service. Please check your internet connection.",
                503,
            ) from exc
        except Exception as exc:  # anything unexpected from the SDK
            logger.exception("Unexpected error while calling Gemini")
            raise AIServiceError(
                "ai_error", "Something went wrong while contacting the AI. Please try again.", 502
            ) from exc

        text = None
        try:
            text = response.text
        except Exception:  # some SDK versions raise when there are no text parts
            text = None

        if not text or not text.strip():
            feedback = getattr(response, "prompt_feedback", None)
            if feedback is not None and getattr(feedback, "block_reason", None):
                raise AIServiceError(
                    "ai_blocked",
                    "The AI declined to answer this request for safety reasons. Please rephrase it.",
                    422,
                )
            raise AIServiceError(
                "invalid_ai_response", "The AI returned an empty response. Please try again.", 502
            )
        return text.strip()


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """FastAPI dependency. Tests replace this with a fake AI service."""
    global _ai_service
    if _ai_service is None:
        settings = get_settings()
        _ai_service = AIService(
            settings.gemini_api_key,
            settings.model_name,
            settings.ai_timeout_seconds,
            fallback_models=settings.fallback_model_list,
            thinking_level=settings.gemini_thinking_level,
        )
    return _ai_service
