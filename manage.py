#!/usr/bin/env python3
"""
botle Management Script
Comprehensive management tool for all application operations
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AdrillManager:
    """Main management class for botle operations"""
    
    def __init__(self):
        self.app = None
        self.celery = None
        
    def setup_app(self):
        """Set up Flask app context"""
        if not self.app:
            from app.app import create_app
            self.app, self.celery = create_app()
        return self.app, self.celery
    
    def init_database(self):
        """Initialize database and collections"""
        print("🗄️ Initializing database...")
        
        try:
            from init_database import init_database
            success = init_database()
            
            if success:
                print("✅ Database initialization completed successfully!")
                return 0
            else:
                print("❌ Database initialization failed!")
                return 1
                
        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")
            return 1
    
    def seed_data(self):
        """Seed database with sample data"""
        print("🌱 Seeding database with sample data...")
        
        try:
            from seed_data import main as seed_main
            success = seed_main()
            
            if success:
                print("✅ Data seeding completed successfully!")
                return 0
            else:
                print("❌ Data seeding failed!")
                return 1
                
        except Exception as e:
            print(f"❌ Data seeding error: {str(e)}")
            return 1
    
    def create_classes(self, days_ahead=7, org_id=None):
        """Create classes for upcoming days"""
        print(f"📅 Creating classes for {days_ahead} days ahead...")
        
        try:
            from daily_class_creator import DailyClassCreator
            from datetime import date
            
            creator = DailyClassCreator()
            start_date = date.today() + timedelta(days=1)  # Start from tomorrow
            
            created_classes = creator.create_classes_for_range(
                start_date=start_date,
                days_ahead=days_ahead,
                org_id=org_id
            )
            
            creator.close()
            
            print(f"✅ Created {len(created_classes)} classes successfully!")
            return 0
            
        except Exception as e:
            print(f"❌ Class creation error: {str(e)}")
            return 1
    
    def import_holidays(self, year=None):
        """Import holidays for specified year"""
        if year is None:
            year = datetime.now().year
            
        print(f"🎉 Importing holidays for year {year}...")
        
        try:
            from fetch_indian_holidays import IndianHolidayFetcher
            
            fetcher = IndianHolidayFetcher()
            success = fetcher.fetch_and_store_holidays(year)
            
            if success:
                print(f"✅ Holidays for {year} imported successfully!")
                return 0
            else:
                print(f"❌ Failed to import holidays for {year}!")
                return 1
                
        except Exception as e:
            print(f"❌ Holiday import error: {str(e)}")
            return 1
    
    def start_celery_worker(self):
        """Start Celery worker"""
        print("🔄 Starting Celery worker...")
        
        try:
            app, celery = self.setup_app()
            
            # Import all tasks
            from app.tasks import *
            
            print("✅ All tasks imported. Starting worker...")
            celery.start(['worker', '--loglevel=info'])
            
        except Exception as e:
            print(f"❌ Celery worker error: {str(e)}")
            return 1
    
    def start_celery_beat(self):
        """Start Celery beat scheduler"""
        print("⏰ Starting Celery beat scheduler...")
        
        try:
            app, celery = self.setup_app()
            
            # Import all tasks
            from app.tasks import *
            
            print("✅ All tasks imported. Starting beat scheduler...")
            celery.start(['beat', '--loglevel=info'])
            
        except Exception as e:
            print(f"❌ Celery beat error: {str(e)}")
            return 1
    
    def run_startup(self):
        """Run all startup initialization"""
        print("🚀 Running complete startup initialization...")
        
        try:
            from startup import main as startup_main
            return startup_main()
            
        except Exception as e:
            print(f"❌ Startup error: {str(e)}")
            return 1
    
    def test_system(self):
        """Run system tests"""
        print("🧪 Running system tests...")
        
        tests_passed = 0
        tests_failed = 0
        
        # Test database connection
        try:
            app, _ = self.setup_app()
            with app.app_context():
                from app.extensions import verify_database_connection
                success, message = verify_database_connection()
                
                if success:
                    print("✅ Database connection test passed")
                    tests_passed += 1
                else:
                    print(f"❌ Database connection test failed: {message}")
                    tests_failed += 1
        except Exception as e:
            print(f"❌ Database connection test error: {str(e)}")
            tests_failed += 1
        
        # Test Celery connection
        try:
            app, celery = self.setup_app()
            
            # Try to get Celery status
            inspect = celery.control.inspect()
            stats = inspect.stats()
            
            if stats:
                print("✅ Celery connection test passed")
                tests_passed += 1
            else:
                print("⚠️ Celery connection test: No active workers found")
                tests_failed += 1
                
        except Exception as e:
            print(f"⚠️ Celery connection test warning: {str(e)}")
            # Don't count this as a failure since Celery might not be running
        
        # Test authentication
        try:
            from test_auth import main as test_auth_main
            if test_auth_main():
                print("✅ Authentication test passed")
                tests_passed += 1
            else:
                print("❌ Authentication test failed")
                tests_failed += 1
        except Exception as e:
            print(f"⚠️ Authentication test skipped: {str(e)}")
        
        print(f"\n📊 Test Results: {tests_passed} passed, {tests_failed} failed")
        return 0 if tests_failed == 0 else 1
    
    def show_status(self):
        """Show system status"""
        print("📊 System Status")
        print("=" * 40)
        
        try:
            app, celery = self.setup_app()
            
            with app.app_context():
                from app.extensions import mongo
                
                # Database status
                try:
                    # Count some basic collections
                    user_count = mongo.db.users.count_documents({})
                    org_count = mongo.db.organizations.count_documents({})
                    class_count = mongo.db.classes.count_documents({})
                    
                    print(f"📊 Database:")
                    print(f"  - Users: {user_count}")
                    print(f"  - Organizations: {org_count}")
                    print(f"  - Classes: {class_count}")
                    
                except Exception as e:
                    print(f"❌ Database status error: {str(e)}")
                
                # Celery status
                try:
                    inspect = celery.control.inspect()
                    stats = inspect.stats()
                    
                    if stats:
                        worker_count = len(stats)
                        print(f"🔄 Celery: {worker_count} workers active")
                    else:
                        print("⚠️ Celery: No active workers")
                        
                except Exception as e:
                    print(f"⚠️ Celery status: {str(e)}")
                
                print("✅ System status check completed")
                return 0
                
        except Exception as e:
            print(f"❌ Status check error: {str(e)}")
            return 1

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='botle Management Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Database commands
    db_parser = subparsers.add_parser('init-db', help='Initialize database')
    seed_parser = subparsers.add_parser('seed', help='Seed database with sample data')
    
    # Class management
    classes_parser = subparsers.add_parser('create-classes', help='Create classes')
    classes_parser.add_argument('--days', type=int, default=7, help='Days ahead to create classes')
    classes_parser.add_argument('--org-id', help='Organization ID to create classes for')
    
    # Holiday management
    holidays_parser = subparsers.add_parser('import-holidays', help='Import holidays')
    holidays_parser.add_argument('--year', type=int, help='Year to import holidays for')
    
    # Celery commands
    celery_worker_parser = subparsers.add_parser('celery-worker', help='Start Celery worker')
    celery_beat_parser = subparsers.add_parser('celery-beat', help='Start Celery beat scheduler')
    
    # System commands
    startup_parser = subparsers.add_parser('startup', help='Run startup initialization')
    test_parser = subparsers.add_parser('test', help='Run system tests')
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = AdrillManager()
    
    # Route commands
    if args.command == 'init-db':
        return manager.init_database()
    elif args.command == 'seed':
        return manager.seed_data()
    elif args.command == 'create-classes':
        return manager.create_classes(args.days, args.org_id)
    elif args.command == 'import-holidays':
        return manager.import_holidays(args.year)
    elif args.command == 'celery-worker':
        return manager.start_celery_worker()
    elif args.command == 'celery-beat':
        return manager.start_celery_beat()
    elif args.command == 'startup':
        return manager.run_startup()
    elif args.command == 'test':
        return manager.test_system()
    elif args.command == 'status':
        return manager.show_status()
    else:
        print(f"❌ Unknown command: {args.command}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
