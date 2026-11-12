# EduMate Lite 🎓

**Your Personal AI Study Assistant**: an AI chatbot mini-project built with FastAPI, SQLite and Google Gemini.

---

## 1. Introduction

EduMate Lite is a web-based conversational AI assistant for college students. A student can ask academic questions in plain language and get clear explanations, examples and step-by-step answers. Two learning tools are built on the same AI: a **text summarizer** and an **MCQ quiz generator**. All conversations are saved, so a student can reopen and continue them later.

## 2. Abstract

The application has a vanilla HTML/CSS/JavaScript frontend and a Python FastAPI backend. The backend sends the student's message, together with a limited window of recent conversation history, to Google's Gemini large language model through the official `google-genai` SDK. A system prompt makes the model behave as a friendly academic tutor. Conversations, messages and quiz results are stored in SQLite through SQLAlchemy. The API key stays on the server and is never sent to the browser. Every failure (missing key, rate limits, timeouts, network errors) is turned into a clear message for the user.

## 3. Problem Statement

Students often get stuck on difficult concepts outside class hours, struggle to condense long notes, and lack quick ways to test themselves. Generic search results are scattered and not tailored to the student's level. Students need a single, simple assistant that explains topics in easy language, remembers the context of their questions, summarizes study material, and generates practice questions on demand.

## 4. Objectives

1. Build a conversational AI tutor that answers academic questions accurately and simply.
2. Maintain conversation context so follow-up questions work naturally.
3. Persist chat history so students can return to previous conversations.
4. Provide an AI text summarizer with short and detailed modes.
5. Provide an interactive MCQ quiz generator with server-side scoring.
6. Deliver a modern, responsive and accessible user interface.
7. Handle AI and network failures gracefully without crashing.

## 5. Main Features

| Feature | Details |
|---|---|
| 💬 **AI Chat** | Real Gemini answers, Markdown formatting, code blocks, conversation context, typing indicator, timestamps |
| 📋 **Copy / Regenerate** | Copy any answer (or a code block); regenerate the latest answer |
| 🗂️ **Chat History** | Saved in SQLite; open, continue, delete one or clear all (with confirmation) |
| 📝 **Summarizer** | Paste text, choose *Short* or *Detailed*, copy the summary |
| ✅ **MCQ Quiz** | Subject, topic, 5 or 10 questions, Easy/Medium/Hard; one question at a time, progress bar, Previous/Next, results with explanations |
| 🎨 **UI** | Dark theme by default, light/dark toggle (saved), responsive for desktop, tablet and mobile |
| 🛡️ **Safety** | API key only on the server, input validation and length limits, HTML-escaped rendering, friendly error messages |

## 6. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript (ES modules), Lucide icons, Plus Jakarta Sans font |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| AI | Google Gemini via the official `google-genai` SDK |
| Database | SQLite + SQLAlchemy ORM |
| Testing | Pytest + HTTPX (FastAPI `TestClient`) |

> Bootstrap was left out on purpose: the custom CSS is smaller and gave full control over the design, so it wasn't needed.

## 7. System Architecture

```
┌──────────────────────── Browser ────────────────────────┐
│  index.html + style.css                                 │
│  app.js (theme, sidebar, views)                         │
│  chat.js · summarizer.js · quiz.js · markdown.js        │
└──────────────────────────┬──────────────────────────────┘
                           │  fetch() JSON  (/api/...)
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI  (app/main.py) — also serves the frontend      │
│   routes/  chat · history · summarize · quiz · health   │
│   services/ chat_service · quiz_service · ai_service    │
└───────────────┬───────────────────────────┬─────────────┘
                │ SQLAlchemy                │ google-genai SDK
        ┌───────▼────────┐          ┌───────▼────────┐
        │ SQLite         │          │ Google Gemini  │
        │ edumate.db     │          │ API            │
        └────────────────┘          └────────────────┘
```

**Chat flow:** the student sends a message, and the backend loads that conversation's last *N* messages (`CHAT_CONTEXT_MESSAGES`, default 12). It sends them to Gemini with the EduMate system prompt and saves the question and answer only after Gemini replies. If the main model is overloaded or times out, the backend automatically retries with the fallback models. If the AI fails, nothing is saved and the student can retry.

**Quiz flow:** Gemini returns the questions as JSON, and the backend validates them (4 different options, one valid answer index). The browser gets the questions **without the answers**. On submit, the backend scores the answers, saves the result in `quiz_results`, and only then sends back the correct answers and explanations.

### Database tables

| Table | Fields |
|---|---|
| `conversations` | id, title, created_at, updated_at |
| `messages` | id, conversation_id → conversations.id (cascade delete), role, content, timestamp |
| `quiz_results` | id, topic, difficulty, total_questions, correct_answers, score_percentage, created_at |

## 8. Folder Structure

```
EduMate-Lite/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, error handlers, serves frontend
│   │   ├── config.py          # settings from .env
│   │   ├── database.py        # SQLite engine & session
│   │   ├── models.py          # Conversation, Message, QuizResult tables
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── routes/            # chat.py, history.py, summarize.py, quiz.py
│   │   └── services/          # ai_service.py, chat_service.py, quiz_service.py
│   ├── tests/
│   │   ├── conftest.py        # temp database + fake AI for tests
│   │   ├── test_api.py        # automated tests
│   │   └── mock_server.py     # UI testing server with labelled mock AI
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/                    # app.js, chat.js, quiz.js, summarizer.js, markdown.js, utils.js
│   └── assets/logo.svg
├── .env.example
├── .gitignore
├── setup.bat                  # one-time setup on a new computer
├── run.bat                    # one-click start on Windows
└── README.md
```

## 9. Installation (Windows)

Requirements: **Python 3.12** ([python.org](https://www.python.org/downloads/)). Tick "Add Python to PATH" during installation.

### Quick setup (recommended)

1. Download the project: on GitHub click **Code → Download ZIP** and extract it, or run `git clone https://github.com/azmaanpasha-spec/EduMate-Lite.git`.
2. Double-click **`setup.bat`**. It creates the virtual environment, installs the packages and opens `backend\.env` in Notepad; paste your Gemini API key after `GEMINI_API_KEY=` and save.
3. Double-click **`run.bat`** and open http://127.0.0.1:8000.

### Manual setup

Open **Command Prompt** in the `EduMate-Lite` folder and run:

```bat
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 10. Gemini API Configuration

1. Get a free API key at **https://aistudio.google.com/apikey**.
2. Copy the example file into the backend folder (run this from the `EduMate-Lite` folder):
   ```bat
   copy .env.example backend\.env
   ```
3. Open `backend\.env` and set your key:
   ```
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=
   DATABASE_URL=sqlite:///./edumate.db
   APP_ENV=development
   ```
   Leave `GEMINI_MODEL` empty to use the default (`gemini-3.5-flash`), or set any model your key can use, e.g. `gemini-3.5-flash-lite` (faster). Older models such as `gemini-2.5-flash` are no longer available to new keys.
4. Restart the server after any change to `.env`.

`.env` is listed in `.gitignore`, so your key is never committed. **Without a key the app still runs:** history and the interface work, and AI features show setup instructions instead of answers.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Main model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Tried automatically if the main model is overloaded, slow or rate-limited |
| `GEMINI_THINKING_LEVEL` | `low` | Gemini reasoning effort (`minimal`/`low`/`medium`/`high`); `low` keeps answers fast |
| `DATABASE_URL` | `sqlite:///./edumate.db` | Database file (inside `backend/`) |
| `APP_ENV` | `development` | Shown in `/api/health` |
| `CHAT_CONTEXT_MESSAGES` | `12` | Recent messages sent to Gemini as context |
| `AI_TIMEOUT_SECONDS` | `30` | Timeout for each Gemini model attempt |

## 11. Running the Backend

```bat
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Or simply double-click **`run.bat`** in the project folder.

## 12. Opening the Application

| What | URL |
|---|---|
| EduMate Lite | **http://127.0.0.1:8000** |
| Swagger API docs | **http://127.0.0.1:8000/docs** |
| Health check | http://127.0.0.1:8000/api/health |

The green dot at the bottom of the sidebar shows that Gemini is configured.

## 13. API Documentation

Interactive documentation is generated automatically at `/docs`. Errors always look like `{"detail": "readable message", "error_code": "..."}`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Body `{message, conversation_id?}` → answer; creates a conversation if no id |
| `POST` | `/api/chat/regenerate` | Body `{conversation_id}` → new answer for the last question |
| `GET` | `/api/history` | List conversations (newest first, with message counts) |
| `GET` | `/api/history/{id}` | One conversation with its messages |
| `DELETE` | `/api/history/{id}` | Delete a conversation and its messages |
| `DELETE` | `/api/history` | Clear all history |
| `POST` | `/api/summarize` | Body `{text, length: "short" \| "detailed"}` → summary |
| `POST` | `/api/quiz/generate` | Body `{subject, topic, num_questions: 5 \| 10, difficulty}` → questions (no answers) |
| `POST` | `/api/quiz/submit` | Body `{quiz_id, answers: [0-3 or null, ...]}` → score, review, saved result |
| `GET` | `/api/health` | App, database and AI configuration status (no secrets) |

**Status codes:** `200` success · `404` not found · `422` invalid input · `429` rate limit / quota · `502` AI error or invalid key · `503` AI not configured or unavailable · `504` AI timeout.

**Example:**

```bat
curl -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" -d "{\"message\": \"What is Big O notation?\"}"
```

## 14. Testing

### Automated tests

The tests use a **fake AI** and a **temporary database**, so they need no API key, no internet and cost nothing:

```bat
cd backend
.venv\Scripts\activate
pytest -v
```

They cover: startup and frontend serving, database tables, health endpoint, chat and saved messages, conversation context and the context-window limit, input validation, missing-key behaviour, AI error handling (invalid key, rate limit, quota, model not found, timeout, network failure, empty response), regenerate, history listing, deleting (including cascade), clearing, persistence across restart, summarizer validation and prompts, quiz generation, JSON validation and retry, scoring, result saving, and preventing double submission.

### Testing the interface without an API key

```bat
cd backend
.venv\Scripts\activate
python tests\mock_server.py
```

Then open http://127.0.0.1:8001. This server uses a separate database and a mock AI whose replies are all labelled **"[Mock AI]"**, so every button can be tried. It is only for testing and is never used by the real app.

### Real AI test

With a valid key in `backend\.env`, start the app normally and:
1. Ask a question, then a follow-up such as "give me an example", to check that context is remembered.
2. Summarize the sample text in both modes.
3. Generate and submit a 5-question quiz.

---

*EduMate Lite is a college mini-project for the subject AI Chatbot.*
