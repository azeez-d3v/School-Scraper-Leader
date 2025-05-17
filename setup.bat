@echo off
setlocal EnableDelayedExpansion

REM Change to the directory where the script is located
cd /d "%~dp0"
echo Script directory: %CD%

REM Check for administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script requires administrator privileges.
    echo Please run this script as administrator.
    pause
    exit /b 1
)

echo ========================================
echo School Scraper Leader - Setup Process
echo ========================================
echo.


echo Cleaning up previous installation...
if exist ".venv" (
    echo Removing .venv folder...
    rd /s /q ".venv" 2>nul
    if exist ".venv" echo WARNING: Failed to remove .venv folder.
)
if exist ".python-version" (
    echo Removing .python-version file...
    del /f ".python-version" 2>nul
    if exist ".python-version" echo WARNING: Failed to remove .python-version file.
)
if exist "pyproject.toml" (
    echo Removing pyproject.toml file...
    del /f "pyproject.toml" 2>nul
    if exist "pyproject.toml" echo WARNING: Failed to remove pyproject.toml file.
)
if exist "uv.lock" (
    echo Removing uv.lock file...
    del /f "uv.lock" 2>nul
    if exist "uv.lock" echo WARNING: Failed to remove uv.lock file.
)
if exist "output" (
    echo Removing output folder...
    rd /s /q "output" 2>nul
    if exist "output" echo WARNING: Failed to remove output folder.
)
if exist "__pycache__" (
    echo Removing __pycache__ folder...
    rd /s /q "__pycache__" 2>nul
    if exist "__pycache__" echo WARNING: Failed to remove __pycache__ folder.
)
echo Cleanup complete.
echo.

echo Checking for requirements.txt...
echo Full path: %CD%\requirements.txt
if exist "requirements.txt" (
    echo Found requirements.txt file at: %CD%\requirements.txt
) else (
    echo ERROR: requirements.txt not found in the current directory: %CD%
    echo Contents of directory:
    dir
    echo Please ensure requirements.txt exists before running this script.
    pause
    exit /b 1
)

echo Checking for local UV executable...
where uv
if %errorlevel% neq 0 (
    echo ERROR: UV executable not found in PATH.
    echo Please ensure UV is installed and available in PATH.
    pause
    exit /b 1
)

echo.
echo Initializing project with UV...
uv init
if %errorlevel% neq 0 (
    echo ERROR: Failed to initialize project with UV.
    pause
    exit /b 1
)

echo.
echo Installing packages from requirements.txt...
echo This may take several minutes...
uv add -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages with UV.
    pause
    exit /b 1
)

echo.
echo Creating output directories...
if not exist "output" mkdir "output"
if not exist "output\raw_data" mkdir "output\raw_data"
if not exist "output\parsed_data" mkdir "output\parsed_data"
echo Output directories created.

echo.
echo Creating .env file if it doesn't exist...
if not exist ".env" (
    echo GOOGLE_API_KEY=apikey> .env
    echo Created .env file with default GOOGLE_API_KEY
    echo NOTE: You will need to update the API key with a valid one.
) else (
    echo .env file already exists
)

echo.
echo Creating run.bat file...
(
echo @echo off
echo setlocal
echo.
echo REM Change to the directory where the script is located
echo cd /d "%%~dp0"
echo.
echo if not exist ".venv" (
echo    echo ERROR: Virtual environment not found.
echo    echo Please run setup.bat first.
echo    pause
echo    exit /b 1
echo ^)
echo.
echo echo Starting application...
echo uv run streamlit run main.py
echo.
echo endlocal
) > run.bat

echo.
echo ========================================
echo Setup complete!
echo.
echo To run the application, use: 
echo     run.bat
echo ========================================

pause
exit /b 0