#!/usr/bin/env python3
"""
Send Daily Digest
Sends daily digest messages to coaches and admins with tomorrow's schedule.
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
            now = datetime.utcnow()
            tomorrow = now + timedelta(days=1)
            whatsapp_service = EnhancedWhatsAppService()
            
            coaches_and_admins = mongo.db.users.find({
                'role': {'$in': ['coach', 'center_admin', 'org_admin']},
                'is_active': True,
                'phone_number': {'$exists': True, '$ne': None}
            })
            
            results = {'digests_sent': 0, 'errors': 0}
            
            for user_data in coaches_and_admins:
                user = User.from_dict(user_data)
                
                tomorrow_classes = list(mongo.db.classes.find({
                    'organization_id': user.organization_id,
                    'scheduled_at': {
                        '$gte': tomorrow.replace(hour=0, minute=0, second=0, microsecond=0),
                        '$lt': tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
                    },
                    'status': 'scheduled'
                }))
                
                pending_payments = mongo.db.payments.count_documents({
                    'organization_id': user.organization_id,
                    'status': {'$in': ['pending', 'overdue']}
                })
                
                digest_message = f"""
📊 *Daily Digest - {tomorrow.strftime('%B %d, %Y')}*

Hi {user.name}! 👋

📅 *Tomorrow's Classes:* {len(tomorrow_classes)}
💳 *Pending Payments:* {pending_payments}

Have a great day! 🌟
                """.strip()
                
                if len(tomorrow_classes) > 0 or pending_payments > 0:
                    try:
                        success, message = whatsapp_service.send_message(
                            str(user.phone_number),
                            digest_message
                        )
                        if success:
                            results['digests_sent'] += 1
                        else:
                            results['errors'] += 1
                    except Exception as e:
                        results['errors'] += 1
                        print(f"  ⚠️ Error sending to {user.name}: {str(e)}")
            
            print(f"✅ Sent {results['digests_sent']} daily digests ({results['errors']} errors)")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

