#!/usr/bin/env python3
"""
Send Payment Reminders
Sends payment reminders for overdue and upcoming payments.
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
        from app.models.payments import Payment
        
        app, _ = create_app()
        
        with app.app_context():
            now = datetime.utcnow()
            whatsapp_service = EnhancedWhatsAppService()
            
            # Find overdue payments
            overdue_payments = mongo.db.payments.find({
                'due_date': {'$lt': now.date()},
                'status': {'$in': ['pending', 'overdue']},
                'reminder_history': {'$not': {'$size': {'$gte': 3}}}
            })
            
            # Find payments due in 3 days
            upcoming_due_date = (now + timedelta(days=3)).date()
            upcoming_payments = mongo.db.payments.find({
                'due_date': upcoming_due_date,
                'status': 'pending',
                'reminder_history': {'$exists': False}
            })
            
            results = {'overdue_processed': 0, 'upcoming_processed': 0, 'successful': 0, 'failed': 0}
            
            for payment_data in overdue_payments:
                payment = Payment.from_dict(payment_data)
                days_overdue = payment.get_days_overdue()
                urgency = 'final' if days_overdue > 14 else 'urgent' if days_overdue > 7 else 'normal'
                
                success, message = whatsapp_service.send_payment_reminder(str(payment._id), urgency)
                results['overdue_processed'] += 1
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
            
            for payment_data in upcoming_payments:
                payment = Payment.from_dict(payment_data)
                success, message = whatsapp_service.send_payment_reminder(str(payment._id), 'gentle')
                results['upcoming_processed'] += 1
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
            
            print(f"✅ Sent {results['successful']} payment reminders ({results['failed']} failed)")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
