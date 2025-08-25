#!/usr/bin/env python3
"""
Class Creation Task Scheduler for Adrilly

This script sets up automated class creation using Celery for background processing.
It can be run as a one-time task or scheduled using cron/Windows Task Scheduler.

Usage:
    # Run immediately
    python schedule_class_creation.py --now
    
    # Schedule for specific time (requires cron or task scheduler)
    python schedule_class_creation.py --schedule "0 6 * * *"  # Daily at 6 AM
    
    # Add to Celery beat schedule
    python schedule_class_creation.py --add-to-beat
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from daily_class_creator import DailyClassCreator


def create_celery_task():
    """Create a Celery task for class creation"""
    
    # Create a new task file
    task_content = '''
from celery import Celery
from datetime import datetime, timedelta
import os
import sys

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from daily_class_creator import DailyClassCreator
from app.extensions import make_celery

# Initialize Celery
celery = Celery('class_creator')

@celery.task
def create_daily_classes(days_ahead=7, org_id=None):
    """Celery task to create daily classes"""
    try:
        creator = DailyClassCreator()
        
        # Start from tomorrow
        start_date = (datetime.utcnow() + timedelta(days=1)).date()
        
        print(f"🚀 Starting automated class creation")
        print(f"📅 Creating classes for {days_ahead} days starting from {start_date}")
        
        # Create classes
        created_classes = creator.create_classes_for_range(
            start_date=start_date,
            days_ahead=days_ahead,
            org_id=org_id
        )
        
        # Cleanup old classes (older than 30 days)
        cleaned_count = creator.cleanup_old_classes(30)
        
        creator.close()
        
        result = {
            'success': True,
            'created_classes': len(created_classes),
            'cleaned_classes': cleaned_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        print(f"✅ Task completed: {result}")
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
        print(f"❌ Task failed: {error_result}")
        return error_result

@celery.task
def create_classes_for_organization(org_id, days_ahead=7):
    """Create classes for a specific organization"""
    return create_daily_classes(days_ahead=days_ahead, org_id=org_id)

# Periodic task setup
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'create-daily-classes': {
        'task': 'schedule_class_creation.create_daily_classes',
        'schedule': crontab(hour=6, minute=0),  # Every day at 6:00 AM
        'args': (7,)  # Create for 7 days ahead
    },
}

celery.conf.timezone = 'UTC'
'''
    
    with open('app/tasks/class_creation_tasks.py', 'w') as f:
        f.write(task_content)
    
    print("✅ Created Celery task file: app/tasks/class_creation_tasks.py")


def create_cron_script():
    """Create a script suitable for cron scheduling"""
    
    script_content = f'''#!/bin/bash
# Cron script for Adrilly class creation
# Add this to crontab: 0 6 * * * /path/to/adrilly-web/create_classes_cron.sh

cd "{os.path.dirname(os.path.abspath(__file__))}"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run the class creator
python daily_class_creator.py --days-ahead 7 --cleanup-days 30

# Log the execution
echo "$(date): Class creation completed" >> logs/class_creation.log
'''
    
    with open('create_classes_cron.sh', 'w') as f:
        f.write(script_content)
    
    # Make it executable
    os.chmod('create_classes_cron.sh', 0o755)
    
    print("✅ Created cron script: create_classes_cron.sh")
    print("📝 To schedule with cron, run: crontab -e")
    print("📝 Then add: 0 6 * * * /path/to/adrilly-web/create_classes_cron.sh")


def create_windows_bat():
    """Create a Windows batch file for Task Scheduler"""
    
    bat_content = f'''@echo off
REM Windows batch script for Adrilly class creation
REM Schedule this with Windows Task Scheduler to run daily at 6 AM

cd /d "{os.path.dirname(os.path.abspath(__file__))}"

REM Activate virtual environment if it exists
if exist venv\\Scripts\\activate.bat (
    call venv\\Scripts\\activate.bat
)

REM Run the class creator
python daily_class_creator.py --days-ahead 7 --cleanup-days 30

REM Log the execution
echo %date% %time%: Class creation completed >> logs\\class_creation.log
'''
    
    with open('create_classes_task.bat', 'w') as f:
        f.write(bat_content)
    
    print("✅ Created Windows batch script: create_classes_task.bat")
    print("📝 Schedule this with Windows Task Scheduler to run daily")


def run_immediate():
    """Run class creation immediately"""
    try:
        creator = DailyClassCreator()
        
        # Create classes for the next 7 days
        start_date = (datetime.utcnow() + timedelta(days=1)).date()
        created_classes = creator.create_classes_for_range(start_date, days_ahead=7)
        
        # Cleanup old classes
        cleaned_count = creator.cleanup_old_classes(30)
        
        creator.close()
        
        print(f"✅ Immediate execution completed")
        print(f"📈 Created {len(created_classes)} classes")
        print(f"🧹 Cleaned up {cleaned_count} old classes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during immediate execution: {str(e)}")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Schedule class creation for Adrilly')
    parser.add_argument('--now', action='store_true', help='Run class creation immediately')
    parser.add_argument('--add-to-beat', action='store_true', help='Add task to Celery beat schedule')
    parser.add_argument('--create-cron', action='store_true', help='Create cron script')
    parser.add_argument('--create-windows', action='store_true', help='Create Windows batch script')
    parser.add_argument('--setup-all', action='store_true', help='Set up all scheduling methods')
    
    args = parser.parse_args()
    
    if not any([args.now, args.add_to_beat, args.create_cron, args.create_windows, args.setup_all]):
        parser.print_help()
        return 1
    
    print("🏃‍♂️ Adrilly Class Creation Scheduler")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        if args.now:
            print("\n🔄 Running immediate class creation...")
            success = run_immediate()
            if not success:
                return 1
        
        if args.add_to_beat or args.setup_all:
            print("\n📅 Setting up Celery beat schedule...")
            create_celery_task()
        
        if args.create_cron or args.setup_all:
            print("\n🐧 Creating cron script...")
            create_cron_script()
        
        if args.create_windows or args.setup_all:
            print("\n🪟 Creating Windows batch script...")
            create_windows_bat()
        
        if args.setup_all:
            print("\n📋 Setup Summary:")
            print("   ✅ Celery task created")
            print("   ✅ Cron script created")
            print("   ✅ Windows batch script created")
            print("\n🔧 Next Steps:")
            print("   1. Choose your preferred scheduling method:")
            print("      - Celery Beat: Start celery beat worker")
            print("      - Cron (Linux/Mac): Add create_classes_cron.sh to crontab")
            print("      - Windows: Schedule create_classes_task.bat in Task Scheduler")
            print("   2. Ensure your environment variables are properly set")
            print("   3. Test the scripts before scheduling")
        
        print(f"\n✅ Scheduler setup complete!")
        print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
