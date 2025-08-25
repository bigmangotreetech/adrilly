#!/usr/bin/env python3
"""
Indian Holidays Fetcher Script
Fetches holidays from Calendarific API and stores them in the database
"""

import os
import sys
import requests
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
import schedule
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.extensions import mongo
from app.models.holiday import Holiday
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/holiday_fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IndianHolidayFetcher:
    """Fetches and manages Indian holidays from Calendarific API"""
    
    def __init__(self):
        self.api_key = os.getenv('CALENDARIFIC_API_ENDPOINT')
        self.base_url = "https://calendarific.com/api/v2/holidays"
        self.country_code = "IN"  # India
        
        if not self.api_key:
            raise ValueError("CALENDARIFIC_API_ENDPOINT environment variable not set")
    
    def fetch_holidays_for_year(self, year: int) -> List[Dict]:
        """
        Fetch holidays for a specific year from Calendarific API
        
        Args:
            year: Year to fetch holidays for
            
        Returns:
            List of holiday dictionaries
        """
        try:
            params = {
                'api_key': self.api_key,
                'country': self.country_code,
                'year': year,
                'type': 'national,local,religious,observance'
            }
            
            logger.info(f"Fetching holidays for year {year}")
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('meta', {}).get('code') != 200:
                logger.error(f"API Error: {data.get('meta', {}).get('error_detail', 'Unknown error')}")
                return []
            
            holidays = data.get('response', {}).get('holidays', [])
            logger.info(f"Successfully fetched {len(holidays)} holidays for {year}")
            
            return holidays
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching holidays for {year}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching holidays for {year}: {str(e)}")
            return []
    
    def process_holiday_data(self, holiday_data: Dict) -> Optional[Dict]:
        """
        Process and normalize holiday data from API
        
        Args:
            holiday_data: Raw holiday data from API
            
        Returns:
            Processed holiday dictionary or None if invalid
        """
        try:
            # Extract basic information
            name = holiday_data.get('name', '').strip()
            description = holiday_data.get('description', '').strip()
            
            # Parse date
            date_info = holiday_data.get('date', {})
            iso_date = date_info.get('iso')
            
            if not iso_date or not name:
                return None
            
            # Parse the date
            holiday_date = datetime.strptime(iso_date, '%Y-%m-%d').date()
            
            # Get holiday types and locations
            holiday_types = holiday_data.get('type', [])
            if isinstance(holiday_types, str):
                holiday_types = [holiday_types]
            
            locations = holiday_data.get('locations', 'All India')
            if isinstance(locations, str):
                locations = locations
            elif isinstance(locations, list):
                locations = ', '.join(locations) if locations else 'All India'
            else:
                locations = 'All India'
            
            # Determine if this affects scheduling (major holidays only)
            affects_scheduling = any(htype in ['national', 'public'] for htype in holiday_types)
            
            # Create processed holiday data
            processed_holiday = {
                'name': name,
                'description': description or name,
                'date_observed': holiday_date,
                'locations': locations,
                'holiday_types': holiday_types,
                'affects_scheduling': affects_scheduling,
                'source': 'calendarific_api',
                'api_data': holiday_data,  # Store original data for reference
                'imported_at': datetime.utcnow(),
                'is_enabled': True,  # Default to enabled
                'is_imported': True
            }
            
            return processed_holiday
            
        except Exception as e:
            logger.error(f"Error processing holiday data: {str(e)}")
            return None
    
    def save_holidays_to_db(self, holidays: List[Dict], year: int) -> int:
        """
        Save processed holidays to database
        
        Args:
            holidays: List of processed holiday dictionaries
            year: Year these holidays belong to
            
        Returns:
            Number of holidays saved
        """
        saved_count = 0
        
        try:
            # Remove existing imported holidays for this year
            mongo.db.holidays.delete_many({
                'source': 'calendarific_api',
                'date_observed': {
                    '$gte': date(year, 1, 1),
                    '$lte': date(year, 12, 31)
                }
            })
            
            for holiday_data in holidays:
                processed = self.process_holiday_data(holiday_data)
                if processed:
                    try:
                        # Check if holiday already exists (by name and date)
                        existing = mongo.db.holidays.find_one({
                            'name': processed['name'],
                            'date_observed': processed['date_observed']
                        })
                        
                        if existing:
                            # Update existing holiday
                            mongo.db.holidays.update_one(
                                {'_id': existing['_id']},
                                {'$set': processed}
                            )
                            logger.debug(f"Updated holiday: {processed['name']}")
                        else:
                            # Insert new holiday
                            mongo.db.holidays.insert_one(processed)
                            logger.debug(f"Inserted holiday: {processed['name']}")
                        
                        saved_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error saving holiday {processed['name']}: {str(e)}")
                        continue
            
            logger.info(f"Successfully saved {saved_count} holidays for year {year}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving holidays to database: {str(e)}")
            return saved_count
    
    def fetch_and_store_holidays(self, year: Optional[int] = None) -> bool:
        """
        Main function to fetch and store holidays for a year
        
        Args:
            year: Year to fetch holidays for (defaults to current year)
            
        Returns:
            True if successful, False otherwise
        """
        if year is None:
            year = datetime.now().year
        
        try:
            logger.info(f"Starting holiday fetch process for year {year}")
            
            # Fetch holidays from API
            holidays_data = self.fetch_holidays_for_year(year)
            
            if not holidays_data:
                logger.warning(f"No holidays fetched for year {year}")
                return False
            
            # Save to database
            saved_count = self.save_holidays_to_db(holidays_data, year)
            
            if saved_count > 0:
                logger.info(f"Holiday fetch completed successfully. Saved {saved_count} holidays for {year}")
                return True
            else:
                logger.warning(f"No holidays were saved for year {year}")
                return False
                
        except Exception as e:
            logger.error(f"Holiday fetch process failed for year {year}: {str(e)}")
            return False
    
    def get_stored_holidays(self, year: Optional[int] = None, enabled_only: bool = False) -> List[Dict]:
        """
        Get stored holidays from database
        
        Args:
            year: Year to get holidays for (defaults to current year)
            enabled_only: If True, only return enabled holidays
            
        Returns:
            List of holiday dictionaries
        """
        if year is None:
            year = datetime.now().year
        
        try:
            query = {
                'date_observed': {
                    '$gte': date(year, 1, 1),
                    '$lte': date(year, 12, 31)
                }
            }
            
            if enabled_only:
                query['is_enabled'] = True
            
            holidays = list(mongo.db.holidays.find(query).sort('date_observed', 1))
            return holidays
            
        except Exception as e:
            logger.error(f"Error retrieving holidays from database: {str(e)}")
            return []


def setup_yearly_schedule():
    """Setup scheduled job to run on last day of year"""
    
    def run_yearly_fetch():
        """Run the yearly holiday fetch"""
        fetcher = IndianHolidayFetcher()
        current_year = datetime.now().year
        next_year = current_year + 1
        
        # Fetch holidays for next year
        logger.info(f"Running scheduled holiday fetch for {next_year}")
        success = fetcher.fetch_and_store_holidays(next_year)
        
        if success:
            logger.info(f"Scheduled holiday fetch completed successfully for {next_year}")
        else:
            logger.error(f"Scheduled holiday fetch failed for {next_year}")
    
    # Schedule to run on December 31st at 23:59
    schedule.every().year.do(run_yearly_fetch)
    
    # For testing, you can also schedule to run daily at a specific time
    # schedule.every().day.at("23:59").do(run_yearly_fetch)
    
    logger.info("Yearly holiday fetch scheduler setup complete")


def run_scheduler():
    """Run the scheduler in a loop"""
    logger.info("Starting holiday fetch scheduler...")
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Indian Holiday Fetcher')
    parser.add_argument('--year', type=int, help='Year to fetch holidays for')
    parser.add_argument('--schedule', action='store_true', help='Run scheduler')
    parser.add_argument('--test', action='store_true', help='Run test fetch for current year')
    
    args = parser.parse_args()
    
    try:
        fetcher = IndianHolidayFetcher()
        
        if args.schedule:
            setup_yearly_schedule()
            run_scheduler()
        elif args.test:
            # Test run for current year
            success = fetcher.fetch_and_store_holidays()
            if success:
                print("Test run completed successfully")
            else:
                print("Test run failed")
                sys.exit(1)
        else:
            # Fetch for specific year or current year
            year = args.year or datetime.now().year
            success = fetcher.fetch_and_store_holidays(year)
            
            if success:
                print(f"Successfully fetched holidays for {year}")
            else:
                print(f"Failed to fetch holidays for {year}")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
