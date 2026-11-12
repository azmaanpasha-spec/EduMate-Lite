@echo off
REM One-time setup for EduMate Lite on a new computer.
REM Creates the Python environment, installs the packages and creates backend\.env
cd /d "%~dp0"

echo.
echo === EduMate Lite setup ===
echo.

REM 1. Find Python 3.12 (py launcher first, then python on PATH)
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  python --version 2>nul | findstr /C:"Python 3.12" >nul && set "PY=python"
)
if not defined PY (
  echo Python 3.12 was not found.
  echo Install it from https://www.python.org/downloads/ and tick "Add Python to PATH",
  echo then run setup.bat again.
  pause
  exit /b 1
)
echo [1/3] Using %PY%

REM 2. Virtual environment + packages
if not exist "backend\.venv\Scripts\python.exe" (
  echo [2/3] Creating virtual environment...
  %PY% -m venv backend\.venv || (echo Could not create the virtual environment. & pause & exit /b 1)
) else (
  echo [2/3] Virtual environment already exists.
)
echo       Installing packages (this needs internet and can take a few minutes)...
backend\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
backend\.venv\Scripts\python.exe -m pip install --quiet -r backend\requirements.txt || (echo Package installation failed. Check your internet connection. & pause & exit /b 1)

REM 3. Configuration file with the API key
if not exist "backend\.env" (
  copy /y ".env.example" "backend\.env" >nul
  echo [3/3] Created backend\.env - Notepad will open: paste your key after GEMINI_API_KEY= and save.
  start /wait notepad "backend\.env"
) else (
  echo [3/3] backend\.env already exists - keeping your settings.
)

echo.
echo Setup complete! Double-click run.bat to start EduMate Lite.
echo Then open http://127.0.0.1:8000 in your browser.
echo.
pause
