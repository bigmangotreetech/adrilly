#!/usr/bin/env python3
"""
Sync Organization Holidays
Syncs master holidays with organization holidays.
"""

import os
import sys
import argparse
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    parser = argparse.ArgumentParser(description='Sync organization holidays')
    parser.add_argument('--org-id', type=str, help='Optional organization ID (syncs for all orgs if not specified)')
    args = parser.parse_args()
    
    try:
        from app.app import create_app
        from app.extensions import mongo
        from bson import ObjectId
        from app.services.holiday_service import HolidayService
        
        app, _ = create_app()
        
        with app.app_context():
            if args.org_id:
                orgs = [mongo.db.organizations.find_one({'_id': ObjectId(args.org_id)})]
            else:
                orgs = list(mongo.db.organizations.find({'is_active': True}))
            
            current_year = datetime.now().year
            master_holidays = list(mongo.db.holidays.find({
                'is_master': True,
                'date_observed': {
                    '$gte': datetime(current_year, 1, 1).date(),
                    '$lt': datetime(current_year + 1, 1, 1).date()
                }
            }))
            
            results = {'organizations_processed': 0, 'holidays_synced': 0, 'errors': []}
            
            for org in orgs:
                if not org:
                    continue
                
                results['organizations_processed'] += 1
                
                try:
                    for master_holiday in master_holidays:
                        existing = mongo.db.org_holidays.find_one({
                            'holiday_id': master_holiday['_id'],
                            'organization_id': org['_id']
                        })
                        
                        if not existing:
                            HolidayService.import_master_holiday_to_organization(
                                str(org['_id']),
                                str(master_holiday['_id'])
                            )
                            results['holidays_synced'] += 1
                
                except Exception as e:
                    error_msg = f"Failed to sync holidays for org {org.get('name', org['_id'])}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"  ⚠️ {error_msg}")
            
            print(f"✅ Processed {results['organizations_processed']} organizations")
            print(f"   Synced {results['holidays_synced']} holidays ({len(results['errors'])} errors)")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

