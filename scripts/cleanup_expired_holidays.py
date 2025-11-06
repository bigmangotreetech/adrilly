#!/usr/bin/env python3
"""
Cleanup Expired Holidays
Cleans up old holidays that are no longer relevant (older than 2 years).
"""

import os
import sys
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        
        app, _ = create_app()
        
        with app.app_context():
            cutoff_date = datetime.now() - timedelta(days=730)  # 2 years
            cutoff_date = cutoff_date.date()
            
            master_result = mongo.db.holidays.delete_many({
                'is_master': True,
                'date_observed': {'$lt': cutoff_date}
            })
            
            org_result = mongo.db.org_holidays.delete_many({
                'date_observed': {'$lt': cutoff_date}
            })
            
            print(f"✅ Cleaned up {master_result.deleted_count} master holidays")
            print(f"   Cleaned up {org_result.deleted_count} organization holidays")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

