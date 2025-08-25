import os
import requests
from datetime import datetime
from twilio.rest import Client
from app.extensions import mongo
from app.models.class_schedule import Class
from app.models.attendance import Attendance
from app.models.user import User
from bson import ObjectId

class WhatsAppService:
    """Service for WhatsApp messaging integration"""
    
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
    
    def send_twilio_message(self, to_number, message, media_url=None):
        """Send WhatsApp message via Twilio"""
        if not self.twilio_client:
            return False, "Twilio not configured"
        
        try:
            message_data = {
                'from_': os.getenv('TWILIO_WHATSAPP_FROM'),
                'body': message,
                'to': f'whatsapp:{to_number}'
            }
            
            if media_url:
                message_data['media_url'] = [media_url]
            
            message = self.twilio_client.messages.create(**message_data)
            return True, message.sid
        except Exception as e:
            return False, str(e)
    
    def send_interakt_message(self, to_number, message, template_name=None, parameters=None):
        """Send WhatsApp message via Interakt"""
        if not self.interakt_api_key:
            return False, "Interakt not configured"
        
        try:
            headers = {
                'Authorization': f'Bearer {self.interakt_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': to_number,
                'type': 'text',
                'message': message
            }
            
            if template_name:
                payload.update({
                    'type': 'template',
                    'template': {
                        'name': template_name,
                        'parameters': parameters or []
                    }
                })
            
            response = requests.post(
                f'{self.interakt_base_url}/v1/messages',
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                return True, response.json().get('messageId')
            else:
                return False, response.text
        except Exception as e:
            return False, str(e)
    
    def send_class_reminder(self, class_id, hours_before=2):
        """Send class reminder to all students"""
        try:
            # Get class details
            class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_data:
                return False, "Class not found"
            
            class_obj = Class.from_dict(class_data)
            
            # Get coach details
            coach_data = mongo.db.users.find_one({'_id': class_obj.coach_id})
            coach_name = coach_data['name'] if coach_data else 'Coach'
            
            # Get all students for this class
            student_ids = class_obj.student_ids.copy()
            
            # Add students from groups
            if class_obj.group_ids:
                group_students = mongo.db.users.find({
                    'groups': {'$in': [str(gid) for gid in class_obj.group_ids]},
                    'role': 'student'
                })
                for student in group_students:
                    student_id = ObjectId(student['_id'])
                    if student_id not in student_ids:
                        student_ids.append(student_id)
            
            # Send reminders to each student
            sent_count = 0
            webhook_url = f"{os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')}/api/webhooks/whatsapp"
            
            for student_id in student_ids:
                student_data = mongo.db.users.find_one({'_id': student_id})
                if not student_data:
                    continue
                
                student = User.from_dict(student_data)
                
                # Create or update attendance record
                attendance_data = mongo.db.attendance.find_one({
                    'class_id': class_obj._id,
                    'student_id': student_id
                })
                
                if not attendance_data:
                    # Create new attendance record
                    attendance = Attendance(
                        class_id=str(class_obj._id),
                        student_id=str(student_id),
                        status='pending'
                    )
                    result = mongo.db.attendance.insert_one(attendance.to_dict())
                    attendance._id = result.inserted_id
                else:
                    attendance = Attendance.from_dict(attendance_data)
                
                # Prepare reminder message
                message = self._create_reminder_message(
                    student.name,
                    class_obj,
                    coach_name,
                    str(attendance._id)
                )
                
                # Send message
                success, message_id = self.send_message(student.phone_number, message)
                
                if success:
                    # Update attendance with message ID
                    mongo.db.attendance.update_one(
                        {'_id': attendance._id},
                        {'$set': {
                            'whatsapp_message_id': message_id,
                            'updated_at': datetime.utcnow()
                        }}
                    )
                    sent_count += 1
            
            # Mark class as reminder sent
            mongo.db.classes.update_one(
                {'_id': class_obj._id},
                {'$set': {'reminder_sent': True, 'updated_at': datetime.utcnow()}}
            )
            
            return True, f"Sent {sent_count} reminders"
        
        except Exception as e:
            return False, str(e)
    
    def send_message(self, phone_number, message):
        """Send WhatsApp message using available service"""
        # Try Twilio first
        if self.twilio_client:
            return self.send_twilio_message(phone_number, message)
        
        # Try Interakt as fallback
        if self.interakt_api_key:
            return self.send_interakt_message(phone_number, message)
        
        # No service available - log to console for development
        print(f"WhatsApp Message to {phone_number}: {message}")
        return True, "dev_message_id"
    
    def _create_reminder_message(self, student_name, class_obj, coach_name, attendance_id):
        """Create reminder message with RSVP buttons"""
        date_str = class_obj.scheduled_at.strftime('%B %d, %Y')
        time_str = class_obj.scheduled_at.strftime('%I:%M %p')
        location_str = class_obj.location.get('name', 'TBD') if class_obj.location else 'TBD'
        
        message = f"""
🏃‍♂️ *Class Reminder*

Hi {student_name}!

You have a {class_obj.title} class scheduled:

📅 *Date:* {date_str}
⏰ *Time:* {time_str}
📍 *Location:* {location_str}
👨‍🏫 *Coach:* {coach_name}

Please confirm your attendance:

✅ Reply "YES" to confirm
❌ Reply "NO" if you can't make it
⏳ Reply "MAYBE" if you're unsure

*Attendance ID:* {attendance_id}
        """.strip()
        
        return message
    
    def handle_webhook_response(self, message_data):
        """Handle incoming WhatsApp webhook responses"""
        try:
            # Extract message details (format depends on provider)
            from_number = message_data.get('From', '').replace('whatsapp:', '')
            message_body = message_data.get('Body', '').strip().upper()
            message_id = message_data.get('MessageSid', message_data.get('messageId'))
            
            # Look for attendance ID in recent messages
            # This is a simplified approach - in production, you'd track conversations better
            attendance_record = mongo.db.attendance.find_one({
                'whatsapp_message_id': {'$exists': True}
            }, sort=[('created_at', -1)])
            
            if not attendance_record:
                return False, "No attendance record found"
            
            # Find user by phone number
            user_data = mongo.db.users.find_one({'phone_number': from_number})
            if not user_data:
                return False, "User not found"
            
            # Find matching attendance record
            attendance_data = mongo.db.attendance.find_one({
                'student_id': user_data['_id'],
                'whatsapp_message_id': {'$exists': True}
            }, sort=[('created_at', -1)])
            
            if not attendance_data:
                return False, "No matching attendance record"
            
            attendance = Attendance.from_dict(attendance_data)
            
            # Process response
            response = None
            if message_body in ['YES', 'Y', '1', 'CONFIRM', 'ATTENDING']:
                response = 'yes'
            elif message_body in ['NO', 'N', '0', 'CANCEL', 'NOT ATTENDING']:
                response = 'no'
            elif message_body in ['MAYBE', 'M', 'UNSURE', 'UNCERTAIN']:
                response = 'maybe'
            
            if response:
                # Update attendance
                attendance.update_rsvp(response, message_id)
                mongo.db.attendance.update_one(
                    {'_id': attendance._id},
                    {'$set': attendance.to_dict()}
                )
                
                # Send confirmation message
                confirmation_msg = self._create_confirmation_message(response, attendance_data)
                self.send_message(from_number, confirmation_msg)
                
                return True, f"RSVP updated: {response}"
            else:
                return False, "Invalid response format"
        
        except Exception as e:
            return False, str(e)
    
    def _create_confirmation_message(self, response, attendance_data):
        """Create confirmation message for RSVP response"""
        confirmations = {
            'yes': "✅ Great! Your attendance has been confirmed. See you in class! 🏃‍♂️",
            'no': "❌ Thanks for letting us know. Your absence has been recorded. 📝",
            'maybe': "⏳ Noted! Please try to confirm closer to class time. 🤔"
        }
        
        return confirmations.get(response, "Thank you for your response!")
    
    def send_payment_reminder(self, student_id, payment_details):
        """Send payment reminder"""
        try:
            student_data = mongo.db.users.find_one({'_id': ObjectId(student_id)})
            if not student_data:
                return False, "Student not found"
            
            student = User.from_dict(student_data)
            
            message = f"""
💳 *Payment Reminder*

Hi {student.name}!

You have a pending payment:

📋 *Description:* {payment_details['description']}
💰 *Amount:* ₹{payment_details['amount']}
📅 *Due Date:* {payment_details['due_date'].strftime('%B %d, %Y')}

Please make the payment at your earliest convenience.

For any queries, contact your coach or admin.
            """.strip()
            
            return self.send_message(student.phone_number, message)
        
        except Exception as e:
            return False, str(e) 