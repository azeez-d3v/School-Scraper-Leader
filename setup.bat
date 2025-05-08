@echo off
echo ========================================
echo School Scraper Leader - Setup Process
echo ========================================
echo.

echo Installing UV package manager...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

echo.
echo Creating virtual environment with Python 3.13.3...
uv venv --python 3.13.3

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Initializing project with UV...
uv init

echo.
echo Installing required packages from requirements.txt...
uv add -r requirements.txt

echo.
echo Creating output directories if they don't exist...
if not exist "output" mkdir output
if not exist "output\raw_data" mkdir output\raw_data
if not exist "output\parsed_data" mkdir output\parsed_data

echo.
echo ========================================
echo Setup complete!
echo.
echo To run the application, use: 
echo     run.bat
echo or:
echo     .venv\Scripts\activate.bat && uv run streamlit run main.py
echo ========================================

echo.
pause