#!/usr/bin/env python3
"""
Holiday System Setup Script
Sets up the Indian holidays fetching system
"""

import os
import sys
import subprocess
from datetime import datetime

def install_requirements():
    """Install required packages"""
    requirements = [
        'requests>=2.25.0',
        'schedule>=1.1.0'
    ]
    
    print("Installing required packages...")
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', req])
            print(f"✓ Installed {req}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {req}")
            return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = [
        'logs'
    ]
    
    print("Creating directories...")
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}")
        else:
            print(f"✓ Directory exists: {directory}")

def check_environment():
    """Check environment variables"""
    print("Checking environment variables...")
    
    api_key = os.getenv('CALENDARIFIC_API_ENDPOINT')
    if api_key:
        print("✓ CALENDARIFIC_API_ENDPOINT is set")
        return True
    else:
        print("✗ CALENDARIFIC_API_ENDPOINT not set")
        print("Please set your Calendarific API key:")
        print("export CALENDARIFIC_API_ENDPOINT='your_api_key_here'")
        return False

def test_holiday_fetch():
    """Test the holiday fetching functionality"""
    print("Testing holiday fetch...")
    
    try:
        from fetch_indian_holidays import IndianHolidayFetcher
        
        fetcher = IndianHolidayFetcher()
        current_year = datetime.now().year
        
        print(f"Fetching holidays for {current_year}...")
        success = fetcher.fetch_and_store_holidays(current_year)
        
        if success:
            print(f"✓ Successfully fetched holidays for {current_year}")
            
            # Check stored holidays
            stored = fetcher.get_stored_holidays(current_year)
            print(f"✓ Found {len(stored)} holidays in database")
            
            return True
        else:
            print(f"✗ Failed to fetch holidays for {current_year}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing holiday fetch: {str(e)}")
        return False

def setup_scheduler():
    """Setup the holiday scheduler"""
    print("Setting up holiday scheduler...")
    
    try:
        # Create a simple startup script
        startup_script = """#!/bin/bash
# Holiday Fetcher Startup Script
cd "$(dirname "$0")"
python3 schedule_holiday_fetcher.py --daemon
"""
        
        with open('start_holiday_scheduler.sh', 'w') as f:
            f.write(startup_script)
        
        # Make it executable
        os.chmod('start_holiday_scheduler.sh', 0o755)
        
        print("✓ Created startup script: start_holiday_scheduler.sh")
        print("  To start the scheduler: ./start_holiday_scheduler.sh")
        
        return True
        
    except Exception as e:
        print(f"✗ Error setting up scheduler: {str(e)}")
        return False

def show_usage():
    """Show usage instructions"""
    print("\n" + "="*60)
    print("HOLIDAY SYSTEM SETUP COMPLETE")
    print("="*60)
    print()
    print("Commands:")
    print("---------")
    print("1. Fetch holidays for current year:")
    print("   python3 fetch_indian_holidays.py --test")
    print()
    print("2. Fetch holidays for specific year:")
    print("   python3 fetch_indian_holidays.py --year 2025")
    print()
    print("3. Start the scheduler (runs in background):")
    print("   ./start_holiday_scheduler.sh")
    print()
    print("4. Run scheduler manually (foreground):")
    print("   python3 schedule_holiday_fetcher.py")
    print()
    print("API Endpoints:")
    print("-------------")
    print("- GET /api/holidays/indian/<year>  - Get holidays for year")
    print("- POST /api/holidays/import        - Import selected holidays")
    print("- POST /api/holidays/fetch/<year>  - Fetch holidays from API")
    print()
    print("Web Interface:")
    print("-------------")
    print("Visit the Holidays Management page to:")
    print("- View current holidays")
    print("- Import Indian holidays")
    print("- Enable/disable individual holidays")
    print()

def main():
    """Main setup function"""
    print("Holiday System Setup")
    print("===================")
    print()
    
    # Check environment
    if not check_environment():
        return False
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Create directories
    create_directories()
    
    # Test functionality
    if not test_holiday_fetch():
        print("✗ Holiday fetch test failed")
        return False
    
    # Setup scheduler
    if not setup_scheduler():
        print("✗ Scheduler setup failed")
        return False
    
    # Show usage
    show_usage()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
