#!/usr/bin/env python3
"""
Process Billing Cycles
Processes billing cycles for users with subscriptions and marks payments as due.
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
        from bson import ObjectId
        from calendar import monthrange
        from dateutil.relativedelta import relativedelta
        
        app, _ = create_app()
        
        with app.app_context():
            today = date.today()
            print(f"Processing billing cycles for {today}")
            
            users_with_subscriptions = mongo.db.users.find({
                'subscription_ids': {'$exists': True, '$ne': []},
                'next_billing_date': {'$exists': True},
                'is_active': True
            })
            
            processed_count = 0
            fee_due_count = 0
            
            for user in users_with_subscriptions:
                try:
                    next_billing_date = user.get('next_billing_date')
                    if isinstance(next_billing_date, datetime):
                        next_billing_date = next_billing_date.date()
                    
                    if next_billing_date and next_billing_date <= today:
                        # Mark as fee due and create payment record
                        organization_id = user.get('organization_id')
                        subscription_ids = user.get('subscription_ids', [])
                        
                        if subscription_ids:
                            subscription_id = subscription_ids[0]
                            subscription = mongo.db.subscriptions.find_one({'_id': ObjectId(subscription_id)})
                            
                            if subscription:
                                mongo.db.users.update_one(
                                    {'_id': user['_id']},
                                    {'$set': {
                                        'payment_status': 'fee_due',
                                        'fee_due_date': today,
                                        'updated_at': datetime.utcnow()
                                    }}
                                )
                                
                                # Create payment record
                                existing_payment = mongo.db.payments.find_one({
                                    'user_id': user['_id'],
                                    'due_date': today,
                                    'subscription_id': ObjectId(subscription_id),
                                    'status': {'$in': ['pending', 'paid']}
                                })
                                
                                if not existing_payment:
                                    payment_record = {
                                        'user_id': user['_id'],
                                        'organization_id': organization_id,
                                        'subscription_id': ObjectId(subscription_id),
                                        'amount': user.get('subscription_amount', subscription.get('price', 0)),
                                        'cycle_type': user.get('subscription_cycle_type', 'monthly'),
                                        'due_date': today,
                                        'status': 'pending',
                                        'payment_type': 'subscription',
                                        'description': f"{subscription.get('name', 'Subscription')} - {next_billing_date.strftime('%B %Y')}",
                                        'created_at': datetime.utcnow(),
                                        'created_by_system': True
                                    }
                                    mongo.db.payments.insert_one(payment_record)
                                    fee_due_count += 1
                                
                                # Calculate next billing date
                                cycle_type = user.get('subscription_cycle_type', 'monthly')
                                if cycle_type == 'weekly':
                                    next_billing = next_billing_date + relativedelta(weeks=1)
                                elif cycle_type == 'monthly':
                                    next_billing = next_billing_date + relativedelta(months=1)
                                    last_day = monthrange(next_billing.year, next_billing.month)[1]
                                    if next_billing_date.day > last_day:
                                        next_billing = next_billing.replace(day=last_day)
                                    else:
                                        next_billing = next_billing.replace(day=next_billing_date.day)
                                elif cycle_type == 'quarterly':
                                    next_billing = next_billing_date + relativedelta(months=3)
                                elif cycle_type == 'yearly':
                                    next_billing = next_billing_date + relativedelta(years=1)
                                else:
                                    next_billing = next_billing_date + relativedelta(months=1)
                                
                                mongo.db.users.update_one(
                                    {'_id': user['_id']},
                                    {'$set': {
                                        'next_billing_date': next_billing,
                                        'last_billing_date': next_billing_date,
                                        'updated_at': datetime.utcnow()
                                    }}
                                )
                                
                                processed_count += 1
                
                except Exception as user_error:
                    print(f"  ⚠️ Error processing user {user.get('_id')}: {str(user_error)}")
                    continue
            
            print(f"✅ Processed {processed_count} users, marked {fee_due_count} as fee_due")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

