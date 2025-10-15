#!/usr/bin/env python3
"""
Standalone Startup Script
Run all initialization tasks independently of the main app
"""

import os
import sys
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/startup.log', mode='a') if os.path.exists('logs') else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main startup function"""
    print("🚀 botle Sports Coaching - Startup Initialization")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Import and run the startup initialization
        from app.startup.initialization import run_startup_scripts
        
        # result = run_startup_scripts()
        
        print("\n" + "=" * 60)
        if result['success']:
            print("✅ ALL STARTUP TASKS COMPLETED SUCCESSFULLY!")
            print(f"Summary: {result.get('summary', 'All tasks completed')}")
        else:
            print("⚠️ STARTUP COMPLETED WITH ISSUES")
            print(f"Summary: {result.get('summary', 'Some tasks failed')}")
            if 'error' in result:
                print(f"Error: {result['error']}")
        
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show detailed results
        if 'results' in result:
            print("\nDetailed Results:")
            for task, status in result['results'].items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {task.replace('_', ' ').title()}")
        
        return 0 if result['success'] else 1
        
    except Exception as e:
        print(f"\n❌ STARTUP FAILED: {str(e)}")
        logger.error(f"Startup script failed: {str(e)}", exc_info=True)
        return 1

def run_specific_task(task_name):
    """Run a specific initialization task"""
    print(f"🎯 Running specific task: {task_name}")
    
    try:
        from app.app import create_app
        from app.startup.initialization import StartupInitializer
        
        app, celery = create_app()
        
        with app.app_context():
            initializer = StartupInitializer(app, celery)
            
            # Map task names to methods
            task_methods = {
                'database': initializer._init_database,
                'collections': initializer._init_collections,
                'celery': initializer._init_celery_tasks,
                'classes': initializer._init_class_creation,
                'holidays': initializer._init_holiday_system,
                'periodic': initializer._init_periodic_tasks
            }
            
            if task_name not in task_methods:
                print(f"❌ Unknown task: {task_name}")
                print(f"Available tasks: {', '.join(task_methods.keys())}")
                return 1
            
            result = task_methods[task_name]()
            
            if result:
                print(f"✅ Task '{task_name}' completed successfully!")
                return 0
            else:
                print(f"❌ Task '{task_name}' failed!")
                return 1
                
    except Exception as e:
        print(f"❌ Task execution failed: {str(e)}")
        logger.error(f"Task '{task_name}' failed: {str(e)}", exc_info=True)
        return 1

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='botle Startup Initialization')
    parser.add_argument('--task', help='Run specific task only', 
                       choices=['database', 'collections', 'celery', 'classes', 'holidays', 'periodic'])
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.task:
        exit_code = run_specific_task(args.task)
    else:
        exit_code = main()
    
    sys.exit(exit_code)
