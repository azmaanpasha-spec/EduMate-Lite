@echo off
REM Starts EduMate Lite at http://127.0.0.1:8000
cd /d "%~dp0backend"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run the installation steps in README.md first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo Opening EduMate Lite at http://127.0.0.1:8000  (API docs: http://127.0.0.1:8000/docs)
uvicorn app.main:app --reload
