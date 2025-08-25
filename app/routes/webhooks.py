from flask import Blueprint, request, jsonify
from app.services.whatsapp_service import WhatsAppService

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

@webhooks_bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Get the message data from the webhook
        message_data = request.json or request.form.to_dict()
        
        if not message_data:
            return jsonify({'error': 'No data received'}), 400
        
        # Initialize WhatsApp service
        whatsapp_service = WhatsAppService()
        
        # Handle the webhook response
        success, message = whatsapp_service.handle_webhook_response(message_data)
        
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@webhooks_bp.route('/whatsapp', methods=['GET'])
def whatsapp_webhook_verify():
    """Verify WhatsApp webhook (for Twilio/Meta verification)"""
    try:
        # For Twilio webhook verification
        hub_mode = request.args.get('hub.mode')
        hub_challenge = request.args.get('hub.challenge')
        hub_verify_token = request.args.get('hub.verify_token')
        
        # You should set a webhook verification token in your environment
        WEBHOOK_VERIFY_TOKEN = "your_webhook_verify_token"
        
        if hub_mode == 'subscribe' and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
            return hub_challenge, 200
        else:
            return 'Verification failed', 403
    
    except Exception as e:
        return 'Verification error', 500

@webhooks_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test webhook endpoint for development"""
    try:
        data = request.json
        print(f"Test webhook received: {data}")
        return jsonify({'message': 'Test webhook received', 'data': data}), 200
    
    except Exception as e:
        return jsonify({'error': 'Test webhook failed'}), 500 