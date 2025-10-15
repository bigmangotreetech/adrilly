from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from app.services.whatsapp_verification_service import WhatsAppVerificationService
from app.utils.auth import jwt_required, get_current_user
from app.extensions import mongo

whatsapp_verification_bp = Blueprint('whatsapp_verification', __name__, url_prefix='/api/whatsapp-verification')
whatsapp_verification_service = WhatsAppVerificationService()

@whatsapp_verification_bp.route('/send-code', methods=['POST'])
def send_verification_code():
    """Send WhatsApp verification code"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
            
        # Check if WhatsApp verification is enabled
        if not current_app.config.get('WHATSAPP_VERIFICATION_ENABLED'):
            return jsonify({'error': 'WhatsApp verification is not enabled'}), 400
            
        # Send verification code
        success, message, code = whatsapp_verification_service.send_verification_code(phone_number)
        
        if success:
            return jsonify({
                'message': message,
                'expires_in': current_app.config.get('VERIFICATION_CODE_EXPIRY')
            }), 200
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error sending verification code: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@whatsapp_verification_bp.route('/verify-code', methods=['POST'])
def verify_code():
    """Verify WhatsApp verification code"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        code = data.get('code')
        
        if not phone_number or not code:
            return jsonify({'error': 'Phone number and code are required'}), 400
            
        # Verify code
        success, message = whatsapp_verification_service.verify_code(phone_number, code)
        
        if success:
            # Update user's phone verification status
            mongo.db.users.update_one(
                {'phone_number': phone_number},
                {
                    '$set': {
                        'phone_verified': True,
                        'phone_verified_at': datetime.utcnow()
                    }
                }
            )
            
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error verifying code: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@whatsapp_verification_bp.route('/status', methods=['GET'])
@jwt_required
def verification_status():
    """Get verification status for current user"""
    try:
        current_user = get_current_user()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
            
        status = whatsapp_verification_service.get_verification_status(current_user['phone_number'])
        return jsonify(status), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting verification status: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
        
def register_whatsapp_verification_blueprint(app):
    """Register the WhatsApp verification blueprint"""
    app.register_blueprint(whatsapp_verification_bp)
