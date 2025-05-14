@echo off
echo ========================================
echo School Scraper Leader - Setup Process
echo ========================================
echo.

echo Checking if UV package manager is installed...
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo UV is already installed.
) else (
    echo UV is not installed. Installing UV package manager...
    powershell -ExecutionPolicy ByPass -c "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://astral.sh/uv/install.ps1 | iex"
)

echo.
echo Checking if virtual environment exists...
if exist ".venv" (
    echo Virtual environment already exists, skipping creation.
) else (
    echo Creating virtual environment with Python 3.13.3...
    uv venv --python 3.13.3
)

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Checking if pyproject.toml exists...
if exist "pyproject.toml" (
    echo pyproject.toml already exists, skipping initialization.
) else (
    echo Initializing project with UV...
    uv init
)

echo.
echo Installing required packages from requirements.txt...
uv add -r requirements.txt

echo.
echo Creating output directories if they don't exist...
if not exist "output" mkdir output
if not exist "output\raw_data" mkdir output\raw_data
if not exist "output\parsed_data" mkdir output\parsed_data

echo.
echo Creating .env file if it doesn't exist...
if not exist ".env" (
    echo GOOGLE_API_KEY=apikey> .env
    echo Created .env file with default GOOGLE_API_KEY
) else (
    echo .env file already exists
)

echo.
echo ========================================
echo Setup complete!
echo.
echo To run the application, use: 
echo     run.bat
echo or:
echo     .venv\Scripts\activate.bat ^&^& uv run streamlit run main.py
echo ========================================

echo.
pause
