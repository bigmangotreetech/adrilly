from flask import session
from flask_jwt_extended import get_jwt, get_jwt_identity


def get_user_info_from_session_or_claims():
    """
    Get user information from session first, fall back to JWT claims if not available
    Returns: dict with user_id, role, organization_id
    """
    # Try session first
    if 'user_id' in session and session.get('user_id'):
        return {
            'user_id': session['user_id'],
            'role': session.get('role'),
            'organization_id': session.get('organization_id')
        }
    
    # Fall back to JWT claims
    try:
        claims = get_jwt()
        return {
            'user_id': get_jwt_identity(),
            'role': claims.get('role'),
            'organization_id': claims.get('organization_id')
        }
    except Exception:
        return None