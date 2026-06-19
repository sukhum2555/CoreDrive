@echo off
title NAS Drive Server
cd /d "%~dp0"

:: Activate virtual environment
if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found.
    echo Please create one first:
    echo   python -m venv env
    echo   env\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

:: Check Django installed
python -c "import django" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt
)

:: Run setup if first time
if not exist "db.sqlite3" (
    echo [SETUP] First run detected. Running setup...
    echo.
    python setup.py
    if errorlevel 1 (
        echo [ERROR] Setup failed.
        pause
        exit /b 1
    )
)

echo.
echo ======================================
echo   NAS Drive Server
echo   URL: http://127.0.0.1:8000
echo   Press Ctrl+C to stop
echo ======================================
echo.

set PYTHONIOENCODING=utf-8
set DJANGO_SETTINGS_MODULE=NAS.settings
python manage.py runserver 0.0.0.0:8000

pause
