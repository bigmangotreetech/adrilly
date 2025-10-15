#!/bin/bash
# Linux/Mac shell script to start botle Sports Coaching System

echo "========================================"
echo " botle Sports Coaching System"
echo " Starting all services..."
echo "========================================"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: Virtual environment not found at venv/"
    echo "Please create one with: python -m venv venv"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run startup initialization
echo ""
echo "Running startup initialization..."
python startup.py
if [ $? -ne 0 ]; then
    echo "Warning: Startup initialization had issues"
fi

# Start Redis (if available)
echo ""
echo "Checking for Redis..."
if command -v redis-server &> /dev/null; then
    echo "Starting Redis server..."
    redis-server --daemonize yes
    echo "Redis started in background"
else
    echo "Warning: Redis not found. Please install and start Redis manually."
    echo "Install with: sudo apt-get install redis-server (Ubuntu/Debian)"
    echo "            : brew install redis (macOS)"
fi

# Wait a moment for Redis to start
sleep 3

# Start Celery worker in background
echo ""
echo "Starting Celery worker..."
python celery_worker.py &
CELERY_WORKER_PID=$!
echo "Celery worker started with PID: $CELERY_WORKER_PID"

# Start Celery beat scheduler in background
echo ""
echo "Starting Celery beat scheduler..."
python -m celery -A celery_worker.celery beat --loglevel=info &
CELERY_BEAT_PID=$!
echo "Celery beat started with PID: $CELERY_BEAT_PID"

# Wait a moment for Celery to start
sleep 3

# Function to cleanup processes on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    if [ ! -z "$CELERY_WORKER_PID" ]; then
        kill $CELERY_WORKER_PID 2>/dev/null
        echo "Celery worker stopped"
    fi
    if [ ! -z "$CELERY_BEAT_PID" ]; then
        kill $CELERY_BEAT_PID 2>/dev/null
        echo "Celery beat stopped"
    fi
    echo "Cleanup complete"
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start Flask application
echo ""
echo "Starting Flask application..."
echo ""
echo "========================================"
echo " All services started!"
echo " Access the application at:"
echo " http://localhost:5000"
echo ""
echo " Press Ctrl+C to stop all services"
echo "========================================"
echo ""

python run.py

# If we reach here, Flask has stopped, so cleanup
cleanup
