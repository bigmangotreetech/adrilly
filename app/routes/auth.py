from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.services.auth_service import AuthService
from app.extensions import mongo
from marshmallow import Schema, fields, ValidationError
from bson import ObjectId

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Request schemas for validation
class OTPRequestSchema(Schema):
    phone_number = fields.Str(required=True)

class OTPVerifySchema(Schema):
    phone_number = fields.Str(required=True)
    otp = fields.Str(required=True)
    name = fields.Str(required=False)

class LoginSchema(Schema):
    phone_number = fields.Str(required=True)
    password = fields.Str(required=True)

class RegisterUserSchema(Schema):
    phone_number = fields.Str(required=True)
    name = fields.Str(required=True)
    password = fields.Str(required=False)
    role = fields.Str(required=False, validate=lambda x: x in ['org_admin', 'center_admin', 'coach', 'student'])
    organization_id = fields.Str(required=True)  # Required for multi-tenant

class CreateOrganizationSchema(Schema):
    name = fields.Str(required=True)
    contact_info = fields.Dict(required=False)
    address = fields.Dict(required=False)
    sports = fields.List(fields.Str(), required=False)
    admin_phone = fields.Str(required=True)
    admin_name = fields.Str(required=True)
    admin_password = fields.Str(required=True)

class UpdateProfileSchema(Schema):
    name = fields.Str(required=False)
    profile_data = fields.Dict(required=False)

class ChangePasswordSchema(Schema):
    old_password = fields.Str(required=True)
    new_password = fields.Str(required=True)

@auth_bp.route('/request-otp', methods=['POST'])
def request_otp():
    """Request OTP for phone number (multi-tenant aware)"""
    try:
        # Validate request data
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = OTPRequestSchema()
        data = schema.load(request.json)
        
        # Log OTP request (without sensitive data)
        print(f"OTP request for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        
        result, status_code = AuthService.request_otp(data['phone_number'])
        
        if status_code == 200:
            print(f"OTP sent successfully for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        else:
            print(f"OTP request failed for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]} - {result.get('error', 'Unknown error')}")
        
        return jsonify(result), status_code
    
    except ValidationError as e:
        print(f"OTP request validation error: {e.messages}")
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        print(f"OTP request internal error: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e) if current_app.debug else 'Contact support'}), 500

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP and login/register user"""
    try:
        # Validate request data
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = OTPVerifySchema()
        data = schema.load(request.json)
        
        # Log OTP verification attempt (without sensitive data)
        print(f"OTP verification attempt for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        
        result, status_code = AuthService.verify_otp(
            data['phone_number'],
            data['otp'],
            data.get('name')
        )
        
        if status_code == 200:
            print(f"OTP verification successful for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        else:
            print(f"OTP verification failed for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]} - {result.get('error', 'Unknown error')}")
        
        return jsonify(result), status_code
    
    except ValidationError as e:
        print(f"OTP verification validation error: {e.messages}")
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        print(f"OTP verification internal error: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e) if current_app.debug else 'Contact support'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with phone number and password"""
    try:
        # Validate request data
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = LoginSchema()
        data = schema.load(request.json)
        
        # Log login attempt (without sensitive data)
        print(f"Login attempt for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        
        result, status_code = AuthService.login_with_password(
            data['phone_number'],
            data['password']
        )
        
        if status_code == 200:
            print(f"Login successful for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]}")
        else:
            print(f"Login failed for phone: {data['phone_number'][:3]}***{data['phone_number'][-3:]} - {result.get('error', 'Unknown error')}")
        
        return jsonify(result), status_code
    
    except ValidationError as e:
        print(f"Login validation error: {e.messages}")
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        print(f"Login internal error: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e) if current_app.debug else 'Contact support'}), 500

@auth_bp.route('/register-user', methods=['POST'])
@jwt_required()
def register_user():
    """Register new user within organization (admin/center_admin only)"""
    try:
        schema = RegisterUserSchema()
        data = schema.load(request.json)
        
        # Check permissions
        claims = get_jwt()
        current_user_role = claims.get('role')
        current_user_id = get_jwt_identity()
        current_org_id = claims.get('organization_id')
        
        # Only certain roles can create users
        if current_user_role not in ['super_admin', 'org_admin', 'center_admin']:
            return jsonify({'error': 'Insufficient permissions to create users'}), 403
        
        # Ensure user is creating in their own organization (except super_admin)
        if current_user_role != 'super_admin' and current_org_id != data['organization_id']:
            return jsonify({'error': 'Cannot create users in other organizations'}), 403
        
        # Role hierarchy validation
        current_user = AuthService.get_user_by_id(current_user_id)
        if not current_user.can_manage_user_role(data.get('role', 'student')):
            return jsonify({'error': 'Cannot create users with this role'}), 403
        
        result, status_code = AuthService.register_user(
            phone_number=data['phone_number'],
            name=data['name'],
            password=data.get('password'),
            role=data.get('role', 'student'),
            organization_id=data['organization_id'],
            created_by=current_user_id
        )
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/create-organization', methods=['POST'])
@jwt_required()
def create_organization():
    """Create new organization with admin user (super_admin only)"""
    try:
        schema = CreateOrganizationSchema()
        data = schema.load(request.json)
        
        # Check permissions
        claims = get_jwt()
        current_user_role = claims.get('role')
        
        # Only super_admin can create organizations
        if current_user_role != 'super_admin':
            return jsonify({'error': 'Only super administrators can create organizations'}), 403
        
        result, status_code = AuthService.create_organization_with_admin(
            org_name=data['name'],
            contact_info=data.get('contact_info', {}),
            address=data.get('address', {}),
            sports=data.get('sports', []),
            admin_phone=data['admin_phone'],
            admin_name=data['admin_name'],
            admin_password=data['admin_password']
        )
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile with organization info"""
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(user_id)
        
        if user:
            profile_data = user.to_dict()
            
            # Add organization details if available
            if user.organization_id:
                org_data = mongo.db.organizations.find_one({'_id': user.organization_id})
                if org_data:
                    profile_data['organization'] = {
                        'id': str(org_data['_id']),
                        'name': org_data['name'],
                        'sports': org_data.get('sports', [])
                    }
            
            return jsonify({'user': profile_data}), 200
        else:
            return jsonify({'error': 'User not found'}), 404
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        schema = UpdateProfileSchema()
        data = schema.load(request.json)
        
        user_id = get_jwt_identity()
        user, status_code = AuthService.update_user_profile(user_id, data)
        
        if user:
            return jsonify({'user': user.to_dict()}), status_code
        else:
            return jsonify({'error': 'Failed to update profile'}), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        schema = ChangePasswordSchema()
        data = schema.load(request.json)
        
        user_id = get_jwt_identity()
        result, status_code = AuthService.change_password(
            user_id,
            data['old_password'],
            data['new_password']
        )
        
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Create new access token
        from flask_jwt_extended import create_access_token
        additional_claims = {
            'phone_number': user.phone_number,
            'role': user.role,
            'organization_id': str(user.organization_id) if user.organization_id else None,
            'permissions': user.permissions
        }
        
        access_token = create_access_token(
            identity=user_id,
            additional_claims=additional_claims
        )
        
        return jsonify({'access_token': access_token}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (invalidate token)"""
    try:
        # In a production system, you'd want to blacklist the token
        # For now, just return success
        return jsonify({'message': 'Logged out successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/organizations', methods=['GET'])
@jwt_required()
def get_organizations():
    """Get accessible organizations for current user"""
    try:
        claims = get_jwt()
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        accessible_orgs = user.get_accessible_organizations()
        
        if accessible_orgs == 'all':
            # Super admin can see all organizations
            orgs_cursor = mongo.db.organizations.find({})
        elif accessible_orgs:
            # User can see specific organizations
            org_ids = [ObjectId(org_id) for org_id in accessible_orgs]
            orgs_cursor = mongo.db.organizations.find({'_id': {'$in': org_ids}})
        else:
            # No access to any organizations
            orgs_cursor = []
        
        organizations = []
        for org_data in orgs_cursor:
            organizations.append({
                'id': str(org_data['_id']),
                'name': org_data['name'],
                'sports': org_data.get('sports', []),
                'contact_info': org_data.get('contact_info', {}),
                'created_at': org_data.get('created_at'),
                'is_active': org_data.get('is_active', True)
            })
        
        return jsonify({
            'organizations': organizations,
            'total': len(organizations)
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/switch-organization/<org_id>', methods=['POST'])
@jwt_required()
def switch_organization(org_id):
    """Switch to a different organization (for users with multi-org access)"""
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user can access this organization
        if not user.can_access_organization(org_id):
            return jsonify({'error': 'Access denied to this organization'}), 403
        
        # Create new access token with updated organization context
        from flask_jwt_extended import create_access_token, create_refresh_token
        
        additional_claims = {
            'phone_number': user.phone_number,
            'role': user.role,
            'organization_id': org_id,
            'permissions': user.permissions
        }
        
        access_token = create_access_token(
            identity=user_id,
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=user_id)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Organization switched successfully'
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@auth_bp.route('/change-password-api', methods=['POST'])
@jwt_required()
def change_password_api():
    """Change user password"""
    try:
        data = request.get_json()
        
        if not data or 'current_password' not in data or 'new_password' not in data:
            return jsonify({'error': 'Current password and new password are required'}), 400
        
        current_password = data['current_password']
        new_password = data['new_password']
        
        # Validate new password
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters long'}), 400
        
        user_id = get_jwt_identity()
        
        # Get user from database
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Verify current password
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Update password
        user.set_password(new_password)
        
        # Save to database
        update_result = mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'password_hash': user.password_hash}}
        )
        
        if update_result.modified_count == 0:
            return jsonify({'error': 'Failed to update password'}), 500
        
        return jsonify({'message': 'Password changed successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# Helper function to check user permissions
def require_role(allowed_roles):
    """Decorator to check user role"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            try:
                claims = get_jwt()
                user_role = claims.get('role')
                
                if user_role not in allowed_roles:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': 'Authorization error'}), 401
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def require_permission(permission):
    """Decorator to check specific permission"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            try:
                claims = get_jwt()
                user_permissions = claims.get('permissions', [])
                
                if permission not in user_permissions:
                    return jsonify({'error': f'Missing required permission: {permission}'}), 403
                
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': 'Authorization error'}), 401
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator 