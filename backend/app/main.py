"""
EduMate Lite - FastAPI application entry point.

Run from the `backend` folder:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from .config import FRONTEND_DIR, get_settings
from .database import check_db, init_db
from .routes import chat, history, quiz, summarize
from .services.ai_service import AIServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("edumate")
for _name in ("httpx", "httpx2", "google_genai.models"):
    logging.getLogger(_name).setLevel(logging.WARNING)  # do not log every outgoing AI request

APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    settings = get_settings()
    if settings.ai_configured:
        logger.info("Gemini AI configured (model: %s)", settings.model_name)
    else:
        logger.warning("GEMINI_API_KEY is not set - AI features will show a setup message.")
    yield


app = FastAPI(
    title="EduMate Lite API",
    description="Backend for EduMate Lite - Your Personal AI Study Assistant.",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ------------------------- Error handlers -------------------------
@app.exception_handler(AIServiceError)
async def ai_error_handler(_request: Request, exc: AIServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "error_code": exc.code})


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(_request: Request, exc: SQLAlchemyError):
    logger.exception("Database error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred. Please try again.", "error_code": "database_error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """Return one readable sentence instead of FastAPI's raw error list."""
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err.get("loc") else "input"
        text = err.get("msg", "is invalid").removeprefix("Value error, ")
        messages.append(f"{field.replace('_', ' ').capitalize()}: {text}")
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(messages) or "Invalid input.", "error_code": "validation_error"},
    )


# ------------------------- API routes -------------------------
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(summarize.router)
app.include_router(quiz.router)


@app.get("/api/health", tags=["Health"])
def health():
    """Application, database and AI configuration status (never exposes the key)."""
    settings = get_settings()
    db_ok = check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "version": APP_VERSION,
        "environment": settings.app_env,
        "database": "connected" if db_ok else "unavailable",
        "ai": {
            "provider": "Google Gemini",
            "configured": settings.ai_configured,
            "model": settings.model_name,
            "fallback_models": settings.fallback_model_list,
        },
    }


# ------------------------- Frontend -------------------------
# Mounted last so it never hides the /api routes. html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
