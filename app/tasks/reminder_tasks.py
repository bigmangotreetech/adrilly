from datetime import datetime, timedelta
from celery import Celery
from app.extensions import mongo
from app.services.whatsapp_service import WhatsAppService
from app.models.class_schedule import Class
from app.models.payment import Payment
from bson import ObjectId

# Initialize Celery (will be properly configured in app.py)
celery = Celery('sports_coaching')

@celery.task
def send_class_reminders(hours_before=2):
    """Send class reminders for upcoming classes"""
    try:
        whatsapp_service = WhatsAppService()
        
        # Calculate the time window for reminders
        now = datetime.utcnow()
        reminder_time = now + timedelta(hours=hours_before)
        
        # Find classes that need reminders
        # Classes scheduled within the next 'hours_before' hours that haven't had reminders sent
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
            
            # Send reminder
            success, message = whatsapp_service.send_class_reminder(str(class_obj._id), hours_before)
            
            if success:
                sent_count += 1
                print(f"Sent reminder for class: {class_obj.title} - {message}")
            else:
                print(f"Failed to send reminder for class: {class_obj.title} - {message}")
        
        return f"Processed {sent_count} class reminders"
    
    except Exception as e:
        print(f"Error in send_class_reminders: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def send_payment_reminders():
    """Send payment reminders for overdue payments"""
    try:
        whatsapp_service = WhatsAppService()
        
        # Find overdue payments
        today = datetime.utcnow().date()
        overdue_payments = mongo.db.payments.find({
            'status': {'$in': ['pending', 'overdue']},
            'due_date': {'$lt': today}
        })
        
        sent_count = 0
        for payment_data in overdue_payments:
            payment = Payment.from_dict(payment_data)
            
            # Send payment reminder
            success, message = whatsapp_service.send_payment_reminder(
                str(payment.student_id),
                {
                    'description': payment.description,
                    'amount': payment.amount,
                    'due_date': payment.due_date
                }
            )
            
            if success:
                sent_count += 1
                # Mark payment as overdue if it wasn't already
                if payment.status == 'pending':
                    payment.mark_overdue()
                    mongo.db.payments.update_one(
                        {'_id': payment._id},
                        {'$set': payment.to_dict()}
                    )
                print(f"Sent payment reminder for: {payment.description}")
            else:
                print(f"Failed to send payment reminder for: {payment.description} - {message}")
        
        return f"Processed {sent_count} payment reminders"
    
    except Exception as e:
        print(f"Error in send_payment_reminders: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def generate_recurring_payments():
    """Generate payments for active payment plans"""
    try:
        from app.models.payment import PaymentPlan
        
        today = datetime.utcnow().date()
        
        # Find payment plans that need new payments generated
        payment_plans = mongo.db.payment_plans.find({
            'is_active': True,
            'auto_generate': True,
            'next_payment_date': {'$lte': today}
        })
        
        generated_count = 0
        for plan_data in payment_plans:
            plan = PaymentPlan.from_dict(plan_data)
            
            # Check if payment already exists for this period
            existing_payment = mongo.db.payments.find_one({
                'student_id': plan.student_id,
                'due_date': plan.next_payment_date,
                'payment_type': plan.cycle_type
            })
            
            if not existing_payment:
                # Create new payment
                new_payment = Payment(
                    student_id=str(plan.student_id),
                    organization_id=str(plan.organization_id),
                    amount=plan.amount_per_cycle,
                    description=f"{plan.plan_name} - {plan.next_payment_date.strftime('%B %Y')}",
                    due_date=plan.next_payment_date,
                    payment_type=plan.cycle_type,
                    group_id=str(plan.group_id) if plan.group_id else None
                )
                
                result = mongo.db.payments.insert_one(new_payment.to_dict())
                generated_count += 1
                
                print(f"Generated payment for plan: {plan.plan_name}")
            
            # Update next payment date
            if plan.cycle_type == 'weekly':
                next_date = plan.next_payment_date + timedelta(weeks=1)
            elif plan.cycle_type == 'monthly':
                # Add one month
                if plan.next_payment_date.month == 12:
                    next_date = plan.next_payment_date.replace(year=plan.next_payment_date.year + 1, month=1)
                else:
                    next_date = plan.next_payment_date.replace(month=plan.next_payment_date.month + 1)
            elif plan.cycle_type == 'quarterly':
                # Add three months
                month = plan.next_payment_date.month + 3
                year = plan.next_payment_date.year
                if month > 12:
                    month -= 12
                    year += 1
                next_date = plan.next_payment_date.replace(year=year, month=month)
            else:
                next_date = plan.next_payment_date + timedelta(days=30)  # Default fallback
            
            # Update payment plan
            mongo.db.payment_plans.update_one(
                {'_id': plan._id},
                {'$set': {
                    'next_payment_date': next_date,
                    'updated_at': datetime.utcnow()
                }}
            )
        
        return f"Generated {generated_count} recurring payments"
    
    except Exception as e:
        print(f"Error in generate_recurring_payments: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def update_class_status():
    """Update class status based on current time"""
    try:
        now = datetime.utcnow()
        updated_count = 0
        
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
        updated_count += result.modified_count
        
        # Mark classes as completed if they've ended (assuming 2-hour duration max)
        result = mongo.db.classes.update_many(
            {
                'scheduled_at': {'$lte': now - timedelta(hours=2)},
                'status': 'ongoing'
            },
            {'$set': {
                'status': 'completed',
                'updated_at': now
            }}
        )
        updated_count += result.modified_count
        
        return f"Updated status for {updated_count} classes"
    
    except Exception as e:
        print(f"Error in update_class_status: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def cleanup_expired_otps():
    """Clean up expired OTP codes"""
    try:
        now = datetime.utcnow()
        
        result = mongo.db.users.update_many(
            {
                'otp_expires_at': {'$lt': now},
                'otp_code': {'$ne': None}
            },
            {'$set': {
                'otp_code': None,
                'otp_expires_at': None,
                'updated_at': now
            }}
        )
        
        return f"Cleaned up {result.modified_count} expired OTPs"
    
    except Exception as e:
        print(f"Error in cleanup_expired_otps: {str(e)}")
        return f"Error: {str(e)}"

# Periodic task configurations
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks"""
    
    # Send class reminders every 30 minutes
    sender.add_periodic_task(
        1800.0,  # 30 minutes
        send_class_reminders.s(hours_before=2),
        name='send class reminders'
    )
    
    # Send payment reminders daily at 9 AM
    sender.add_periodic_task(
        86400.0,  # 24 hours
        send_payment_reminders.s(),
        name='send payment reminders'
    )
    
    # Generate recurring payments daily at 6 AM
    sender.add_periodic_task(
        86400.0,  # 24 hours
        generate_recurring_payments.s(),
        name='generate recurring payments'
    )
    
    # Update class status every 15 minutes
    sender.add_periodic_task(
        900.0,  # 15 minutes
        update_class_status.s(),
        name='update class status'
    )
    
    # Clean up expired OTPs every hour
    sender.add_periodic_task(
        3600.0,  # 1 hour
        cleanup_expired_otps.s(),
        name='cleanup expired otps'
    )
    
    # Create daily classes every day at 6 AM
    from celery.schedules import crontab
    from app.tasks.enhanced_reminder_tasks import create_daily_classes
    sender.add_periodic_task(
        crontab(hour=6, minute=0),  # Daily at 6:00 AM
        create_daily_classes.s(days_ahead=7),
        name='create daily classes'
    ) 