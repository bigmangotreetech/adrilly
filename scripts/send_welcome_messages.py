#!/usr/bin/env python3
"""
Send Welcome Messages
Sends welcome messages to new users who joined in the last 24 hours.
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
        from app.models.user import User
        
        app, _ = create_app()
        
        with app.app_context():
            yesterday = datetime.utcnow() - timedelta(days=1)
            whatsapp_service = EnhancedWhatsAppService()
            
            new_users = mongo.db.users.find({
                'created_at': {'$gte': yesterday},
                'role': 'student',
                'welcome_message_sent': {'$ne': True},
                'phone_number': {'$exists': True, '$ne': None}
            })
            
            results = {'total_new_users': 0, 'successful': 0, 'failed': 0}
            
            for user_data in new_users:
                user = User.from_dict(user_data)
                success, message = whatsapp_service.send_welcome_message(str(user._id))
                
                results['total_new_users'] += 1
                if success:
                    results['successful'] += 1
                    mongo.db.users.update_one(
                        {'_id': user._id},
                        {'$set': {'welcome_message_sent': True}}
                    )
                else:
                    results['failed'] += 1
            
            print(f"✅ Sent {results['successful']} welcome messages ({results['failed']} failed)")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
