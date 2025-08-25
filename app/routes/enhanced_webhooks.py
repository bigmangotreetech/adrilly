from flask import Blueprint, request, jsonify, current_app
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from app.models.user import User
from app.extensions import mongo
from datetime import datetime
import hmac
import hashlib
import os

enhanced_webhooks_bp = Blueprint('enhanced_webhooks', __name__, url_prefix='/api/webhooks')

@enhanced_webhooks_bp.route('/twilio-whatsapp', methods=['POST'])
def handle_twilio_whatsapp_webhook():
    """Enhanced Twilio WhatsApp webhook handler with better security and features"""
    try:
        # Verify webhook signature for security
        if not _verify_twilio_signature(request):
            current_app.logger.warning("Invalid Twilio webhook signature")
            return jsonify({'error': 'Invalid signature'}), 403
        
        # Get webhook data
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        to_number = request.form.get('To', '').replace('whatsapp:', '')
        message_body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        
        # Log incoming webhook
        current_app.logger.info(f"WhatsApp webhook: {from_number} -> {to_number}: {message_body[:50]}...")
        
        whatsapp_service = EnhancedWhatsAppService()
        
        # Handle different types of webhook events
        if message_status:
            # This is a status callback (delivery receipt)
            return _handle_message_status_update(message_sid, message_status)
        
        elif message_body:
            # This is an incoming message
            return _handle_incoming_message(from_number, message_body, message_sid, whatsapp_service)
        
        else:
            current_app.logger.warning("Unknown webhook event type")
            return jsonify({'status': 'ignored'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error handling WhatsApp webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_webhooks_bp.route('/whatsapp-analytics/<organization_id>', methods=['GET'])
def get_whatsapp_analytics(organization_id):
    """Get WhatsApp messaging analytics for organization"""
    try:
        days = request.args.get('days', 30, type=int)
        
        whatsapp_service = EnhancedWhatsAppService()
        analytics = whatsapp_service.get_messaging_analytics(organization_id, days)
        
        return jsonify({
            'organization_id': organization_id,
            'analytics': analytics
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting WhatsApp analytics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_webhooks_bp.route('/test-whatsapp', methods=['POST'])
def test_whatsapp_message():
    """Test endpoint for WhatsApp message sending (development only)"""
    if not current_app.debug:
        return jsonify({'error': 'Test endpoint only available in debug mode'}), 403
    
    try:
        data = request.json
        phone_number = data.get('phone_number')
        message = data.get('message')
        message_type = data.get('type', 'test')
        
        if not phone_number or not message:
            return jsonify({'error': 'phone_number and message are required'}), 400
        
        whatsapp_service = EnhancedWhatsAppService()
        success, result = whatsapp_service.send_twilio_message(phone_number, message, message_type=message_type)
        
        return jsonify({
            'success': success,
            'result': result
        }), 200 if success else 400
        
    except Exception as e:
        current_app.logger.error(f"Error in test WhatsApp: {str(e)}")
        return jsonify({'error': str(e)}), 500

@enhanced_webhooks_bp.route('/send-class-reminders/<class_id>', methods=['POST'])
def send_class_reminders(class_id):
    """Endpoint to trigger class reminders"""
    try:
        hours_before = request.json.get('hours_before', 2)
        
        whatsapp_service = EnhancedWhatsAppService()
        success, message, results = whatsapp_service.send_bulk_reminders(class_id, hours_before)
        
        if success:
            return jsonify({
                'message': message,
                'results': results
            }), 200
        else:
            return jsonify({
                'error': message,
                'results': results
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Error sending class reminders: {str(e)}")
        return jsonify({'error': str(e)}), 500

@enhanced_webhooks_bp.route('/send-payment-reminder/<payment_id>', methods=['POST'])
def send_payment_reminder(payment_id):
    """Endpoint to send payment reminder"""
    try:
        urgency = request.json.get('urgency', 'normal')
        
        whatsapp_service = EnhancedWhatsAppService()
        success, message = whatsapp_service.send_payment_reminder(payment_id, urgency)
        
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error sending payment reminder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@enhanced_webhooks_bp.route('/send-welcome-message/<user_id>', methods=['POST'])
def send_welcome_message(user_id):
    """Endpoint to send welcome message to new user"""
    try:
        whatsapp_service = EnhancedWhatsAppService()
        success, message = whatsapp_service.send_welcome_message(user_id)
        
        if success:
            return jsonify({'message': 'Welcome message sent', 'message_id': message}), 200
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error sending welcome message: {str(e)}")
        return jsonify({'error': str(e)}), 500

def _verify_twilio_signature(request) -> bool:
    """Verify Twilio webhook signature for security"""
    try:
        # Get signature from headers
        signature = request.headers.get('X-Twilio-Signature', '')
        
        # Skip verification in development if no auth token
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if not auth_token:
            current_app.logger.warning("Twilio auth token not configured - skipping signature verification")
            return True
        
        # Build URL
        url = request.url
        
        # Get POST data
        post_data = request.form.to_dict()
        
        # Create expected signature
        validator = hmac.new(
            auth_token.encode('utf-8'),
            msg=(url + ''.join(f'{k}{v}' for k, v in sorted(post_data.items()))).encode('utf-8'),
            digestmod=hashlib.sha1
        )
        
        expected_signature = validator.digest().hex()
        
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        current_app.logger.error(f"Error verifying Twilio signature: {str(e)}")
        return False

def _handle_message_status_update(message_sid: str, status: str) -> tuple:
    """Handle message delivery status updates"""
    try:
        # Update message status in logs
        mongo.db.whatsapp_logs.update_one(
            {'message_id': message_sid},
            {
                '$set': {
                    'delivery_status': status,
                    'status_updated_at': datetime.utcnow()
                }
            }
        )
        
        # Handle failed messages
        if status in ['failed', 'undelivered']:
            current_app.logger.warning(f"WhatsApp message {message_sid} failed with status: {status}")
            
            # Could implement retry logic here
            # _schedule_message_retry(message_sid)
        
        return jsonify({'status': 'processed'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error handling message status update: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def _handle_incoming_message(from_number: str, message_body: str, message_sid: str, 
                           whatsapp_service: EnhancedWhatsAppService) -> tuple:
    """Handle incoming WhatsApp messages"""
    try:
        # Log incoming message
        mongo.db.whatsapp_logs.insert_one({
            'from_number': from_number,
            'message_body': message_body,
            'message_sid': message_sid,
            'direction': 'incoming',
            'timestamp': datetime.utcnow()
        })
        
        # Check if this is an RSVP response
        if _is_rsvp_response(message_body):
            success, response = whatsapp_service.handle_rsvp_response(from_number, message_body, message_sid)
            
            if success:
                current_app.logger.info(f"RSVP processed: {from_number} -> {response}")
            else:
                current_app.logger.warning(f"RSVP processing failed: {response}")
            
            return jsonify({'status': 'rsvp_processed', 'result': response}), 200
        
        # Check if this is a help request
        elif _is_help_request(message_body):
            return _handle_help_request(from_number, whatsapp_service)
        
        # Check if this is a general query
        elif _is_general_query(message_body):
            return _handle_general_query(from_number, message_body, whatsapp_service)
        
        else:
            # Unknown message type - send generic help
            help_message = """
🤖 *Automated Response*

Thanks for your message! I'm an automated system that handles:

• Class attendance confirmations (YES/NO/MAYBE)
• Payment reminders
• Class notifications

For general inquiries, please contact our admin team directly.

Need help with attendance? Reply with 'HELP' for instructions.
            """.strip()
            
            whatsapp_service.send_twilio_message(from_number, help_message, message_type='auto_response')
            
            return jsonify({'status': 'auto_response_sent'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error handling incoming message: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def _is_rsvp_response(message_body: str) -> bool:
    """Check if message is an RSVP response"""
    rsvp_keywords = [
        'yes', 'no', 'maybe', 'confirm', 'cancel', 'attend', 'skip', 'coming', 'can\'t',
        'attendance', '✅', '❌', '⏳', '👍', '👎', '🤔'
    ]
    
    message_lower = message_body.lower()
    return any(keyword in message_lower for keyword in rsvp_keywords)

def _is_help_request(message_body: str) -> bool:
    """Check if message is a help request"""
    help_keywords = ['help', 'how', 'what', 'instructions', 'guide', '?']
    message_lower = message_body.lower()
    return any(keyword in message_lower for keyword in help_keywords)

def _is_general_query(message_body: str) -> bool:
    """Check if message is a general query"""
    query_keywords = ['when', 'where', 'who', 'schedule', 'payment', 'class', 'timing']
    message_lower = message_body.lower()
    return any(keyword in message_lower for keyword in query_keywords)

def _handle_help_request(from_number: str, whatsapp_service: EnhancedWhatsAppService) -> tuple:
    """Handle help requests"""
    help_message = """
🆘 *Help & Instructions*

Here's what I can help you with:

📅 *Class Attendance:*
• Reply "YES" to confirm attendance
• Reply "NO" if you can't attend  
• Reply "MAYBE" if unsure

💳 *Payments:*
• I'll send payment reminders
• Contact admin for payment issues

📞 *Need Human Help?*
Call our admin team or visit the center for personal assistance.

🤖 *About Me:*
I'm an automated assistant for quick responses. For complex queries, please contact our staff directly.
    """.strip()
    
    whatsapp_service.send_twilio_message(from_number, help_message, message_type='help_response')
    return jsonify({'status': 'help_sent'}), 200

def _handle_general_query(from_number: str, message_body: str, 
                         whatsapp_service: EnhancedWhatsAppService) -> tuple:
    """Handle general queries with basic auto-responses"""
    
    message_lower = message_body.lower()
    
    if 'schedule' in message_lower or 'timing' in message_lower:
        response = """
📅 *Class Schedule Information*

For your current class schedule:
• Check the mobile app
• Log into the web portal
• Contact our admin team

⏰ You'll receive automatic reminders 2 hours before each class!
        """.strip()
    
    elif 'payment' in message_lower:
        response = """
💳 *Payment Information*

For payment-related queries:
• Check your payment status in the app
• Contact our admin team for assistance
• Payment reminders are sent automatically

📞 Need immediate help? Call our office directly.
        """.strip()
    
    elif 'where' in message_lower or 'location' in message_lower:
        response = """
📍 *Location Information*

Class locations are included in your reminders. For general location info:
• Check the app for detailed directions
• Contact admin for specific directions
• Look for location details in class confirmations

🗺️ Need help finding us? Our admin team can assist!
        """.strip()
    
    else:
        response = """
🤖 *General Information*

Thanks for your message! For detailed assistance:
• Check our mobile app or web portal
• Contact our admin team directly
• Call our office during business hours

I'll automatically notify you about classes and payments!
        """.strip()
    
    whatsapp_service.send_twilio_message(from_number, response, message_type='auto_response')
    return jsonify({'status': 'auto_response_sent'}), 200
