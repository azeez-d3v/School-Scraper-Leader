@echo off
echo ========================================
echo School Scraper Leader - Setup Process
echo ========================================
echo.

echo Checking for local UV executable...
if exist "uv.exe" (
    echo Found local UV executable in root directory.
    
    REM Add current directory to PATH for this session
    set "PATH=%CD%;%PATH%"
    echo Successfully added current directory with UV to PATH.
    echo UV executable path:
    where uv
) else (
    echo ERROR: Local UV executable not found in the root directory.
    echo Please ensure uv.exe exists in the project root folder.
    goto error
)

echo.
echo Checking if virtual environment exists...
if exist ".venv" (
    echo Virtual environment already exists, skipping creation.
) else (
    echo Creating virtual environment with UV...
    uv venv
    
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment with UV.
        echo Please ensure you have a working UV executable.
        goto error
    )
    echo Virtual environment successfully created with UV.
)

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    goto error
)

echo.
echo Verifying activated environment...
echo Current Python path:
where python

echo.
echo Checking if pyproject.toml exists...
if exist "pyproject.toml" (
    echo pyproject.toml already exists.
) else (
    echo Creating pyproject.toml with UV...
    uv init
)

echo.
echo Checking if requirements.txt exists...
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found. Cannot install dependencies.
    goto error
)

echo.
echo Installing required packages from requirements.txt...
echo This may take several minutes...
uv pip install -r requirements.txt

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
    echo NOTE: You will need to update the API key with a valid one.
) else (
    echo .env file already exists
)

echo.
echo Creating run.bat file...
(
echo @echo off
echo echo Setting up environment...
echo if not exist ".venv" ^(
echo     echo ERROR: Virtual environment not found.
echo     echo Please run setup.bat first.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo call .venv\Scripts\activate.bat
echo.
echo echo Adding local UV to PATH...
echo set "PATH=%%CD%%;%%PATH%%"
echo.
echo echo Starting application...
echo uv run streamlit run main.py
) > run.bat

echo.
echo ========================================
echo Setup complete!
echo.
echo To run the application, use: 
echo     run.bat
echo ========================================

echo.
goto end

:error
echo.
echo ========================================
echo Setup failed with errors.
echo Please check the messages above and fix any issues.
echo Then run setup.bat again.
echo ========================================
exit /b 1

:end
pause