#!/usr/bin/env python3
"""
Migration script to add is_bookable field to existing activities and classes.

This script:
1. Updates all existing activities to have is_bookable=True (if not already set)
2. Updates all existing classes to have is_bookable=True (if not already set)
"""

import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_is_bookable():
    """Migrate existing activities and classes to include is_bookable field"""
    mongo_uri = os.environ.get('MONGODB_URI')
    if not mongo_uri:
        print("Error: MONGODB_URI not found in environment variables")
        return
    
    client = MongoClient(mongo_uri)
    db = client.adrilly
    
    print("Starting migration: Adding is_bookable field to activities and classes...")
    print("-" * 60)
    
    # Update activities
    print("\n1. Updating activities...")
    activities_result = db.activities.update_many(
        {'is_bookable': {'$exists': False}},
        {'$set': {'is_bookable': True}}
    )
    print(f"   ✅ Updated {activities_result.modified_count} activities with is_bookable=True")
    
    # Also update activities that might have is_bookable set to None
    activities_null_result = db.activities.update_many(
        {'is_bookable': None},
        {'$set': {'is_bookable': True}}
    )
    print(f"   ✅ Updated {activities_null_result.modified_count} activities with is_bookable=None to True")
    
    # Update classes
    print("\n2. Updating classes...")
    classes_result = db.classes.update_many(
        {'is_bookable': {'$exists': False}},
        {'$set': {'is_bookable': True}}
    )
    print(f"   ✅ Updated {classes_result.modified_count} classes with is_bookable=True")
    
    # Also update classes that might have is_bookable set to None
    classes_null_result = db.classes.update_many(
        {'is_bookable': None},
        {'$set': {'is_bookable': True}}
    )
    print(f"   ✅ Updated {classes_null_result.modified_count} classes with is_bookable=None to True")
    
    # For classes without is_bookable, try to inherit from activity if schedule_item_id exists
    print("\n3. Updating classes without is_bookable by inheriting from activity...")
    classes_without_bookable = db.classes.find({
        '$or': [
            {'is_bookable': {'$exists': False}},
            {'is_bookable': None}
        ],
        'schedule_item_id': {'$exists': True, '$ne': None}
    })
    
    updated_from_activity = 0
    for class_doc in classes_without_bookable:
        schedule_item_id = class_doc.get('schedule_item_id')
        if schedule_item_id:
            # Get schedule item
            schedule_item = db.schedules.find_one({'_id': schedule_item_id})
            if schedule_item and schedule_item.get('activity_id'):
                # Get activity
                activity = db.activities.find_one({'_id': schedule_item['activity_id']})
                if activity:
                    is_bookable = activity.get('is_bookable', True)
                    db.classes.update_one(
                        {'_id': class_doc['_id']},
                        {'$set': {'is_bookable': is_bookable}}
                    )
                    updated_from_activity += 1
    
    print(f"   ✅ Updated {updated_from_activity} classes by inheriting is_bookable from their activities")
    
    # Summary
    print("\n" + "-" * 60)
    print("Migration Summary:")
    total_activities = activities_result.modified_count + activities_null_result.modified_count
    total_classes = classes_result.modified_count + classes_null_result.modified_count + updated_from_activity
    print(f"   Total activities updated: {total_activities}")
    print(f"   Total classes updated: {total_classes}")
    print("\n✅ Migration completed successfully!")
    
    client.close()

if __name__ == '__main__':
    try:
        migrate_is_bookable()
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

