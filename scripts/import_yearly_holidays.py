#!/usr/bin/env python3
"""
Import Yearly Holidays
Imports holidays for a specific year.
"""

import os
import sys
import argparse
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    parser = argparse.ArgumentParser(description='Import yearly holidays')
    parser.add_argument('--year', type=int, default=datetime.now().year, help='Year to import (default: current year)')
    parser.add_argument('--country-code', type=str, default='IN', help='Country code (default: IN)')
    args = parser.parse_args()
    
    try:
        from app.app import create_app
        from app.extensions import mongo
        
        app, _ = create_app()
        
        with app.app_context():
            try:
                from fetch_indian_holidays import IndianHolidayFetcher
            except ImportError:
                print("❌ Error: IndianHolidayFetcher not available")
                return 1
            
            fetcher = IndianHolidayFetcher()
            success = fetcher.fetch_and_store_holidays(args.year)
            
            if success:
                holiday_count = mongo.db.holidays.count_documents({
                    'date_observed': {
                        '$gte': datetime(args.year, 1, 1).date(),
                        '$lt': datetime(args.year + 1, 1, 1).date()
                    },
                    'is_master': True
                })
                print(f"✅ Imported {holiday_count} holidays for year {args.year}")
            else:
                print(f"❌ Failed to import holidays for year {args.year}")
                return 1
            
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
