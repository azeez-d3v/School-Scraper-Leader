@echo off
echo Setting up environment...
if not exist ".venv" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Adding local UV to PATH...
set "PATH=%CD%;%PATH%"

echo Starting application...
uv run streamlit run main.py
if %errorlevel% neq 0 (
    echo Fallback: Starting streamlit directly...
    streamlit run main.py
)
