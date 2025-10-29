"""
Billing Cycle Tasks
Scheduled tasks to process recurring billing cycles
"""

from datetime import datetime, date, timedelta
from app.extensions import mongo, celery
from bson import ObjectId
from calendar import monthrange
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)

@celery.task
def process_billing_cycles():
    """
    Process billing cycles for users with subscriptions
    Checks if today is the billing date and marks payment status as 'fee_due'
    """
    try:
        today = date.today()
        logger.info(f"Processing billing cycles for {today}")
        
        # Find all users with active subscriptions and next_billing_date
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
                
                # Convert to date if datetime
                if isinstance(next_billing_date, datetime):
                    next_billing_date = next_billing_date.date()
                
                # Check if billing date is today or past
                if next_billing_date and next_billing_date <= today:
                    # Mark as fee due
                    organization_id = user.get('organization_id')
                    subscription_ids = user.get('subscription_ids', [])
                    
                    if subscription_ids:
                        subscription_id = subscription_ids[0]
                        subscription = mongo.db.subscriptions.find_one({'_id': ObjectId(subscription_id)})
                        
                        if subscription:
                            # Update user payment status
                            mongo.db.users.update_one(
                                {'_id': user['_id']},
                                {
                                    '$set': {
                                        'payment_status': 'fee_due',
                                        'fee_due_date': today,
                                        'updated_at': datetime.utcnow()
                                    }
                                }
                            )
                            
                            # Create a payment record for tracking
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
                            
                            # Check if payment record already exists for this billing cycle
                            existing_payment = mongo.db.payments.find_one({
                                'user_id': user['_id'],
                                'due_date': today,
                                'subscription_id': ObjectId(subscription_id),
                                'status': {'$in': ['pending', 'paid']}
                            })
                            
                            if not existing_payment:
                                mongo.db.payments.insert_one(payment_record)
                                logger.info(f"Created fee_due payment for user {user.get('name')} ({user['_id']})")
                                fee_due_count += 1
                            else:
                                logger.info(f"Payment already exists for user {user.get('name')} ({user['_id']})")
                            
                            # Calculate and update next billing date
                            cycle_type = user.get('subscription_cycle_type', 'monthly')
                            next_billing = _calculate_next_billing(next_billing_date, cycle_type)
                            
                            mongo.db.users.update_one(
                                {'_id': user['_id']},
                                {
                                    '$set': {
                                        'next_billing_date': next_billing,
                                        'last_billing_date': next_billing_date,
                                        'updated_at': datetime.utcnow()
                                    }
                                }
                            )
                            
                            processed_count += 1
                            logger.info(f"Updated billing for user {user.get('name')}: Next billing {next_billing}")
                
            except Exception as user_error:
                logger.error(f"Error processing user {user.get('_id')}: {str(user_error)}")
                continue
        
        result_message = f"Billing cycle check complete: {processed_count} users processed, {fee_due_count} marked as fee_due"
        logger.info(result_message)
        return result_message
        
    except Exception as e:
        error_message = f"Error in process_billing_cycles: {str(e)}"
        logger.error(error_message)
        return error_message


def _calculate_next_billing(current_date, cycle_type):
    """
    Calculate next billing date based on cycle type
    Handles edge cases for dates 29, 30, 31
    """
    try:
        # Convert to date if datetime
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        
        billing_day = current_date.day
        
        if cycle_type == 'weekly':
            return current_date + timedelta(weeks=1)
        elif cycle_type == 'monthly':
            # Add one month
            next_date = current_date + relativedelta(months=1)
            # Handle edge cases for day 29, 30, 31
            last_day_of_month = monthrange(next_date.year, next_date.month)[1]
            if billing_day > last_day_of_month:
                # If billing day doesn't exist in next month, use last day of month
                next_date = next_date.replace(day=last_day_of_month)
            else:
                next_date = next_date.replace(day=billing_day)
            return next_date
        elif cycle_type == 'quarterly':
            # Add three months
            next_date = current_date + relativedelta(months=3)
            # Handle edge cases
            last_day_of_month = monthrange(next_date.year, next_date.month)[1]
            if billing_day > last_day_of_month:
                next_date = next_date.replace(day=last_day_of_month)
            else:
                next_date = next_date.replace(day=billing_day)
            return next_date
        elif cycle_type == 'yearly':
            # Add one year
            next_date = current_date + relativedelta(years=1)
            # Handle leap year edge case
            try:
                next_date = next_date.replace(day=billing_day)
            except ValueError:
                # Feb 29 in non-leap year -> Feb 28
                next_date = next_date.replace(day=28)
            return next_date
        else:
            # Default to monthly
            next_date = current_date + relativedelta(months=1)
            last_day_of_month = monthrange(next_date.year, next_date.month)[1]
            if billing_day > last_day_of_month:
                next_date = next_date.replace(day=last_day_of_month)
            else:
                next_date = next_date.replace(day=billing_day)
            return next_date
    except Exception as e:
        logger.error(f"Error calculating next billing date: {str(e)}")
        # Fallback to simple date addition
        if cycle_type == 'weekly':
            return current_date + timedelta(weeks=1)
        elif cycle_type == 'quarterly':
            return current_date + timedelta(days=90)
        elif cycle_type == 'yearly':
            return current_date + timedelta(days=365)
        else:  # monthly
            return current_date + timedelta(days=30)


# Periodic task configuration using Celery beat
from celery.schedules import crontab

@celery.on_after_configure.connect
def setup_billing_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for billing cycle management"""
    try:
        # Process billing cycles daily at 00:01 AM
        sender.add_periodic_task(
            crontab(hour=0, minute=1),
            process_billing_cycles.s(),
            name='process-daily-billing-cycles'
        )
        logger.info("✅ Billing cycle periodic task configured: Daily at 00:01")
        
        # Mark overdue payments daily at 00:30 AM
        sender.add_periodic_task(
            crontab(hour=0, minute=30),
            mark_overdue_payments.s(),
            name='mark-overdue-payments'
        )
        logger.info("✅ Overdue payment task configured: Daily at 00:30")
        
    except Exception as e:
        logger.error(f"❌ Failed to setup billing periodic tasks: {str(e)}")


@celery.task
def mark_overdue_payments():
    """
    Mark payments as overdue if they're past due date and still pending
    """
    try:
        today = date.today()
        logger.info(f"Checking for overdue payments as of {today}")
        
        # Find payments that are pending and past due
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
        
        # Update user payment status to overdue
        overdue_payments = mongo.db.payments.find({
            'status': 'overdue',
            'due_date': {'$lt': today}
        })
        
        for payment in overdue_payments:
            mongo.db.users.update_one(
                {'_id': payment['user_id']},
                {
                    '$set': {
                        'payment_status': 'overdue',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        
        message = f"Marked {result.modified_count} payments as overdue"
        logger.info(message)
        return message
        
    except Exception as e:
        error_message = f"Error marking overdue payments: {str(e)}"
        logger.error(error_message)
        return error_message

