@echo off
echo ========================================
echo School Scraper Leader - Setup Process
echo ========================================
echo.

REM Initialize USE_PIP variable
set USE_PIP=0

echo Checking if UV package manager is installed...
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo UV is already installed.
) else (
    echo UV is not installed. Installing UV package manager...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

echo.
echo Checking if virtual environment exists...
if exist ".venv" (
    echo Virtual environment already exists, skipping creation.
) else (
    echo Creating virtual environment...
    if "%USE_PIP%"=="1" (
        echo Using pip to create venv...
        python -m venv .venv
    ) else (
        echo Using UV to create Python venv...
        where python3.13 >nul 2>nul
        if %errorlevel% equ 0 (
            echo Creating virtual environment with Python 3.13...
            uv venv --python 3.13
        ) else (
            echo No specific Python version found, letting UV create environment with bundled Python...
            uv venv
        )
        
        if %errorlevel% neq 0 (
            echo WARNING: Failed to create virtual environment with UV.
            echo Checking if Python is installed for fallback...
            where python >nul 2>nul
            if %errorlevel% neq 0 (
                echo ERROR: Cannot create virtual environment.
                echo Neither UV venv creation worked nor is Python available.
                echo Please install either UV properly or Python and run this script again.
                goto error
            ) else (
                echo Python is available, falling back to pip for venv creation...
                set USE_PIP=1
                python -m pip install virtualenv >nul 2>nul
                python -m venv .venv
            )
        )
    )
    
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        echo Please ensure you have a working Python or UV installation.
        goto error
    )
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
if not "%VIRTUAL_ENV%"==".venv" (
    if not "%VIRTUAL_ENV%"=="%CD%\.venv" (
        echo WARNING: Virtual environment may not be activated correctly.
        echo Proceeding anyway, but this might cause issues.
    )
)

echo.
echo Checking if pyproject.toml exists...
if exist "pyproject.toml" (
    echo pyproject.toml already exists.
) else (
    echo WARNING: pyproject.toml not found, creating one...
    if "%USE_PIP%"=="0" (
        echo Initializing project with UV...
        uv init
    ) else (
        echo Creating minimal pyproject.toml...
        (
            echo [project]
            echo name = "school-scraper-leader"
            echo version = "0.1.0"
            echo description = "School Scraper Leader Tool"
            echo readme = "README.md"
            echo requires-python = "^3.8"
            echo dependencies = [
            echo ]
        ) > pyproject.toml
    )
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

if "%USE_PIP%"=="1" (
    echo Using pip for package installation...
    python -m pip install -r requirements.txt
    
    REM Check for protobuf version issues
    echo Checking for protobuf conflicts...
    python -m pip install protobuf==3.20.3 --no-deps
) else (
    echo Using UV for package installation...
    uv pip install -r requirements.txt
    
    REM Check if uv.lock exists after installation
    if not exist "uv.lock" (
        echo WARNING: uv.lock file not created. Creating a fallback lock file...
        uv pip freeze > uv.lock
    )
)

if %errorlevel% neq 0 (
    echo WARNING: Some dependencies might not have installed correctly.
    echo Attempting to fix common issues...
    
    REM Install specific versions of problematic packages
    if "%USE_PIP%"=="1" (
        python -m pip install protobuf==6.30.2 --no-deps
        python -m pip install charset-normalizer==3.4.2 --no-deps
    ) else (
        uv pip install protobuf==6.30.2 --no-deps
        uv pip install charset-normalizer==3.4.2 --no-deps
    )
    
    echo Performed fixes for common dependency issues.
)

echo.
echo Verifying key dependencies...
python -c "import streamlit; import pandas; import langchain" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: Some critical dependencies are missing.
    echo Attempting to install them individually...
    
    if "%USE_PIP%"=="1" (
        python -m pip install streamlit pandas langchain langchain-community
    ) else (
        uv pip install streamlit pandas langchain langchain-community
    )
)

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
echo Updating run.bat with dependency checks...
(
echo @echo off
echo echo Checking environment setup...
echo if not exist ".venv" ^(
echo     echo ERROR: Virtual environment not found.
echo     echo Please run setup.bat first.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo call .venv\Scripts\activate.bat
echo.
echo echo Verifying critical dependencies...
echo python -c "import streamlit" 2^>nul
echo if %%errorlevel%% neq 0 ^(
echo     echo ERROR: Streamlit not found. Running setup to fix...
echo     call setup.bat
echo     if %%errorlevel%% neq 0 ^(
echo         echo Setup failed. Please run setup.bat manually and check for errors.
echo         pause
echo         exit /b 1
echo     ^)
echo ^)
echo.
echo echo Starting application...
echo uv run streamlit run main.py
echo if %%errorlevel%% neq 0 ^(
echo     echo Fallback to direct streamlit execution...
echo     streamlit run main.py
echo ^)
) > run.bat

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
