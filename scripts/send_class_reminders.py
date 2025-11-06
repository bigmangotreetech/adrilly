#!/usr/bin/env python3
"""
Send Class Reminders
Sends WhatsApp reminders to students for upcoming classes.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    parser = argparse.ArgumentParser(description='Send class reminders')
    parser.add_argument('--hours-before', type=int, default=2, help='Hours before class to send reminder (default: 2)')
    args = parser.parse_args()
    
    try:
        from app.app import create_app
        from app.extensions import mongo
        from app.services.whatsapp_service import WhatsAppService
        from app.models.class_schedule import Class
        
        app, _ = create_app()
        
        with app.app_context():
            whatsapp_service = WhatsAppService()
            now = datetime.utcnow()
            reminder_time = now + timedelta(hours=args.hours_before)
            
            classes_cursor = mongo.db.classes.find({
                'scheduled_at': {
                    '$gte': now,
                    '$lte': reminder_time
                },
                'reminder_sent': {'$ne': True},
                'status': 'scheduled'
            })
            
            sent_count = 0
            for class_data in classes_cursor:
                class_obj = Class.from_dict(class_data)
                success, message = whatsapp_service.send_class_reminder(str(class_obj._id), args.hours_before)
                
                if success:
                    sent_count += 1
                    print(f"✓ Sent reminder for: {class_obj.title}")
                else:
                    print(f"✗ Failed: {class_obj.title} - {message}")
            
            print(f"\n✅ Processed {sent_count} class reminders")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
