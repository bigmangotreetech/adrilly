#!/usr/bin/env python3
"""
Holiday Fetcher Scheduler
Sets up automated holiday fetching to run on the last day of each year
"""

import os
import sys
import time
import logging
from datetime import datetime, date
import schedule

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fetch_indian_holidays import IndianHolidayFetcher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/holiday_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_yearly_holiday_fetch():
    """Fetch holidays for the next year"""
    try:
        current_year = datetime.now().year
        next_year = current_year + 1
        
        logger.info(f"Starting yearly holiday fetch for {next_year}")
        
        fetcher = IndianHolidayFetcher()
        success = fetcher.fetch_and_store_holidays(next_year)
        
        if success:
            logger.info(f"Successfully fetched holidays for {next_year}")
            
            # Also refresh current year holidays if it's early in the year
            if datetime.now().month <= 2:
                logger.info(f"Refreshing holidays for current year {current_year}")
                fetcher.fetch_and_store_holidays(current_year)
        else:
            logger.error(f"Failed to fetch holidays for {next_year}")
            
    except Exception as e:
        logger.error(f"Error in yearly holiday fetch: {str(e)}")

def run_daily_check():
    """Check if today is December 31st and run the fetch"""
    today = date.today()
    
    # Run on December 31st
    if today.month == 12 and today.day == 31:
        logger.info("December 31st detected - running yearly holiday fetch")
        run_yearly_holiday_fetch()
    
    # Also run on January 1st as a backup
    elif today.month == 1 and today.day == 1:
        logger.info("January 1st backup check - running yearly holiday fetch")
        run_yearly_holiday_fetch()

def setup_scheduler():
    """Setup the holiday fetch scheduler"""
    
    # Schedule daily check at 11:59 PM
    schedule.every().day.at("23:59").do(run_daily_check)
    
    # Schedule weekly maintenance check on Sundays at 6:00 AM
    schedule.every().sunday.at("06:00").do(lambda: logger.info("Weekly scheduler health check"))
    
    logger.info("Holiday fetch scheduler setup complete")
    logger.info("Scheduled tasks:")
    logger.info("- Daily check at 23:59 (runs fetch on Dec 31st)")
    logger.info("- Weekly health check on Sundays at 06:00")

def run_scheduler():
    """Run the scheduler in a continuous loop"""
    logger.info("Starting holiday fetch scheduler daemon...")
    
    # Run initial check
    logger.info("Running initial holiday availability check")
    try:
        fetcher = IndianHolidayFetcher()
        current_year = datetime.now().year
        
        # Check if we have holidays for current year
        holidays = fetcher.get_stored_holidays(current_year)
        if not holidays:
            logger.info(f"No holidays found for {current_year}, fetching...")
            fetcher.fetch_and_store_holidays(current_year)
            
        # Check if we have holidays for next year (if we're in Q4)
        if datetime.now().month >= 10:
            next_year = current_year + 1
            next_year_holidays = fetcher.get_stored_holidays(next_year)
            if not next_year_holidays:
                logger.info(f"No holidays found for {next_year}, fetching...")
                fetcher.fetch_and_store_holidays(next_year)
                
    except Exception as e:
        logger.error(f"Error in initial holiday check: {str(e)}")
    
    # Main scheduler loop
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Holiday Fetch Scheduler')
    parser.add_argument('--run-once', action='store_true', help='Run holiday fetch once and exit')
    parser.add_argument('--year', type=int, help='Specific year to fetch (with --run-once)')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon service')
    
    args = parser.parse_args()
    
    if args.run_once:
        # Run once and exit
        year = args.year or datetime.now().year
        try:
            fetcher = IndianHolidayFetcher()
            success = fetcher.fetch_and_store_holidays(year)
            if success:
                print(f"Successfully fetched holidays for {year}")
                sys.exit(0)
            else:
                print(f"Failed to fetch holidays for {year}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
    
    elif args.daemon:
        # Run as daemon
        setup_scheduler()
        run_scheduler()
    
    else:
        # Default: setup scheduler and run
        setup_scheduler()
        
        print("Holiday Fetch Scheduler")
        print("======================")
        print("This will monitor for December 31st and fetch holidays for the next year.")
        print("Press Ctrl+C to stop.")
        print()
        
        try:
            run_scheduler()
        except KeyboardInterrupt:
            print("\nScheduler stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    main()
