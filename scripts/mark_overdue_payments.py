#!/usr/bin/env python3
"""
Mark Overdue Payments
Marks payments as overdue if they're past due date and still pending.
"""

import os
import sys
from datetime import datetime, date

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        
        app, _ = create_app()
        
        with app.app_context():
            today = date.today()
            print(f"Checking for overdue payments as of {today}")
            
            result = mongo.db.payments.update_many(
                {
                    'status': 'pending',
                    'due_date': {'$lt': today}
                },
                {
                    '$set': {
                        'status': 'overdue',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            overdue_count = result.modified_count
            
            # Update user payment status
            overdue_payments = mongo.db.payments.find({
                'status': 'overdue',
                'due_date': {'$lt': today}
            })
            
            users_updated = 0
            for payment in overdue_payments:
                if payment.get('user_id'):
                    mongo.db.users.update_one(
                        {'_id': payment['user_id']},
                        {
                            '$set': {
                                'payment_status': 'overdue',
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )
                    users_updated += 1
            
            print(f"✅ Marked {overdue_count} payments as overdue")
            print(f"   Updated {users_updated} user payment statuses")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

