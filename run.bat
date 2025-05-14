@echo off
echo Checking environment setup...
if not exist ".venv" (
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Verifying critical dependencies...
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Streamlit not found. Running setup to fix...
    call setup.bat
    if %errorlevel% neq 0 (
        echo Setup failed. Please run setup.bat manually and check for errors.
        pause
        exit /b 1
    )
)

echo Starting application...
uv run streamlit run main.py
if %errorlevel% neq 0 (
    echo Fallback to direct streamlit execution...
    streamlit run main.py
)
