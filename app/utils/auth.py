from functools import wraps
from flask import session, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from bson import ObjectId
from app.extensions import mongo

def jwt_or_session_required():
    """
    Custom decorator that accepts both JWT tokens and logged-in sessions
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # First, session authentication
            if 'user_id' in session and session.get('user_id'):
                return f(*args, **kwargs)
            
            # Then, try JWT authentication
            try:
                verify_jwt_in_request()
                # If JWT is valid, proceed with JWT claims
                return f(*args, **kwargs)
            except Exception as jwt_error:
                # JWT failed, try session authentication
                return jsonify({'error': 'Authorization token or valid session required'}), 401
        
        return wrapper
    return decorator

def get_current_user_info():
    """
    Get current user information from either JWT or session
    Returns: dict with user_id, role, organization_id, permissions
    """
    try:
        # Try JWT first
        verify_jwt_in_request()
        claims = get_jwt()
        user_id = get_jwt_identity()
        
        return {
            'user_id': user_id,
            'role': claims.get('role'),
            'organization_id': claims.get('organization_id'),
            'permissions': claims.get('permissions', []),
            'phone_number': claims.get('phone_number'),
            'auth_type': 'jwt'
        }
    except Exception:
        # Try session authentication
        if 'user_id' in session and session.get('user_id'):
            # Get user data from database to populate missing session info
            user_data = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
            if user_data:
                return {
                    'user_id': session['user_id'],
                    'role': session.get('role') or user_data.get('role'),
                    'organization_id': session.get('organization_id') or str(user_data.get('organization_id', '')),
                    'permissions': user_data.get('permissions', []),
                    'phone_number': user_data.get('phone_number'),
                    'auth_type': 'session'
                }
        
        return None

def require_role_hybrid(allowed_roles):
    """
    Role-based access control that works with both JWT and session auth
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_info = get_current_user_info()
            
            if not user_info:
                return jsonify({'error': 'Authentication required'}), 401
            
            user_role = user_info.get('role')
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return wrapper
    return decorator

def get_current_user_id():
    """
    Get current user ID from either JWT or session
    """
    user_info = get_current_user_info()
    return user_info['user_id'] if user_info else None

def get_current_user_role():
    """
    Get current user role from either JWT or session
    """
    user_info = get_current_user_info()
    return user_info['role'] if user_info else None

def get_current_organization_id():
    """
    Get current organization ID from either JWT or session
    """
    user_info = get_current_user_info()
    return user_info['organization_id'] if user_info else None
