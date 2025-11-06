#!/usr/bin/env python3
"""
Generate Recurring Payments
Generates payments for active payment plans.
"""

import os
import sys
from datetime import datetime, timedelta, date

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        from app.models.payments import Payment, PaymentPlan
        
        app, _ = create_app()
        
        with app.app_context():
            today = date.today()
            
            payment_plans = mongo.db.payment_plans.find({
                'is_active': True,
                'auto_generate': True,
                'next_payment_date': {'$lte': today}
            })
            
            generated_count = 0
            
            for plan_data in payment_plans:
                plan = PaymentPlan.from_dict(plan_data)
                
                existing_payment = mongo.db.payments.find_one({
                    'student_id': plan.student_id,
                    'due_date': plan.next_payment_date,
                    'payment_type': plan.cycle_type
                })
                
                if not existing_payment:
                    new_payment = Payment(
                        student_id=str(plan.student_id),
                        organization_id=str(plan.organization_id),
                        amount=plan.amount_per_cycle,
                        description=f"{plan.plan_name} - {plan.next_payment_date.strftime('%B %Y')}",
                        due_date=plan.next_payment_date,
                        payment_type=plan.cycle_type,
                        group_id=str(plan.group_id) if plan.group_id else None
                    )
                    
                    mongo.db.payments.insert_one(new_payment.to_dict())
                    generated_count += 1
                    print(f"  ✓ Generated payment for plan: {plan.plan_name}")
                
                # Update next payment date
                if plan.cycle_type == 'weekly':
                    next_date = plan.next_payment_date + timedelta(weeks=1)
                elif plan.cycle_type == 'monthly':
                    if plan.next_payment_date.month == 12:
                        next_date = plan.next_payment_date.replace(year=plan.next_payment_date.year + 1, month=1)
                    else:
                        next_date = plan.next_payment_date.replace(month=plan.next_payment_date.month + 1)
                elif plan.cycle_type == 'quarterly':
                    month = plan.next_payment_date.month + 3
                    year = plan.next_payment_date.year
                    if month > 12:
                        month -= 12
                        year += 1
                    next_date = plan.next_payment_date.replace(year=year, month=month)
                else:
                    next_date = plan.next_payment_date + timedelta(days=30)
                
                mongo.db.payment_plans.update_one(
                    {'_id': plan._id},
                    {'$set': {
                        'next_payment_date': next_date,
                        'updated_at': datetime.utcnow()
                    }}
                )
            
            print(f"✅ Generated {generated_count} recurring payments")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

