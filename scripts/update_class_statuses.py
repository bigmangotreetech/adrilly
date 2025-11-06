#!/usr/bin/env python3
"""
Update Class Statuses
Marks classes as 'ongoing' if they've started and 'completed' if the end time has passed.
"""

import os
import sys
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    """Update class statuses based on current time"""
    try:
        from app.app import create_app
        app, _ = create_app()
        
        with app.app_context():
            from app.extensions import mongo
            
            now = datetime.utcnow()
            updated_count = 0
            
            print(f"Starting class status update at {now}")
            
            # Mark classes as ongoing if they've started
            result = mongo.db.classes.update_many(
                {
                    'scheduled_at': {'$lte': now},
                    'status': 'scheduled'
                },
                {'$set': {
                    'status': 'ongoing',
                    'updated_at': now
                }}
            )
            ongoing_count = result.modified_count
            updated_count += ongoing_count
            if ongoing_count > 0:
                print(f"  ✓ Marked {ongoing_count} classes as ongoing")
            
            # Mark classes as completed if current time is beyond class end time
            classes_cursor = mongo.db.classes.find({
                'status': {'$in': ['scheduled', 'ongoing']}
            })
            
            completed_classes = []
            for class_data in classes_cursor:
                scheduled_at = class_data.get('scheduled_at')
                duration_minutes = class_data.get('duration_minutes') or class_data.get('duration', 60)
                
                if scheduled_at:
                    end_time = scheduled_at + timedelta(minutes=duration_minutes)
                    if now >= end_time:
                        completed_classes.append(class_data['_id'])
            
            if completed_classes:
                result = mongo.db.classes.update_many(
                    {
                        '_id': {'$in': completed_classes},
                        'status': {'$ne': 'cancelled'}
                    },
                    {'$set': {
                        'status': 'completed',
                        'updated_at': now
                    }}
                )
                completed_count = result.modified_count
                updated_count += completed_count
                if completed_count > 0:
                    print(f"  ✓ Marked {completed_count} classes as completed")
            
            print(f"\n✅ Successfully updated status for {updated_count} classes")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
