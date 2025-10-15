#!/usr/bin/env python3
"""
Celery worker entry point for background tasks
"""

from app.app import create_app
import logging
import sys
import signal
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create app and celery instances
app, celery = create_app()

# Import all task modules to ensure they are registered
try:
    from app.tasks import *
    logger.info("✅ All Celery tasks imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Some task modules could not be imported: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Celery worker...")
    logger.info("💡 To stop the worker, use Ctrl+C or send SIGTERM")
    
    try:
        # Use the proper Celery worker command with better signal handling
        celery.worker_main(['worker', '--loglevel=info', '--without-gossip', '--without-mingle', '--without-heartbeat'])
    except KeyboardInterrupt:
        logger.info("🛑 Worker stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Worker failed to start: {e}")
        sys.exit(1) 