from celery import Celery
from datetime import datetime, timedelta
from app.extensions import mongo
from app.models.class_schedule import Class
from app.models.payment import Payment
from app.models.user import User
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from bson import ObjectId
import os
import sys

# Add the root directory to Python path for daily_class_creator import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Initialize Celery
celery = Celery('enhanced_reminders')
celery.config_from_object('config')

@celery.task
def send_automated_class_reminders():
    """Send automated class reminders 2 hours before classes"""
    try:
        now = datetime.utcnow()
        reminder_time = now + timedelta(hours=2)
        
        # Find classes starting in approximately 2 hours that haven't had reminders sent
        start_window = reminder_time - timedelta(minutes=30)  # 30-minute window
        end_window = reminder_time + timedelta(minutes=30)
        
        classes_cursor = mongo.db.classes.find({
            'scheduled_at': {
                '$gte': start_window,
                '$lte': end_window
            },
            'status': 'scheduled',
            'reminder_sent': {'$ne': True}
        })
        
        whatsapp_service = EnhancedWhatsAppService()
        results = {
            'processed_classes': 0,
            'successful_reminders': 0,
            'failed_reminders': 0,
            'total_students_notified': 0
        }
        
        for class_data in classes_cursor:
            class_obj = Class.from_dict(class_data)
            
            # Send bulk reminders for this class
            success, message, reminder_results = whatsapp_service.send_bulk_reminders(
                str(class_obj._id), hours_before=2
            )
            
            results['processed_classes'] += 1
            
            if success:
                results['successful_reminders'] += 1
                results['total_students_notified'] += len(reminder_results.get('successful', []))
            else:
                results['failed_reminders'] += 1
            
            print(f"Class {class_obj.title}: {message}")
        
        print(f"Automated reminders summary: {results}")
        return f"Processed {results['processed_classes']} classes, notified {results['total_students_notified']} students"
        
    except Exception as e:
        print(f"Error in send_automated_class_reminders: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def send_payment_reminders():
    """Send payment reminders for overdue and upcoming payments"""
    try:
        now = datetime.utcnow()
        whatsapp_service = EnhancedWhatsAppService()
        
        # Find overdue payments
        overdue_payments = mongo.db.payments.find({
            'due_date': {'$lt': now.date()},
            'status': {'$in': ['pending', 'overdue']},
            'reminder_history': {'$not': {'$size': {'$gte': 3}}}  # Max 3 reminders
        })
        
        # Find payments due in 3 days
        upcoming_due_date = (now + timedelta(days=3)).date()
        upcoming_payments = mongo.db.payments.find({
            'due_date': upcoming_due_date,
            'status': 'pending',
            'reminder_history': {'$exists': False}
        })
        
        results = {
            'overdue_processed': 0,
            'upcoming_processed': 0,
            'successful': 0,
            'failed': 0
        }
        
        # Process overdue payments
        for payment_data in overdue_payments:
            payment = Payment.from_dict(payment_data)
            days_overdue = payment.get_days_overdue()
            
            # Determine urgency based on days overdue
            if days_overdue > 14:
                urgency = 'final'
            elif days_overdue > 7:
                urgency = 'urgent'
            else:
                urgency = 'normal'
            
            success, message = whatsapp_service.send_payment_reminder(
                str(payment._id), urgency
            )
            
            results['overdue_processed'] += 1
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
        
        # Process upcoming payments
        for payment_data in upcoming_payments:
            payment = Payment.from_dict(payment_data)
            
            success, message = whatsapp_service.send_payment_reminder(
                str(payment._id), 'gentle'
            )
            
            results['upcoming_processed'] += 1
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
        
        print(f"Payment reminders summary: {results}")
        return f"Sent {results['successful']} payment reminders, {results['failed']} failed"
        
    except Exception as e:
        print(f"Error in send_payment_reminders: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def send_welcome_messages_to_new_users():
    """Send welcome messages to users who joined in the last 24 hours"""
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Find new users from last 24 hours who haven't received welcome messages
        new_users = mongo.db.users.find({
            'created_at': {'$gte': yesterday},
            'role': 'student',
            'welcome_message_sent': {'$ne': True},
            'phone_number': {'$exists': True, '$ne': None}
        })
        
        whatsapp_service = EnhancedWhatsAppService()
        results = {
            'total_new_users': 0,
            'successful': 0,
            'failed': 0
        }
        
        for user_data in new_users:
            user = User.from_dict(user_data)
            
            success, message = whatsapp_service.send_welcome_message(str(user._id))
            
            results['total_new_users'] += 1
            if success:
                results['successful'] += 1
                
                # Mark as welcome message sent
                mongo.db.users.update_one(
                    {'_id': user._id},
                    {'$set': {'welcome_message_sent': True}}
                )
            else:
                results['failed'] += 1
        
        print(f"Welcome messages summary: {results}")
        return f"Sent {results['successful']} welcome messages to new users"
        
    except Exception as e:
        print(f"Error in send_welcome_messages: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def cleanup_old_whatsapp_logs():
    """Clean up old WhatsApp logs to maintain database performance"""
    try:
        # Keep logs for 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # Delete old message logs
        result = mongo.db.whatsapp_logs.delete_many({
            'timestamp': {'$lt': cutoff_date}
        })
        
        print(f"Cleaned up {result.deleted_count} old WhatsApp message logs")
        
        # Delete old RSVP logs
        result = mongo.db.rsvp_logs.delete_many({
            'timestamp': {'$lt': cutoff_date}
        })
        
        print(f"Cleaned up {result.deleted_count} old RSVP logs")
        
        return f"Cleanup completed"
        
    except Exception as e:
        print(f"Error in cleanup_old_whatsapp_logs: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def generate_whatsapp_analytics_report():
    """Generate daily WhatsApp analytics reports for organizations"""
    try:
        whatsapp_service = EnhancedWhatsAppService()
        
        # Get all active organizations
        organizations = mongo.db.organizations.find({'is_active': True})
        
        results = {
            'organizations_processed': 0,
            'reports_generated': 0
        }
        
        for org_data in organizations:
            org_id = str(org_data['_id'])
            org_name = org_data.get('name', 'Unknown')
            
            # Get analytics for last 7 days
            analytics = whatsapp_service.get_messaging_analytics(org_id, days=7)
            
            if analytics:
                # Store analytics report
                report = {
                    'organization_id': ObjectId(org_id),
                    'organization_name': org_name,
                    'period_start': datetime.utcnow() - timedelta(days=7),
                    'period_end': datetime.utcnow(),
                    'analytics': analytics,
                    'generated_at': datetime.utcnow()
                }
                
                mongo.db.whatsapp_analytics_reports.insert_one(report)
                results['reports_generated'] += 1
            
            results['organizations_processed'] += 1
        
        print(f"Analytics reports summary: {results}")
        return f"Generated {results['reports_generated']} analytics reports"
        
    except Exception as e:
        print(f"Error in generate_whatsapp_analytics_report: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def update_class_statuses():
    """Update class statuses based on current time"""
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
        completion_time = now - timedelta(hours=2)
        result = mongo.db.classes.update_many(
            {
                'scheduled_at': {'$lte': completion_time},
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
        print(f"Error in update_class_statuses: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def send_daily_digest():
    """Send daily digest messages to coaches and admins"""
    try:
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        
        whatsapp_service = EnhancedWhatsAppService()
        results = {
            'digests_sent': 0,
            'errors': 0
        }
        
        # Find all coaches and admins
        coaches_and_admins = mongo.db.users.find({
            'role': {'$in': ['coach', 'center_admin', 'org_admin']},
            'is_active': True,
            'phone_number': {'$exists': True, '$ne': None}
        })
        
        for user_data in coaches_and_admins:
            user = User.from_dict(user_data)
            
            # Get tomorrow's classes for this user's organization
            tomorrow_classes = list(mongo.db.classes.find({
                'organization_id': user.organization_id,
                'scheduled_at': {
                    '$gte': tomorrow.replace(hour=0, minute=0, second=0, microsecond=0),
                    '$lt': tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
                },
                'status': 'scheduled'
            }))
            
            # Get pending payments for organization
            pending_payments = mongo.db.payments.count_documents({
                'organization_id': user.organization_id,
                'status': {'$in': ['pending', 'overdue']}
            })
            
            # Create digest message
            digest_message = f"""
📊 *Daily Digest - {tomorrow.strftime('%B %d, %Y')}*

Hi {user.name}! 👋

📅 *Tomorrow's Classes:* {len(tomorrow_classes)}
💳 *Pending Payments:* {pending_payments}

Have a great day! 🌟
            """.strip()
            
            # Send digest if there's relevant information
            if len(tomorrow_classes) > 0 or pending_payments > 0:
                success, message = whatsapp_service.send_twilio_message(
                    user.phone_number, digest_message, message_type='daily_digest'
                )
                
                if success:
                    results['digests_sent'] += 1
                else:
                    results['errors'] += 1
        
        print(f"Daily digest summary: {results}")
        return f"Sent {results['digests_sent']} daily digests"
        
    except Exception as e:
        print(f"Error in send_daily_digest: {str(e)}")
        return f"Error: {str(e)}"

@celery.task
def create_daily_classes(days_ahead=7, org_id=None):
    """Celery task to automatically create classes based on center schedules"""
    try:
        from daily_class_creator import DailyClassCreator
        
        creator = DailyClassCreator()
        
        # Start from tomorrow
        start_date = (datetime.utcnow() + timedelta(days=1)).date()
        
        print(f"🚀 Starting automated class creation")
        print(f"📅 Creating classes for {days_ahead} days starting from {start_date}")
        
        # Create classes
        created_classes = creator.create_classes_for_range(
            start_date=start_date,
            days_ahead=days_ahead,
            org_id=org_id
        )
        
        # Cleanup old classes (older than 30 days)
        cleaned_count = creator.cleanup_old_classes(30)
        
        creator.close()
        
        result = {
            'success': True,
            'created_classes': len(created_classes),
            'cleaned_classes': cleaned_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        print(f"✅ Class creation task completed: {result}")
        return f"Created {len(created_classes)} classes, cleaned {cleaned_count} old classes"
        
    except Exception as e:
        error_msg = f"Error in create_daily_classes: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@celery.task
def create_classes_for_organization(org_id, days_ahead=7):
    """Create classes for a specific organization"""
    return create_daily_classes(days_ahead=days_ahead, org_id=org_id)

# Task scheduling configuration
if __name__ == '__main__':
    # This would be configured in your task scheduler (like Celery Beat)
    
    # Example schedule configuration:
    # Every 30 minutes - check for class reminders
    # send_automated_class_reminders.apply_async()
    
    # Daily at 9 AM - send payment reminders  
    # send_payment_reminders.apply_async()
    
    # Daily at 10 PM - send daily digest
    # send_daily_digest.apply_async()
    
    # Weekly - cleanup old logs
    # cleanup_old_whatsapp_logs.apply_async()
    
    pass
