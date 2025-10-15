"""
Class Creation Celery Tasks
Automated class creation based on schedules
"""

from datetime import datetime, timedelta, date
import os
import sys
import logging

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from app.extensions import mongo
from bson import ObjectId

logger = logging.getLogger(__name__)

# Import the shared Celery instance from extensions (optional for Celery mode)
try:
    from app.extensions import celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery = None

def create_daily_classes_function(days_ahead=7, org_id=None):
    """Celery task to create daily classes based on schedules"""
    try:

        created_classes = []
        logger.info(f"🚀 Starting automated class creation task")
        logger.info(f"📅 Creating classes for {days_ahead} days ahead")
        
        # Import the class creator
        try:
            from daily_class_creator import DailyClassCreator
        except ImportError:
            error_msg = "DailyClassCreator not available"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'created_classes': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        creator = DailyClassCreator()
        
        # Start from tomorrow
        start_date = (datetime.utcnow() + timedelta(days=1)).date()

        if org_id == None:
            orgs = mongo.db.organizations.find({'is_active': True})
            for org in orgs:
                # Use ObjectId directly, don't convert to string
                org_object_id = org['_id']
                created_classes = creator.create_classes_for_range(
                    start_date=start_date,
                    days_ahead=days_ahead,
                    org_id=org_object_id
                )
                
        else:
            # Ensure org_id is ObjectId if passed as string
            if isinstance(org_id, str):
                org_id = ObjectId(org_id)
            # Create classes
            created_classes = creator.create_classes_for_range(
                start_date=start_date,
                days_ahead=days_ahead,
                org_id=org_id
            )
        
        # Cleanup old classes (older than 30 days)
        try:
            cleaned_count = creator.cleanup_old_classes(30)
        except Exception as e:
            logger.warning(f"⚠️ Class cleanup failed: {e}")
            cleaned_count = 0
        
        creator.close()
        
        result = {
            'success': True,
            'created_classes': len(created_classes),
            'cleaned_classes': cleaned_count,
            'start_date': start_date.isoformat(),
            'days_ahead': days_ahead,
            'organization_id': org_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Class creation task completed: {result}")
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'created_classes': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.error(f"❌ Class creation task failed: {error_result}")
        return error_result


    
def create_classes_for_organization_function(org_id, days_ahead=7):
    """Create classes for a specific organization (standalone function)"""
    logger.info(f"🏢 Creating classes for organization: {org_id}")
    return create_daily_classes_function(days_ahead=days_ahead, org_id=org_id)


# Celery task wrappers (only available if Celery is imported)
if CELERY_AVAILABLE:
    @celery.task(bind=True)
    def create_daily_classes(self, days_ahead=7, org_id=None):
        """Celery wrapper for create_daily_classes_function"""
        return create_daily_classes_function(days_ahead=days_ahead, org_id=org_id)
    
    @celery.task(bind=True)
    def create_classes_for_organization(self, org_id, days_ahead=7):
        """Celery wrapper for create_classes_for_organization_function"""
        return create_classes_for_organization_function(org_id=org_id, days_ahead=days_ahead)
    
        return verify_class_schedules_function()
else:
    # Dummy functions if Celery is not available
    def create_daily_classes(*args, **kwargs):
        logger.warning("Celery not available. Use create_daily_classes_function() instead.")
        return None
    
    def create_classes_for_organization(*args, **kwargs):
        logger.warning("Celery not available. Use create_classes_for_organization_function() instead.")
        return None
    
   
# Note: Periodic tasks are now configured in enhanced_reminder_tasks.py
# to avoid duplicate registrations

# Main execution block for standalone usage
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Class Creation Tasks - Run standalone or with Celery')
    parser.add_argument('action', choices=['create_classes', 'create_org_classes'], 
                       help='Action to perform')
    parser.add_argument('--days-ahead', type=int, default=7, 
                       help='Number of days ahead to create classes (default: 7)')
    parser.add_argument('--org-id', type=str, 
                       help='Organization ID for org-specific actions')
    
    args = parser.parse_args()
    
    # Setup logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"🚀 Running class creation task: {args.action}")
    
    if args.action == 'create_classes':
        # Convert org_id to ObjectId if provided as string
        org_id = ObjectId(args.org_id) if args.org_id else None
        result = create_daily_classes_function(days_ahead=args.days_ahead, org_id=org_id)
        print(f"\n✅ Result: {result}")
    
    elif args.action == 'create_org_classes':
        if not args.org_id:
            print("❌ Error: --org-id is required for create_org_classes action")
            sys.exit(1)
        # Convert org_id to ObjectId if provided as string
        org_id = ObjectId(args.org_id)
        result = create_classes_for_organization_function(org_id=org_id, days_ahead=args.days_ahead)
        print(f"\n✅ Result: {result}")
    
    
    print("\n🎉 Task completed successfully!")


