"""
Holiday Management Celery Tasks
Automated holiday importing and management
"""

from datetime import datetime, timedelta, date
import os
import sys
import logging

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from app.extensions import mongo

logger = logging.getLogger(__name__)

# Import the shared Celery instance from extensions
from app.extensions import celery

@celery.task(bind=True)
def import_yearly_holidays(self, year=None, country_code='IN'):
    """Import holidays for a specific year"""
    try:
        if year is None:
            year = datetime.now().year
        
        logger.info(f"🎉 Starting holiday import for year {year}")
        
        # Try to import the holiday fetcher
        try:
            from fetch_indian_holidays import IndianHolidayFetcher
        except ImportError:
            error_msg = "IndianHolidayFetcher not available"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'year': year,
                'imported_holidays': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        fetcher = IndianHolidayFetcher()
        success = fetcher.fetch_and_store_holidays(year)
        
        # Count imported holidays
        holiday_count = mongo.db.holidays.count_documents({
            'date_observed': {
                '$gte': datetime(year, 1, 1).date(),
                '$lt': datetime(year + 1, 1, 1).date()
            },
            'is_master': True
        })
        
        result = {
            'success': success,
            'year': year,
            'country_code': country_code,
            'imported_holidays': holiday_count if success else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            logger.info(f"✅ Holiday import completed: {result}")
        else:
            logger.error(f"❌ Holiday import failed: {result}")
        
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'year': year,
            'imported_holidays': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.error(f"❌ Holiday import task failed: {error_result}")
        return error_result

@celery.task(bind=True)
def import_next_year_holidays(self):
    """Import holidays for the next year (run at end of current year)"""
    current_year = datetime.now().year
    next_year = current_year + 1
    
    logger.info(f"📅 Importing holidays for next year: {next_year}")
    return import_yearly_holidays.delay(year=next_year)

@celery.task(bind=True)
def sync_organization_holidays(self, org_id=None):
    """Sync master holidays with organization holidays"""
    try:
        logger.info(f"🔄 Syncing organization holidays for org: {org_id}")
        
        # If no org_id specified, sync for all organizations
        if org_id:
            orgs = [mongo.db.organizations.find_one({'_id': org_id})]
        else:
            orgs = list(mongo.db.organizations.find({'is_active': True}))
        
        results = {
            'organizations_processed': 0,
            'holidays_synced': 0,
            'errors': []
        }
        
        current_year = datetime.now().year
        
        # Get all master holidays for current year
        master_holidays = list(mongo.db.holidays.find({
            'is_master': True,
            'date_observed': {
                '$gte': datetime(current_year, 1, 1).date(),
                '$lt': datetime(current_year + 1, 1, 1).date()
            }
        }))
        
        for org in orgs:
            if not org:
                continue
                
            results['organizations_processed'] += 1
            
            try:
                # Import the service
                from app.services.holiday_service import HolidayService
                
                for master_holiday in master_holidays:
                    # Check if organization already has this holiday
                    existing = mongo.db.org_holidays.find_one({
                        'holiday_id': master_holiday['_id'],
                        'organization_id': org['_id']
                    })
                    
                    if not existing:
                        # Add to organization holidays
                        HolidayService.import_master_holiday_to_organization(
                            str(org['_id']),
                            str(master_holiday['_id'])
                        )
                        results['holidays_synced'] += 1
                        
            except Exception as e:
                error_msg = f"Failed to sync holidays for org {org.get('name', org['_id'])}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        result = {
            'success': len(results['errors']) == 0,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Holiday sync completed: {result}")
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.error(f"❌ Holiday sync failed: {error_result}")
        return error_result

@celery.task(bind=True)
def cleanup_expired_holidays(self):
    """Clean up old holidays that are no longer relevant"""
    try:
        logger.info("🧹 Cleaning up expired holidays...")
        
        # Remove holidays older than 2 years
        cutoff_date = datetime.now() - timedelta(days=730)  # 2 years
        cutoff_date = cutoff_date.date()
        
        # Clean up master holidays
        master_result = mongo.db.holidays.delete_many({
            'is_master': True,
            'date_observed': {'$lt': cutoff_date}
        })
        
        # Clean up organization holidays for deleted master holidays
        org_result = mongo.db.org_holidays.delete_many({
            'holiday_id': {'$in': []}  # This will be updated with actual deleted IDs
        })
        
        result = {
            'success': True,
            'deleted_master_holidays': master_result.deleted_count,
            'deleted_org_holidays': org_result.deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Holiday cleanup completed: {result}")
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.error(f"❌ Holiday cleanup failed: {error_result}")
        return error_result

@celery.task(bind=True)
def validate_holiday_data(self):
    """Validate holiday data integrity"""
    try:
        logger.info("🔍 Validating holiday data...")
        
        issues = {
            'orphaned_org_holidays': [],
            'missing_master_holidays': [],
            'duplicate_holidays': [],
            'invalid_dates': []
        }
        
        # Check for orphaned organization holidays
        org_holidays = mongo.db.org_holidays.find({})
        for org_holiday in org_holidays:
            # Check if master holiday exists
            master_exists = mongo.db.holidays.find_one({
                '_id': org_holiday['holiday_id']
            })
            if not master_exists:
                issues['orphaned_org_holidays'].append(str(org_holiday['_id']))
            
            # Check if organization exists
            org_exists = mongo.db.organizations.find_one({
                '_id': org_holiday['organization_id']
            })
            if not org_exists:
                issues['orphaned_org_holidays'].append(str(org_holiday['_id']))
        
        # Check for duplicate master holidays
        pipeline = [
            {
                '$group': {
                    '_id': {
                        'name': '$name',
                        'date_observed': '$date_observed'
                    },
                    'count': {'$sum': 1},
                    'ids': {'$push': '$_id'}
                }
            },
            {
                '$match': {
                    'count': {'$gt': 1}
                }
            }
        ]
        
        duplicates = list(mongo.db.holidays.aggregate(pipeline))
        for dup in duplicates:
            issues['duplicate_holidays'].append({
                'name': dup['_id']['name'],
                'date': dup['_id']['date_observed'].isoformat() if isinstance(dup['_id']['date_observed'], date) else str(dup['_id']['date_observed']),
                'count': dup['count'],
                'ids': [str(id) for id in dup['ids']]
            })
        
        result = {
            'success': True,
            'issues_found': sum(len(issue_list) for issue_list in issues.values()),
            'issues': issues,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Holiday validation completed: {result}")
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.error(f"❌ Holiday validation failed: {error_result}")
        return error_result

# Periodic task configuration using Celery beat
from celery.schedules import crontab

@celery.on_after_configure.connect
def setup_holiday_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for holiday management"""
    
    # Import holidays for next year on December 31st at 11:00 PM
    sender.add_periodic_task(
        crontab(hour=23, minute=0, day_of_month=31, month_of_year=12),
        import_next_year_holidays.s(),
        name='import next year holidays'
    )
    
    # Sync organization holidays weekly on Sunday at 3:00 AM
    sender.add_periodic_task(
        crontab(hour=3, minute=0, day_of_week=0),  # Sunday at 3:00 AM
        sync_organization_holidays.s(),
        name='sync organization holidays'
    )
    
    # Clean up old holidays monthly on the 1st at 4:00 AM
    sender.add_periodic_task(
        crontab(hour=4, minute=0, day_of_month=1),  # 1st of month at 4:00 AM
        cleanup_expired_holidays.s(),
        name='cleanup expired holidays'
    )
    
    # Validate holiday data weekly on Monday at 9:00 AM
    sender.add_periodic_task(
        crontab(hour=9, minute=0, day_of_week=1),  # Monday at 9:00 AM
        validate_holiday_data.s(),
        name='validate holiday data'
    )
    
    logger.info("✅ Holiday management periodic tasks configured")
