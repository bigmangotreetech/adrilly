from flask import Blueprint, request, jsonify, render_template, session
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.services.security_service import security_service
from app.routes.auth import require_role
from app.routes.web import login_required, role_required
from marshmallow import Schema, fields, ValidationError
from datetime import datetime

security_bp = Blueprint('security', __name__, url_prefix='/api/security')

# Web interface blueprint
security_web_bp = Blueprint('security_web', __name__)

@security_bp.route('/validate-password', methods=['POST'])
def validate_password():
    """Validate password strength"""
    try:
        data = request.json
        password = data.get('password')
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        is_valid, errors = security_service.validate_password_strength(password)
        
        return jsonify({
            'valid': is_valid,
            'errors': errors,
            'strength_score': len([e for e in errors if not e]) if is_valid else 0
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/generate-password', methods=['POST'])
def generate_secure_password():
    """Generate a secure password"""
    try:
        data = request.json or {}
        length = data.get('length', 12)
        
        if length < 8 or length > 128:
            return jsonify({'error': 'Password length must be between 8 and 128 characters'}), 400
        
        password = security_service.generate_secure_password(length)
        
        return jsonify({
            'password': password,
            'length': len(password)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/check-account-status/<identifier>', methods=['GET'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def check_account_status(identifier):
    """Check if account is locked or has security issues"""
    try:
        is_locked, lockout_until = security_service.check_account_lockout(identifier)
        
        return jsonify({
            'identifier': identifier,
            'is_locked': is_locked,
            'lockout_until': lockout_until,
            'status': 'locked' if is_locked else 'active'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/unlock-account', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def unlock_account():
    """Manually unlock a locked account"""
    try:
        data = request.json
        identifier = data.get('identifier')
        reason = data.get('reason', 'Manual unlock by admin')
        
        if not identifier:
            return jsonify({'error': 'Identifier is required'}), 400
        
        # Remove lockout
        from app.extensions import mongo
        result = mongo.db.account_lockouts.delete_one({'identifier': identifier})
        
        # Log security event
        security_service.log_security_event('account_unlocked', {
            'identifier': identifier,
            'reason': reason,
            'unlocked_by': get_jwt_identity()
        })
        
        return jsonify({
            'message': f'Account {identifier} has been unlocked',
            'removed_lockout': result.deleted_count > 0
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/rate-limit-status/<identifier>', methods=['GET'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def check_rate_limit_status(identifier):
    """Check rate limit status for an identifier"""
    try:
        limit_type = request.args.get('type', 'api')
        
        allowed, remaining = security_service.check_rate_limit(identifier, limit_type)
        
        return jsonify({
            'identifier': identifier,
            'limit_type': limit_type,
            'allowed': allowed,
            'remaining_requests': remaining
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/validate-email', methods=['POST'])
def validate_email():
    """Validate email with security checks"""
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        is_valid, errors = security_service.validate_email_security(email)
        
        return jsonify({
            'valid': is_valid,
            'errors': errors,
            'email': email
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/sanitize-input', methods=['POST'])
def sanitize_input():
    """Sanitize user input"""
    try:
        data = request.json
        input_data = data.get('input')
        input_type = data.get('type', 'text')
        
        if input_data is None:
            return jsonify({'error': 'Input data is required'}), 400
        
        sanitized = security_service.sanitize_input(input_data, input_type)
        
        return jsonify({
            'original': input_data,
            'sanitized': sanitized,
            'type': input_type
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/generate-token', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def generate_secure_token():
    """Generate secure token for specific purpose"""
    try:
        data = request.json
        purpose = data.get('purpose')
        user_id = data.get('user_id')
        expires_in = data.get('expires_in', 3600)
        
        if not purpose:
            return jsonify({'error': 'Purpose is required'}), 400
        
        token, token_id = security_service.generate_secure_token(
            purpose, user_id, expires_in
        )
        
        return jsonify({
            'token': token,
            'token_id': token_id,
            'purpose': purpose,
            'expires_in': expires_in
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/verify-token', methods=['POST'])
def verify_secure_token():
    """Verify secure token"""
    try:
        data = request.json
        token = data.get('token')
        purpose = data.get('purpose')
        
        if not token or not purpose:
            return jsonify({'error': 'Token and purpose are required'}), 400
        
        is_valid, payload = security_service.verify_secure_token(token, purpose)
        
        return jsonify({
            'valid': is_valid,
            'payload': payload if is_valid else None
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/revoke-token', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def revoke_secure_token():
    """Revoke a security token"""
    try:
        data = request.json
        token_id = data.get('token_id')
        
        if not token_id:
            return jsonify({'error': 'Token ID is required'}), 400
        
        security_service.revoke_token(token_id)
        
        # Log security event
        security_service.log_security_event('token_revoked', {
            'token_id': token_id,
            'revoked_by': get_jwt_identity()
        })
        
        return jsonify({
            'message': 'Token has been revoked',
            'token_id': token_id
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/security-report', methods=['GET'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def get_security_report():
    """Get comprehensive security report"""
    try:
        days = request.args.get('days', 7, type=int)
        
        report = security_service.get_security_report(days)
        
        return jsonify(report), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/log-security-event', methods=['POST'])
@jwt_required()
def log_security_event():
    """Log a security event"""
    try:
        data = request.json
        event_type = data.get('event_type')
        details = data.get('details', {})
        
        if not event_type:
            return jsonify({'error': 'Event type is required'}), 400
        
        security_service.log_security_event(event_type, details)
        
        return jsonify({
            'message': 'Security event logged',
            'event_type': event_type
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/cleanup-expired', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def cleanup_expired_data():
    """Clean up expired security data"""
    try:
        data = request.json or {}
        days_to_keep = data.get('days_to_keep', 30)
        
        # Clean up expired tokens
        expired_tokens = security_service.cleanup_expired_tokens()
        
        # Clean up old login attempts
        old_attempts = security_service.cleanup_old_login_attempts(days_to_keep)
        
        return jsonify({
            'message': 'Cleanup completed',
            'expired_tokens_removed': expired_tokens,
            'old_login_attempts_removed': old_attempts
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/ip-validation', methods=['POST'])
def validate_ip_address():
    """Validate IP address against trusted ranges"""
    try:
        data = request.json
        ip_address = data.get('ip_address') or request.remote_addr
        
        is_trusted = security_service.validate_ip_address(ip_address)
        
        return jsonify({
            'ip_address': ip_address,
            'is_trusted': is_trusted
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Web interface routes
@security_web_bp.route('/security-dashboard')
@login_required
@role_required(['super_admin', 'org_admin'])
def security_dashboard():
    """Security monitoring dashboard"""
    try:
        # Get recent security report
        report = security_service.get_security_report(7)
        
        return render_template('security_dashboard.html', report=report)
    except Exception as e:
        return f"Error loading security dashboard: {str(e)}", 500

@security_web_bp.route('/security-events')
@login_required
@role_required(['super_admin', 'org_admin'])
def security_events():
    """Security events monitoring page"""
    try:
        from app.extensions import mongo
        from datetime import timedelta
        
        # Get recent security events
        start_date = datetime.utcnow() - timedelta(days=7)
        
        events = list(mongo.db.security_events.find({
            'timestamp': {'$gte': start_date}
        }).sort('timestamp', -1).limit(100))
        
        return render_template('security_events.html', events=events)
    except Exception as e:
        return f"Error loading security events: {str(e)}", 500

@security_web_bp.route('/account-lockouts')
@login_required
@role_required(['super_admin', 'org_admin'])
def account_lockouts():
    """Account lockouts management page"""
    try:
        from app.extensions import mongo
        
        # Get current lockouts
        lockouts = list(mongo.db.account_lockouts.find({
            'locked_until': {'$gte': datetime.utcnow()}
        }).sort('locked_at', -1))
        
        return render_template('account_lockouts.html', lockouts=lockouts)
    except Exception as e:
        return f"Error loading account lockouts: {str(e)}", 500

@security_web_bp.route('/password-policy')
@login_required
@role_required(['super_admin', 'org_admin'])
def password_policy():
    """Password policy management page"""
    return render_template('password_policy.html', policy=security_service.password_policy)

# Enhanced authentication middleware
def enhanced_auth_middleware():
    """Enhanced authentication middleware with security checks"""
    if request.endpoint and request.endpoint.startswith('security'):
        # Additional security checks for security endpoints
        
        # Check rate limiting
        identifier = request.remote_addr
        allowed, remaining = security_service.check_rate_limit(identifier, 'api')
        
        if not allowed:
            security_service.log_security_event('rate_limit_exceeded', {
                'ip_address': identifier,
                'endpoint': request.endpoint
            })
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Check IP validation for sensitive operations
        if request.method in ['POST', 'PUT', 'DELETE']:
            if not security_service.validate_ip_address(request.remote_addr):
                security_service.log_security_event('untrusted_ip_access', {
                    'ip_address': request.remote_addr,
                    'endpoint': request.endpoint
                })
                # Could return 403 here if IP restrictions are enforced
        
        # Log security-related API access
        if hasattr(request, 'view_args') and 'security' in request.endpoint:
            security_service.log_security_event('security_api_access', {
                'endpoint': request.endpoint,
                'method': request.method,
                'ip_address': request.remote_addr
            })

def register_security_blueprints(app):
    """Register security monitoring blueprints"""
    app.register_blueprint(security_bp)
    app.register_blueprint(security_web_bp)
    
    # Register enhanced auth middleware
    app.before_request(enhanced_auth_middleware)
