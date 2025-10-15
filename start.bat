@echo off
REM Windows batch script to start botle Sports Coaching System

echo ========================================
echo  botle Sports Coaching System
echo  Starting all services...
echo ========================================

REM Check if virtual environment exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found at venv\
    echo Please create one with: python -m venv venv
)

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Run startup initialization
echo.
echo Running startup initialization...
python startup.py
if errorlevel 1 (
    echo Warning: Startup initialization had issues
)

REM Start Redis (if available)
echo.
echo Checking for Redis...
where redis-server >nul 2>nul
if %errorlevel% == 0 (
    echo Starting Redis server...
    start "Redis Server" redis-server
) else (
    echo Warning: Redis not found. Please install and start Redis manually.
    echo Download from: https://github.com/microsoftarchive/redis/releases
)

REM Wait a moment for Redis to start
timeout /t 3 /nobreak >nul

REM Start Celery worker
echo.
echo Starting Celery worker...
start "Celery Worker" python celery_worker.py

REM Start Celery beat scheduler
echo.
echo Starting Celery beat scheduler...
start "Celery Beat" python -m celery -A celery_worker.celery beat --loglevel=info

REM Wait a moment for Celery to start
timeout /t 3 /nobreak >nul

REM Start Flask application
echo.
echo Starting Flask application...
echo.
echo ========================================
echo  All services started!
echo  Access the application at:
echo  http://localhost:5000
echo ========================================
echo.
python run.py

pause
