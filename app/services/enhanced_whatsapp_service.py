import os
import requests
from datetime import datetime, timedelta
from twilio.rest import Client
from app.extensions import mongo
from app.models.class_schedule import Class
from app.models.attendance import Attendance
from app.models.user import User
from app.models.payment import Payment
from flask import current_app
import re
from typing import Dict, List, Tuple, Optional
import json
from bson import ObjectId

class EnhancedWhatsAppService:
    """Enhanced enterprise-grade WhatsApp messaging service with advanced features"""
    
    def __init__(self):
        self.twilio_client = None
        self.interakt_api_key = None
        self.interakt_base_url = None
        
        # Initialize Twilio if credentials are available
        if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
            self.twilio_client = Client(
                os.getenv('TWILIO_ACCOUNT_SID'),
                os.getenv('TWILIO_AUTH_TOKEN')
            )
        
        # Initialize Interakt if credentials are available
        if os.getenv('INTERAKT_API_KEY'):
            self.interakt_api_key = os.getenv('INTERAKT_API_KEY')
            self.interakt_base_url = os.getenv('INTERAKT_BASE_URL', 'https://api.interakt.ai')
        
        # Message templates for different scenarios
        self.message_templates = {
            'class_reminder': self._create_class_reminder_template,
            'payment_reminder': self._create_payment_reminder_template,
            'class_cancelled': self._create_cancellation_template,
            'welcome_message': self._create_welcome_template,
            'achievement_notification': self._create_achievement_template,
            'feed_notification': self._create_feed_notification_template
        }
        
        # RSVP response patterns
        self.rsvp_patterns = {
            'yes': [r'\byes\b', r'\bconfirm\b', r'\battend\b', r'\bcoming\b', r'✅', r'👍'],
            'no': [r'\bno\b', r'\bcancel\b', r'\bskip\b', r'\babsent\b', r'❌', r'👎'],
            'maybe': [r'\bmaybe\b', r'\bunsure\b', r'\btentative\b', r'\bpossibly\b', r'⏳', r'🤔']
        }
    
    def send_twilio_message(self, to_number: str, message: str, media_url: str = None, 
                           message_type: str = 'text') -> Tuple[bool, str]:
        """Enhanced Twilio message sending with better error handling"""
        if not self.twilio_client:
            return False, "Twilio not configured"
        
        try:
            # Normalize phone number
            to_number = self._normalize_phone_number(to_number)
            
            message_data = {
                'from_': os.getenv('TWILIO_WHATSAPP_FROM'),
                'body': message,
                'to': f'whatsapp:{to_number}'
            }
            
            if media_url:
                message_data['media_url'] = [media_url]
            
            # Send message
            sent_message = self.twilio_client.messages.create(**message_data)
            
            # Log message for tracking
            self._log_message(to_number, message, sent_message.sid, message_type, 'sent')
            
            return True, sent_message.sid
            
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"Twilio message failed to {to_number}: {error_msg}")
            
            # Log failed message
            self._log_message(to_number, message, None, message_type, 'failed', error_msg)
            
            return False, error_msg
    
    def send_interactive_rsvp_message(self, class_id: str, student_id: str, 
                                    reminder_hours: int = 2) -> Tuple[bool, str]:
        """Send interactive RSVP message for class attendance"""
        try:
            # Get class and student details
            class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_data:
                return False, "Class not found"
            
            student_data = mongo.db.users.find_one({'_id': ObjectId(student_id)})
            if not student_data:
                return False, "Student not found"
            
            class_obj = Class.from_dict(class_data)
            student = User.from_dict(student_data)
            
            # Check if class is still in future
            if class_obj.scheduled_at <= datetime.utcnow():
                return False, "Class has already started"
            
            # Get or create attendance record
            attendance_data = mongo.db.attendance.find_one({
                'class_id': ObjectId(class_id),
                'student_id': ObjectId(student_id)
            })
            
            if attendance_data:
                attendance = Attendance.from_dict(attendance_data)
            else:
                attendance = Attendance(class_id, student_id, 'pending')
                result = mongo.db.attendance.insert_one(attendance.to_dict())
                attendance._id = result.inserted_id
            
            # Get coach information
            coach_data = mongo.db.users.find_one({'_id': class_obj.coach_id})
            coach_name = coach_data.get('name', 'Your coach') if coach_data else 'Your coach'
            
            # Create interactive message
            message = self._create_interactive_rsvp_message(
                student_name=student.name,
                class_obj=class_obj,
                coach_name=coach_name,
                attendance_id=str(attendance._id),
                hours_before=reminder_hours
            )
            
            # Send message
            success, message_id = self.send_twilio_message(
                to_number=student.phone_number,
                message=message,
                message_type='class_reminder'
            )
            
            if success:
                # Update attendance with message tracking
                mongo.db.attendance.update_one(
                    {'_id': attendance._id},
                    {
                        '$set': {
                            'reminder_sent_at': datetime.utcnow(),
                            'message_id': message_id,
                            'rsvp_deadline': class_obj.scheduled_at - timedelta(hours=1)
                        }
                    }
                )
                
                return True, f"RSVP message sent to {student.name}"
            else:
                return False, f"Failed to send message: {message_id}"
                
        except Exception as e:
            current_app.logger.error(f"Error sending interactive RSVP: {str(e)}")
            return False, str(e)
    
    def send_bulk_reminders(self, class_id: str, hours_before: int = 2) -> Tuple[bool, str, Dict]:
        """Send bulk reminders to all students in a class"""
        try:
            # Get class details
            class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_data:
                return False, "Class not found", {}
            
            class_obj = Class.from_dict(class_data)
            
            # Check if reminders already sent
            if class_obj.reminder_sent:
                return False, "Reminders already sent for this class", {}
            
            # Get all enrolled students
            enrolled_students = []
            
            # Direct enrollments
            if class_obj.student_ids:
                direct_students = mongo.db.users.find({
                    '_id': {'$in': class_obj.student_ids},
                    'is_active': True
                })
                enrolled_students.extend(list(direct_students))
            
            # Group enrollments
            if class_obj.group_ids:
                group_students = mongo.db.users.find({
                    'groups': {'$in': [str(gid) for gid in class_obj.group_ids]},
                    'is_active': True
                })
                enrolled_students.extend(list(group_students))
            
            # Remove duplicates
            unique_students = {str(s['_id']): s for s in enrolled_students}.values()
            
            results = {
                'total_students': len(unique_students),
                'successful': [],
                'failed': [],
                'skipped': []
            }
            
            for student_data in unique_students:
                student = User.from_dict(student_data)
                
                # Skip if no phone number
                if not student.phone_number:
                    results['skipped'].append({
                        'student_id': str(student._id),
                        'name': student.name,
                        'reason': 'No phone number'
                    })
                    continue
                
                # Send individual RSVP message
                success, message = self.send_interactive_rsvp_message(
                    class_id=class_id,
                    student_id=str(student._id),
                    reminder_hours=hours_before
                )
                
                if success:
                    results['successful'].append({
                        'student_id': str(student._id),
                        'name': student.name,
                        'phone': student.phone_number
                    })
                else:
                    results['failed'].append({
                        'student_id': str(student._id),
                        'name': student.name,
                        'error': message
                    })
            
            # Mark class as reminded
            if results['successful']:
                mongo.db.classes.update_one(
                    {'_id': ObjectId(class_id)},
                    {
                        '$set': {
                            'reminder_sent': True,
                            'reminder_sent_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
            
            success_count = len(results['successful'])
            total_attempted = success_count + len(results['failed'])
            
            return True, f"Sent {success_count}/{total_attempted} reminders successfully", results
            
        except Exception as e:
            current_app.logger.error(f"Error sending bulk reminders: {str(e)}")
            return False, str(e), {}
    
    def handle_rsvp_response(self, from_number: str, message_body: str, 
                           message_sid: str = None) -> Tuple[bool, str]:
        """Enhanced RSVP response handling with better pattern matching"""
        try:
            # Normalize phone number
            from_number = self._normalize_phone_number(from_number)
            message_body = message_body.lower().strip()
            
            # Find user by phone number
            user_data = mongo.db.users.find_one({'phone_number': from_number})
            if not user_data:
                return False, "User not found for this phone number"
            
            # Extract attendance ID if present
            attendance_id = self._extract_attendance_id(message_body)
            
            # Find pending attendance records
            query = {'student_id': ObjectId(user_data['_id'])}
            if attendance_id:
                query['_id'] = ObjectId(attendance_id)
            else:
                # Find most recent pending attendance
                query['status'] = 'pending'
                query['rsvp_deadline'] = {'$gte': datetime.utcnow()}
            
            attendance_data = mongo.db.attendance.find_one(query, sort=[('created_at', -1)])
            if not attendance_data:
                return False, "No pending class RSVP found"
            
            attendance = Attendance.from_dict(attendance_data)
            
            # Determine RSVP response
            rsvp_response = self._parse_rsvp_response(message_body)
            if not rsvp_response:
                # Send help message
                help_msg = self._create_rsvp_help_message()
                self.send_twilio_message(from_number, help_msg, message_type='help')
                return False, "Could not understand response. Help message sent."
            
            # Update attendance
            attendance.update_rsvp(rsvp_response, message_sid)
            mongo.db.attendance.update_one(
                {'_id': attendance._id},
                {'$set': attendance.to_dict()}
            )
            
            # Get class details for confirmation
            class_data = mongo.db.classes.find_one({'_id': attendance.class_id})
            class_obj = Class.from_dict(class_data) if class_data else None
            
            # Send confirmation
            confirmation_msg = self._create_enhanced_confirmation_message(
                rsvp_response, attendance, class_obj
            )
            self.send_twilio_message(from_number, confirmation_msg, message_type='confirmation')
            
            # Log the response
            self._log_rsvp_response(attendance._id, rsvp_response, message_body, from_number)
            
            return True, f"RSVP updated: {rsvp_response}"
            
        except Exception as e:
            current_app.logger.error(f"Error handling RSVP response: {str(e)}")
            return False, str(e)
    
    def send_payment_reminder(self, payment_id: str, urgency: str = 'normal') -> Tuple[bool, str]:
        """Send enhanced payment reminder with different urgency levels"""
        try:
            # Get payment details
            payment_data = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
            if not payment_data:
                return False, "Payment not found"
            
            payment = Payment.from_dict(payment_data)
            
            # Get student details
            student_data = mongo.db.users.find_one({'_id': payment.student_id})
            if not student_data:
                return False, "Student not found"
            
            student = User.from_dict(student_data)
            
            if not student.phone_number:
                return False, "Student has no phone number"
            
            # Create payment reminder message
            message = self._create_payment_reminder_message(payment, student, urgency)
            
            # Send message
            success, message_id = self.send_twilio_message(
                to_number=student.phone_number,
                message=message,
                message_type='payment_reminder'
            )
            
            if success:
                # Update payment with reminder tracking
                mongo.db.payments.update_one(
                    {'_id': payment._id},
                    {
                        '$push': {
                            'reminder_history': {
                                'sent_at': datetime.utcnow(),
                                'urgency': urgency,
                                'message_id': message_id
                            }
                        }
                    }
                )
                
                return True, f"Payment reminder sent to {student.name}"
            else:
                return False, f"Failed to send reminder: {message_id}"
                
        except Exception as e:
            current_app.logger.error(f"Error sending payment reminder: {str(e)}")
            return False, str(e)
    
    def send_welcome_message(self, user_id: str) -> Tuple[bool, str]:
        """Send welcome message to new users"""
        try:
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if not user_data:
                return False, "User not found"
            
            user = User.from_dict(user_data)
            
            if not user.phone_number:
                return False, "User has no phone number"
            
            # Get organization details
            org_data = mongo.db.organizations.find_one({'_id': user.organization_id})
            org_name = org_data.get('name', 'Our Organization') if org_data else 'Our Organization'
            
            # Create welcome message
            message = self._create_welcome_message(user, org_name)
            
            # Send message
            success, message_id = self.send_twilio_message(
                to_number=user.phone_number,
                message=message,
                message_type='welcome'
            )
            
            return success, message_id if success else f"Failed to send welcome message: {message_id}"
            
        except Exception as e:
            current_app.logger.error(f"Error sending welcome message: {str(e)}")
            return False, str(e)
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format"""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d\+]', '', phone_number)
        
        # Add + if missing
        if not cleaned.startswith('+'):
            if len(cleaned) == 10:  # US format
                cleaned = '+1' + cleaned
            elif len(cleaned) == 11 and cleaned.startswith('1'):  # US with country code
                cleaned = '+' + cleaned
            else:
                cleaned = '+' + cleaned
        
        return cleaned
    
    def _parse_rsvp_response(self, message_body: str) -> Optional[str]:
        """Parse RSVP response from message body using enhanced pattern matching"""
        message_lower = message_body.lower()
        
        for response_type, patterns in self.rsvp_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return response_type
        
        return None
    
    def _extract_attendance_id(self, message_body: str) -> Optional[str]:
        """Extract attendance ID from message body"""
        # Look for attendance ID pattern
        match = re.search(r'attendance[:\s]*([a-f0-9]{24})', message_body, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _create_interactive_rsvp_message(self, student_name: str, class_obj: Class, 
                                       coach_name: str, attendance_id: str, 
                                       hours_before: int) -> str:
        """Create enhanced interactive RSVP message"""
        date_str = class_obj.scheduled_at.strftime('%B %d, %Y')
        time_str = class_obj.scheduled_at.strftime('%I:%M %p')
        location_str = class_obj.location.get('name', 'TBD') if class_obj.location else 'TBD'
        
        # Calculate time until class
        time_until = class_obj.scheduled_at - datetime.utcnow()
        hours_until = int(time_until.total_seconds() / 3600)
        
        urgency_emoji = "🔔" if hours_until > 24 else "⏰" if hours_until > 2 else "🚨"
        
        message = f"""
{urgency_emoji} *Class Reminder*

Hi {student_name}! 👋

Your upcoming {class_obj.title} class:

📅 *Date:* {date_str}
⏰ *Time:* {time_str}
📍 *Location:* {location_str}
👨‍🏫 *Coach:* {coach_name}

⏳ *Starting in {hours_until} hours*

*Please confirm your attendance:*
• Reply *YES* ✅ - I'll be there!
• Reply *NO* ❌ - Can't make it
• Reply *MAYBE* ⏳ - Will try to attend

_Quick responses: ✅ 👍 ❌ 👎 🤔_

*Attendance ID:* {attendance_id}

💪 We're excited to see you in class!
        """.strip()
        
        return message
    
    def _create_enhanced_confirmation_message(self, response: str, attendance: Attendance, 
                                            class_obj: Class = None) -> str:
        """Create enhanced confirmation message"""
        emojis = {
            'yes': '✅ 🎉',
            'no': '❌ 😔',
            'maybe': '⏳ 🤔'
        }
        
        confirmations = {
            'yes': f"{emojis['yes']} Awesome! Your attendance is confirmed. We can't wait to see you in class!",
            'no': f"{emojis['no']} Thanks for letting us know. Your absence has been recorded. Hope to see you next time!",
            'maybe': f"{emojis['maybe']} Noted! Please try to confirm closer to class time. We'll save your spot!"
        }
        
        base_message = confirmations.get(response, "Thank you for your response!")
        
        if class_obj and response == 'yes':
            # Add helpful info for confirmed attendees
            base_message += f"\n\n💡 *Quick Tips:*\n• Arrive 10 minutes early\n• Bring water and a towel\n• Let us know if you're running late"
        
        return base_message
    
    def _create_payment_reminder_message(self, payment: Payment, student: User, 
                                       urgency: str) -> str:
        """Create payment reminder message with urgency levels"""
        amount = payment.get_total_amount()
        due_date = payment.due_date.strftime('%B %d, %Y')
        days_overdue = payment.get_days_overdue()
        
        if urgency == 'gentle':
            emoji = "🔔"
            tone = "friendly reminder"
        elif urgency == 'urgent':
            emoji = "⚠️"
            tone = "urgent notice"
        elif urgency == 'final':
            emoji = "🚨"
            tone = "final notice"
        else:  # normal
            emoji = "💳"
            tone = "payment reminder"
        
        message = f"""
{emoji} *Payment {tone.title()}*

Hi {student.name}!

{tone.capitalize()} about your payment:

💰 *Amount:* ₹{amount:.2f}
📅 *Due Date:* {due_date}
📝 *Description:* {payment.description}
        """
        
        if days_overdue > 0:
            message += f"\n🚨 *Overdue by {days_overdue} days*"
            if payment.late_fee > 0:
                message += f"\n💸 *Late Fee:* ₹{payment.late_fee:.2f}"
        
        message += f"""

Please make your payment at your earliest convenience. Contact our admin team if you have any questions.

Thank you! 🙏
        """.strip()
        
        return message
    
    def _create_welcome_message(self, user: User, org_name: str) -> str:
        """Create welcome message for new users"""
        message = f"""
🎉 *Welcome to {org_name}!* 

Hi {user.name}! 👋

We're excited to have you join our community! Here's what you can expect:

📱 *WhatsApp Updates:*
• Class reminders and confirmations
• Payment notifications
• Important announcements
• Progress updates

✅ *Getting Started:*
• Check your class schedule
• Complete your profile
• Set up payment methods
• Join our community feed

💬 *Need Help?*
Just reply to any message and our team will assist you!

Welcome aboard! 🚀
        """.strip()
        
        return message
    
    def _create_rsvp_help_message(self) -> str:
        """Create help message for RSVP responses"""
        return """
🤔 *Not sure how to respond?*

To confirm your class attendance, simply reply with:

✅ *For YES:*
• "YES" or "yes" 
• "Confirm" or "attending"
• "Coming" or ✅ emoji

❌ *For NO:*
• "NO" or "no"
• "Cancel" or "skip"
• "Can't make it" or ❌ emoji

⏳ *For MAYBE:*
• "Maybe" or "unsure"
• "Tentative" or 🤔 emoji

That's it! We'll confirm your response right away. 😊
        """.strip()
    
    def _log_message(self, to_number: str, message: str, message_id: str, 
                    message_type: str, status: str, error: str = None):
        """Log message for tracking and analytics"""
        try:
            log_entry = {
                'to_number': to_number,
                'message_preview': message[:100] + '...' if len(message) > 100 else message,
                'message_id': message_id,
                'message_type': message_type,
                'status': status,
                'error': error,
                'timestamp': datetime.utcnow()
            }
            
            mongo.db.whatsapp_logs.insert_one(log_entry)
            
        except Exception as e:
            current_app.logger.error(f"Error logging WhatsApp message: {str(e)}")
    
    def _log_rsvp_response(self, attendance_id: ObjectId, response: str, 
                          original_message: str, from_number: str):
        """Log RSVP response for analytics"""
        try:
            log_entry = {
                'attendance_id': attendance_id,
                'response': response,
                'original_message': original_message,
                'from_number': from_number,
                'timestamp': datetime.utcnow()
            }
            
            mongo.db.rsvp_logs.insert_one(log_entry)
            
        except Exception as e:
            current_app.logger.error(f"Error logging RSVP response: {str(e)}")
    
    def get_messaging_analytics(self, organization_id: str, days: int = 30) -> Dict:
        """Get WhatsApp messaging analytics for organization"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get user phone numbers for this organization
            org_users = mongo.db.users.find({
                'organization_id': ObjectId(organization_id)
            }, {'phone_number': 1})
            
            phone_numbers = [user['phone_number'] for user in org_users if user.get('phone_number')]
            
            # Message statistics
            message_stats = list(mongo.db.whatsapp_logs.aggregate([
                {
                    '$match': {
                        'to_number': {'$in': phone_numbers},
                        'timestamp': {'$gte': start_date}
                    }
                },
                {
                    '$group': {
                        '_id': '$message_type',
                        'total': {'$sum': 1},
                        'successful': {'$sum': {'$cond': [{'$eq': ['$status', 'sent']}, 1, 0]}},
                        'failed': {'$sum': {'$cond': [{'$eq': ['$status', 'failed']}, 1, 0]}}
                    }
                }
            ]))
            
            # RSVP statistics
            rsvp_stats = list(mongo.db.rsvp_logs.aggregate([
                {
                    '$match': {
                        'from_number': {'$in': phone_numbers},
                        'timestamp': {'$gte': start_date}
                    }
                },
                {
                    '$group': {
                        '_id': '$response',
                        'count': {'$sum': 1}
                    }
                }
            ]))
            
            return {
                'period_days': days,
                'message_stats': message_stats,
                'rsvp_stats': rsvp_stats,
                'total_users': len(phone_numbers)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting messaging analytics: {str(e)}")
            return {}
    
    # Legacy method compatibility
    def send_message(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Legacy compatibility method"""
        return self.send_twilio_message(phone_number, message)
