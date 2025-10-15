#!/usr/bin/env python3
"""
Celery Initialization
Handles Celery task initialization when the app starts
"""

import os
import sys
import logging
from typing import Dict, Any

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

logger = logging.getLogger(__name__)


def initialize_celery(celery) -> bool:
    """Initialize Celery tasks and configuration"""
    try:
        logger.info("Initializing Celery tasks...")
        
        if not celery:
            logger.warning("⚠️ Celery instance not available, skipping task initialization")
            return False
        
        # Import all task modules to register them
        try:
            from app.tasks import reminder_tasks
            from app.tasks import enhanced_reminder_tasks
            from app.tasks import class_creation_tasks

            from app.tasks.class_creation_tasks import (
                create_daily_classes_function,
            )
            create_daily_classes = create_daily_classes_function()
            logger.info("✅ All task modules imported successfully")
        except ImportError as e:
            logger.warning(f"⚠️ Could not import some task modules: {e}")
        
        # Test Celery connection
        try:
            # Try to get Celery status
            inspect = celery.control.inspect()
            stats = inspect.stats()
            if stats:
                logger.info("✅ Celery workers are active")
            else:
                logger.warning("⚠️ No active Celery workers found")
        except Exception as e:
            logger.warning(f"⚠️ Could not connect to Celery workers: {e}")
        
        logger.info("✅ Celery tasks initialized")
        return True
        
    except Exception as e:
        logger.error(f"❌ Celery initialization failed: {str(e)}")
        return False


def initialize_app(app, celery):
    initialize_celery(celery)
    return True