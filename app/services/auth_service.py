import random
import string
from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, create_refresh_token
from flask import current_app
from bson import ObjectId
from app.extensions import mongo
from app.models.user import User
from app.models.organization import Organization
from app.services.email_verification_service import EmailVerificationService

class AuthService:
    """Enhanced authentication service for multi-tenant phone-based login"""
    
    @staticmethod
    def generate_otp(length=6):
        """Generate a random OTP"""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def send_otp(phone_number, otp):
        """Send OTP via SMS (placeholder - integrate with SMS service)"""
        # TODO: Integrate with SMS service like Twilio
        print(f"Sending OTP {otp} to {phone_number}")
        return True
    
    @staticmethod
    def request_otp(phone_number):
        """Request OTP for phone number (multi-tenant aware)"""
        if not User.validate_phone_number(phone_number):
            return {'error': 'Invalid phone number format'}, 400
        
        # Normalize phone number
        normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
        
        # Generate OTP
        otp = AuthService.generate_otp()
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Check if user exists across all organizations
        user_data = mongo.db.users.find_one({'phone_number': normalized_phone})
        
        if user_data:
            # Update existing user with OTP
            mongo.db.users.update_one(
                {'phone_number': normalized_phone},
                {
                    '$set': {
                        'otp_code': otp,
                        'otp_expires_at': otp_expires_at,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        else:
            # Create new temporary user with OTP (no organization yet)
            new_user = User(
                phone_number=normalized_phone,
                name='',  # Will be filled during verification
                role='student'  # Default role
            )
            new_user.otp_code = otp
            new_user.otp_expires_at = otp_expires_at
            
            result = mongo.db.users.insert_one(new_user.to_dict(include_sensitive=True))
            new_user._id = result.inserted_id
        
        # Send OTP
        if AuthService.send_otp(normalized_phone, otp):
            return {'message': 'OTP sent successfully'}, 200
        else:
            return {'error': 'Failed to send OTP'}, 500
    
    @staticmethod
    def verify_otp(phone_number, otp, name=None):
        """Verify OTP and return JWT tokens"""
        normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
        user_data = mongo.db.users.find_one({'phone_number': normalized_phone})
        
        if not user_data:
            return {'error': 'User not found'}, 404
        
        user = User.from_dict(user_data)
        
        # Check OTP validity
        if not user.otp_code or user.otp_code != otp:
            return {'error': 'Invalid OTP'}, 400
        
        if user.otp_expires_at < datetime.utcnow():
            return {'error': 'OTP expired'}, 400
        
        # Update user
        update_data = {
            'verification_status': 'verified',
            'last_login': datetime.utcnow(),
            'otp_code': None,
            'otp_expires_at': None,
            'updated_at': datetime.utcnow()
        }
        
        # Update name if provided (for new users)
        if name and not user.name:
            update_data['name'] = name
        
        mongo.db.users.update_one(
            {'_id': user_data['_id']},
            {'$set': update_data}
        )
        
        # Create JWT tokens
        additional_claims = {
            'phone_number': user.phone_number,
            'role': user.role,
            'organization_id': str(user.organization_id) if user.organization_id else None,
            'permissions': user.permissions
        }
        
        access_token = create_access_token(
            identity=str(user_data['_id']),
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=str(user_data['_id']))
        
        # Get updated user data
        updated_user_data = mongo.db.users.find_one({'_id': user_data['_id']})
        updated_user = User.from_dict(updated_user_data)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': updated_user.to_dict()
        }, 200
    
    @staticmethod
    def login_with_password(phone_number, password):
        """Login with phone number and password"""
        if not phone_number or not password:
            phone_number = '+' + phone_number
        print(f"Login with phone number: {phone_number} and password: {password}")
        normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
        user_data = mongo.db.users.find_one({'phone_number': normalized_phone})
        print(f"User data: {user_data}")
        
        if not user_data:
            return {'error': 'User not found'}, 404
        
        user = User.from_dict(user_data)
        
        if not user.check_password(password):
            return {'error': 'Invalid password'}, 400
        
        if not user.is_active:
            return {'error': 'Account is deactivated'}, 403
        
        # Update last login
        mongo.db.users.update_one(
            {'_id': user_data['_id']},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        
        # Create JWT tokens
        additional_claims = {
            'phone_number': user.phone_number,
            'role': user.role,
            'organization_id': str(user.organization_id) if user.organization_id else None,
            'permissions': user.permissions
        }
        
        access_token = create_access_token(
            identity=str(user_data['_id']),
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=str(user_data['_id']))
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }, 200
    
    @staticmethod
    def register_user(phone_number, name, password=None, role='student', 
                     organization_id=None, created_by=None, email=None):
        """Register a new user within an organization"""
        if not User.validate_phone_number(phone_number):
            return {'error': 'Invalid phone number format'}, 400
        
        # Validate email if provided
        if email:
            is_valid_email, email_message = User.validate_email(email)
            if not is_valid_email:
                return {'error': email_message}, 400
        
        normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
        
        # Check if user already exists by phone or email
        existing_user = mongo.db.users.find_one({'phone_number': normalized_phone})
        if existing_user:
            return {'error': 'User with this phone number already exists'}, 409
        
        if email:
            existing_email = mongo.db.users.find_one({'email': email})
            if existing_email:
                return {'error': 'User with this email already exists'}, 409
        
        # Validate organization exists
        if organization_id:
            org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
            if not org_data:
                return {'error': 'Organization not found'}, 404
        
        # Create new user
        new_user = User(
            phone_number=normalized_phone,
            name=name,
            role=role,
            password=password,
            organization_id=organization_id,
            created_by=created_by
        )
        new_user.verification_status = 'verified' if password else 'pending'
        
        # Set email if provided
        if email:
            new_user.email = email
        
        result = mongo.db.users.insert_one(new_user.to_dict(include_sensitive=True))
        new_user._id = result.inserted_id
        
        return {'user': new_user.to_dict(), 'user_id': str(result.inserted_id)}, 201
    
    @staticmethod
    def create_organization_with_admin(org_name, contact_info, address, activities, 
                                     admin_phone, admin_name, admin_password):
        """Create new organization with admin user"""
        try:
            # Validate admin phone number
            if not User.validate_phone_number(admin_phone):
                return {'error': 'Invalid admin phone number format'}, 400
            
            normalized_phone = User(admin_phone, 'temp')._normalize_phone_number(admin_phone)
            
            # Check if admin user already exists
            existing_admin = mongo.db.users.find_one({'phone_number': normalized_phone})
            if existing_admin:
                return {'error': 'Admin user already exists'}, 409
            
            # Create organization first
            new_org = Organization(
                name=org_name,
                owner_id=None,  # Will be set after creating admin user
                contact_info=contact_info,
                address=address,
                activities=activities
            )
            
            org_result = mongo.db.organizations.insert_one(new_org.to_dict())
            new_org._id = org_result.inserted_id
            org_id = str(new_org._id)
            
            # Create admin user
            admin_user = User(
                phone_number=normalized_phone,
                name=admin_name,
                role='org_admin',
                password=admin_password,
                organization_id=org_id
            )
            admin_user.verification_status = 'verified'
            
            admin_result = mongo.db.users.insert_one(admin_user.to_dict(include_sensitive=True))
            admin_user._id = admin_result.inserted_id
            
            # Update organization with admin user ID
            mongo.db.organizations.update_one(
                {'_id': new_org._id},
                {'$set': {'owner_id': admin_user._id}}
            )
            
            return {
                'organization': new_org.to_dict(),
                'admin_user': admin_user.to_dict(),
                'message': 'Organization and admin user created successfully'
            }, 201
        
        except Exception as e:
            # Cleanup on error
            if 'org_result' in locals():
                mongo.db.organizations.delete_one({'_id': org_result.inserted_id})
            if 'admin_result' in locals():
                mongo.db.users.delete_one({'_id': admin_result.inserted_id})
            
            return {'error': f'Failed to create organization: {str(e)}'}, 500
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        try:
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if user_data:
                return User.from_dict(user_data)
            return None
        except:
            return None
    
    @staticmethod
    def get_users_by_organization(organization_id, role=None):
        """Get all users in an organization"""
        try:
            query = {'organization_id': ObjectId(organization_id)}
            if role:
                query['role'] = role
            
            users_cursor = mongo.db.users.find(query)
            users = [User.from_dict(user_data) for user_data in users_cursor]
            return users
        except:
            return []
    
    @staticmethod
    def update_user_profile(user_id, update_data):
        """Update user profile"""
        try:
            # Remove sensitive fields that shouldn't be updated directly
            sensitive_fields = ['password_hash', 'otp_code', 'otp_expires_at', '_id', 
                              'role', 'organization_id', 'permissions']
            for field in sensitive_fields:
                update_data.pop(field, None)
            
            update_data['updated_at'] = datetime.utcnow()
            
            result = mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                updated_user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
                return User.from_dict(updated_user_data), 200
            else:
                return None, 404
        except Exception as e:
            return None, 400
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """Change user password"""
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user_data:
            return {'error': 'User not found'}, 404
        
        user = User.from_dict(user_data)
        
        if not user.check_password(old_password):
            return {'error': 'Invalid current password'}, 400
        
        user.set_password(new_password)
        
        mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'password_hash': user.password_hash,
                'updated_at': datetime.utcnow()
            }}
        )
        
        return {'message': 'Password updated successfully'}, 200
    
    @staticmethod
    def deactivate_user(user_id, deactivated_by):
        """Deactivate a user account"""
        try:
            result = mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'is_active': False,
                    'updated_at': datetime.utcnow(),
                    'deactivated_by': ObjectId(deactivated_by),
                    'deactivated_at': datetime.utcnow()
                }}
            )
            
            if result.modified_count > 0:
                return {'message': 'User deactivated successfully'}, 200
            else:
                return {'error': 'User not found'}, 404
        except Exception as e:
            return {'error': 'Failed to deactivate user'}, 500
    
    @staticmethod
    def update_user_role(user_id, new_role, updated_by):
        """Update user role (admin function)"""
        try:
            # Validate new role
            if new_role not in User.ROLES:
                return {'error': 'Invalid role'}, 400
            
            # Get new permissions for the role
            temp_user = User('temp', 'temp', role=new_role)
            new_permissions = temp_user.permissions
            
            result = mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'role': new_role,
                    'permissions': new_permissions,
                    'updated_at': datetime.utcnow(),
                    'role_updated_by': ObjectId(updated_by)
                }}
            )
            
            if result.modified_count > 0:
                updated_user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
                return User.from_dict(updated_user_data), 200
            else:
                return None, 404
        except Exception as e:
            return None, 400
    
    @staticmethod
    def authenticate_user(email, password):
        """Authenticate user with email and password"""
        try:
            user_data = mongo.db.users.find_one({'email': email})
            
            if not user_data:
                return None
            
            user = User.from_dict(user_data)
            
            if not user.check_password(password):
                return None
            
            if not user.is_active:
                return None
            
            # Update last login
            mongo.db.users.update_one(
                {'_id': user_data['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            
            return user_data
        except Exception as e:
            return None
    
    @staticmethod
    def create_user(user_data):
        """Create a new user with email and password"""
        try:
            # Check if user already exists
            existing_user = mongo.db.users.find_one({'email': user_data['email']})
            if existing_user:
                return {'error': 'User already exists'}, 409
            
            # Create new user
            new_user = User(
                phone_number=user_data.get('phone_number', ''),
                name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                role=user_data.get('role', 'student'),
                password=user_data.get('password'),
                organization_id=user_data.get('organization_id')
            )
            new_user.email = user_data['email']
            new_user.first_name = user_data.get('first_name', '')
            new_user.last_name = user_data.get('last_name', '')
            new_user.verification_status = 'verified'
            
            result = mongo.db.users.insert_one(new_user.to_dict(include_sensitive=True))
            new_user._id = result.inserted_id
            
            return {'user': new_user.to_dict(), 'user_id': str(result.inserted_id)}, 201
        except Exception as e:
            return {'error': f'Failed to create user: {str(e)}'}, 500
    
    @staticmethod
    def send_verification_code(phone_number: str):
        """Send verification code to user's registered email"""
        try:
            # Normalize phone number
            if not User.validate_phone_number(phone_number):
                return {'error': 'Invalid phone number format'}, 400
            
            normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
            
            print(f"Normalized phone: {normalized_phone}")
            # Find user by phone number
            user_data = mongo.db.users.find_one({'phone_number': normalized_phone})
            if not user_data:
                return {'error': 'No account found with this phone number'}, 404
            
            print(f"User data: {user_data}")
            # Check if user has email
            if user_data.get('email'):
            
            # Generate and send verification code
                email_service = EmailVerificationService()
                success, message, verification_code = email_service.send_verification_code(
                    normalized_phone,
                    user_data['email'],
                    user_data.get('first_name') or user_data.get('name', '').split(' ')[0]
                )
                
                if success:
                    # Store verification code in database
                    expiry_minutes = current_app.config.get('VERIFICATION_CODE_EXPIRY', 600) // 60
                    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
                    
                    mongo.db.users.update_one(
                        {'_id': user_data['_id']},
                        {
                            '$set': {
                                'verification_code': verification_code,
                                'verification_code_expires': expires_at,
                                'verification_attempts': 0,
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )
                    
                    return {'message': message}, 200
                else:
                    return {'error': message}, 500
            else:
                return {'success': True}, 200
        except Exception as e:
            current_app.logger.error(f"Error sending verification code: {str(e)}")
            return {'error': 'Failed to send verification code'}, 500
    
    @staticmethod
    def verify_code_and_login(phone_number: str, verification_code: str):
        """Verify the code and log in the user"""
        try:
            # Normalize phone number
            if not User.validate_phone_number(phone_number):
                return {'error': 'Invalid phone number format'}, 400
            
            normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
            
            # Find user by phone number
            user_data = mongo.db.users.find_one({'phone_number': normalized_phone})
            if not user_data:
                return {'error': 'No account found with this phone number'}, 404
            
            # Check verification code
            stored_code = user_data.get('verification_code')
            code_expires = user_data.get('verification_code_expires')
            attempts = user_data.get('verification_attempts', 0)
            
            # Check if too many attempts
            if attempts >= 5:
                return {'error': 'Too many verification attempts. Please request a new code.'}, 429
            
            # Check if code exists and is not expired
            if not stored_code or not code_expires:
                return {'error': 'No verification code found. Please request a new one.'}, 400
            
            if datetime.utcnow() > code_expires:
                return {'error': 'Verification code has expired. Please request a new one.'}, 400
            
            # Verify the code
            if stored_code != verification_code:
                # Increment attempts
                mongo.db.users.update_one(
                    {'_id': user_data['_id']},
                    {'$inc': {'verification_attempts': 1}}
                )
                return {'error': 'Invalid verification code'}, 400
            
            # Code is valid - clear verification data and update last login
            mongo.db.users.update_one(
                {'_id': user_data['_id']},
                {
                    '$unset': {
                        'verification_code': '',
                        'verification_code_expires': '',
                        'verification_attempts': ''
                    },
                    '$set': {
                        'last_login': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Create JWT tokens
            user = User.from_dict(user_data)
            additional_claims = {
                'phone_number': user.phone_number,
                'role': user.role,
                'organization_id': str(user.organization_id) if user.organization_id else None,
                'permissions': user.permissions
            }
            
            access_token = create_access_token(
                identity=str(user_data['_id']),
                additional_claims=additional_claims
            )
            refresh_token = create_refresh_token(identity=str(user_data['_id']))
            
            return {
                'message': 'Login successful',
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user.to_dict()
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Error verifying code: {str(e)}")
            return {'error': 'Failed to verify code'}, 500
    
    @staticmethod
    def get_verification_status():
        """Get verification service status"""
        try:
            email_service = EmailVerificationService()
            return email_service.verify_ses_configuration()
        except Exception as e:
            return {
                'configured': False,
                'error': str(e)
            } 