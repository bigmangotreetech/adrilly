"""
Celery Tasks Module
Imports and registers all Celery tasks for the application
"""

# Import all task modules to ensure they are registered
try:
    from . import reminder_tasks
    from . import enhanced_reminder_tasks
    
    # Import additional task modules
    try:
        from . import class_creation_tasks
    except ImportError:
        pass  # Class creation tasks may not be available
    
    try:
        from . import holiday_tasks
    except ImportError:
        pass  # Holiday tasks may not be available
    
    print("✅ All Celery task modules imported successfully")
    
except ImportError as e:
    print(f"⚠️ Some Celery task modules could not be imported: {e}")

# Export commonly used tasks
__all__ = [
    'reminder_tasks',
    'enhanced_reminder_tasks',
    'class_creation_tasks',
]
