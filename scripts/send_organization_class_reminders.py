#!/usr/bin/env python3
"""
Send Organization Class Reminders
Sends class reminders based on each organization's reminder settings.
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
        from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
        
        app, _ = create_app()
        
        with app.app_context():
            now = datetime.utcnow()
            whatsapp_service = EnhancedWhatsAppService()
            
            organizations = mongo.db.organizations.find({'is_active': True})
            
            results = {
                'organizations_processed': 0,
                'classes_processed': 0,
                'reminders_sent': 0,
                'errors': 0
            }
            
            for org_data in organizations:
                org_id = org_data['_id']
                org_settings = org_data.get('settings', {})
                reminder_minutes = org_settings.get('reminder_minutes_before', 120)
                
                reminder_time = now + timedelta(minutes=reminder_minutes)
                start_window = reminder_time - timedelta(minutes=1)
                end_window = reminder_time + timedelta(minutes=1)
                
                classes = mongo.db.classes.find({
                    'organization_id': org_id,
                    'scheduled_at': {'$gte': start_window, '$lte': end_window},
                    'status': 'scheduled',
                    'reminder_sent': {'$ne': True}
                })
                
                for class_data in classes:
                    try:
                        success, message, reminder_results = whatsapp_service.send_bulk_reminders(
                            str(class_data['_id']), hours_before=reminder_minutes/60
                        )
                        results['classes_processed'] += 1
                        if success:
                            results['reminders_sent'] += len(reminder_results.get('successful', []))
                    except Exception as e:
                        results['errors'] += 1
                        print(f"  ⚠️ Error for class {class_data.get('_id')}: {str(e)}")
                
                results['organizations_processed'] += 1
            
            print(f"✅ Processed {results['organizations_processed']} orgs, {results['classes_processed']} classes")
            print(f"   Sent {results['reminders_sent']} reminders ({results['errors']} errors)")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
