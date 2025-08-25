from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import re

class User:
    """User model for multi-tenant sports coaching system"""
    
    # Define role hierarchy
    ROLES = {
        'super_admin': 0,    # Platform super admin
        'org_admin': 1,      # Organization admin/owner
        'center_admin': 2,    # Senior coach with admin privileges
        'coach': 3,          # Regular coach
        'student': 4         # Student
    }
    
    def __init__(self, phone_number, name, role='student', password=None, 
                 organization_id=None, groups=None, profile_data=None, created_by=None):
        self.phone_number = self._normalize_phone_number(phone_number) if phone_number else ''
        self.name = name
        self.role = role
        self.password_hash = generate_password_hash(password) if password else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.groups = groups or []  # Group IDs for students
        self.profile_data = profile_data or {}
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.last_login = None
        self.verification_status = 'pending'  # 'pending', 'verified'
        self.otp_code = None
        self.otp_expires_at = None
        self.created_by = ObjectId(created_by) if created_by else None
        
        # Email support
        self.email = None
        self.first_name = ''
        self.last_name = ''
        
        # Profile picture
        self.profile_picture_url = None
        
        # Billing information
        self.billing_start_date = None
        
        # Multi-tenant specific fields
        self.can_create_organizations = (role in ['super_admin'])
        self.can_manage_organization = (role in ['super_admin', 'org_admin'])
        self.can_manage_coaches = (role in ['super_admin', 'org_admin', 'center_admin'])
        self.can_manage_students = (role in ['super_admin', 'org_admin', 'center_admin', 'coach'])
        
        # Organization-specific permissions
        self.permissions = self._get_default_permissions(role)
    
    def _normalize_phone_number(self, phone_number):
        """Normalize phone number format for consistency"""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d\+]', '', phone_number)
        
        return cleaned
    
    def _get_default_permissions(self, role):
        """Get default permissions based on role"""
        permissions = {
            'super_admin': [
                'create_organizations', 'manage_all_organizations', 'manage_all_users',
                'view_all_data', 'system_settings', 'billing_management'
            ],
            'org_admin': [
                'manage_organization', 'manage_coaches', 'manage_students', 'manage_groups',
                'manage_classes', 'manage_payments', 'view_reports', 'organization_settings'
            ],
            'center_admin': [
                'manage_coaches', 'manage_students', 'manage_groups', 'manage_classes',
                'view_attendance', 'manage_progress', 'view_reports'
            ],
            'coach': [
                'manage_students', 'manage_classes', 'view_attendance', 'manage_progress',
                'view_own_classes', 'mark_attendance'
            ],
            'student': [
                'view_own_profile', 'view_own_classes', 'view_own_attendance',
                'view_own_progress', 'view_own_payments', 'marketplace_access'
            ]
        }
        return permissions.get(role, permissions['student'])
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
        self.updated_at = datetime.utcnow()
    
    def check_password(self, password):
        """Check password against hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        return permission in self.permissions
    
    def can_access_organization(self, target_org_id):
        """Check if user can access specific organization"""
        if self.role == 'super_admin':
            return True
        
        if not self.organization_id:
            return False
            
        return str(self.organization_id) == str(target_org_id)
    
    def can_manage_user(self, target_user):
        """Check if user can manage another user"""
        # Super admin can manage everyone
        if self.role == 'super_admin':
            return True
        
        # Must be in same organization
        if not self.can_access_organization(target_user.organization_id):
            return False
        
        # Role hierarchy check
        user_level = self.ROLES.get(self.role, 999)
        target_level = self.ROLES.get(target_user.role, 999)
        
        return user_level < target_level
    
    def get_accessible_organizations(self):
        """Get list of organization IDs this user can access"""
        if self.role == 'super_admin':
            return 'all'  # Special indicator for all organizations
        elif self.organization_id:
            return [str(self.organization_id)]
        else:
            return []
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary"""
        user_dict = {
            'phone_number': self.phone_number,
            'name': self.name,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'profile_picture_url': self.profile_picture_url,
            'role': self.role,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'groups': [str(group_id) for group_id in self.groups],
            'profile_data': self.profile_data,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_login': self.last_login,
            'verification_status': self.verification_status,
            'permissions': self.permissions,
            'created_by': str(self.created_by) if self.created_by else None,
            'can_create_organizations': self.can_create_organizations,
            'can_manage_organization': self.can_manage_organization,
            'can_manage_coaches': self.can_manage_coaches,
            'can_manage_students': self.can_manage_students,
            'billing_start_date': self.billing_start_date
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            user_dict['_id'] = str(self._id)
        
        if include_sensitive:
            user_dict.update({
                'password_hash': self.password_hash,
                'otp_code': self.otp_code,
                'otp_expires_at': self.otp_expires_at
            })
        
        return user_dict
    
    @classmethod
    def from_dict(cls, data):
        """Create user from dictionary"""
        user = cls(
            phone_number=data['phone_number'],
            name=data['name'],
            role=data.get('role', 'student'),
            organization_id=data.get('organization_id'),
            groups=data.get('groups', []),
            profile_data=data.get('profile_data', {}),
            created_by=data.get('created_by')
        )
        
        # Set additional attributes
        if 'password_hash' in data:
            user.password_hash = data['password_hash']
        if '_id' in data:
            user._id = data['_id']
        if 'email' in data:
            user.email = data['email']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'created_at' in data:
            user.created_at = data['created_at']
        if 'updated_at' in data:
            user.updated_at = data['updated_at']
        if 'last_login' in data:
            user.last_login = data['last_login']
        if 'verification_status' in data:
            user.verification_status = data['verification_status']
        if 'otp_code' in data:
            user.otp_code = data['otp_code']
        if 'otp_expires_at' in data:
            user.otp_expires_at = data['otp_expires_at']
        if 'permissions' in data:
            user.permissions = data['permissions']
        if 'can_create_organizations' in data:
            user.can_create_organizations = data['can_create_organizations']
        if 'can_manage_organization' in data:
            user.can_manage_organization = data['can_manage_organization']
        if 'can_manage_coaches' in data:
            user.can_manage_coaches = data['can_manage_coaches']
        if 'can_manage_students' in data:
            user.can_manage_students = data['can_manage_students']
        if 'billing_start_date' in data:
            user.billing_start_date = data['billing_start_date']
        
        return user
    
    @staticmethod
    def validate_phone_number(phone_number):
        """Validate phone number format"""
        # Accept formats like +1234567890, +91-9876543210, etc.
        pattern = r'^\+[1-9]\d{1,14}$'  # E.164 format
        normalized = re.sub(r'[^\d\+]', '', phone_number)
        
        if not normalized.startswith('+'):
            if len(normalized) == 10:  # US format
                normalized = '+1' + normalized
            else:
                normalized = '+' + normalized
        
        return re.match(pattern, normalized) is not None
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return False, "Email is required"
        
        # Basic email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False, "Please enter a valid email address"
        
        if len(email) > 254:  # RFC 5321 limit
            return False, "Email address is too long"
        
        return True, "Valid email"
    
    @staticmethod
    def validate_password(password):
        """Validate password format - must be minimum 10 alphanumeric characters"""
        if not password:
            return False, "Password is required"
        
        if len(password) < 10:
            return False, "Password must be at least 10 characters long"
        
        if not re.match(r'^[a-zA-Z0-9]+$', password):
            return False, "Password must contain only letters and numbers"
        
        # Check for at least one letter and one number
        has_letter = bool(re.search(r'[a-zA-Z]', password))
        has_number = bool(re.search(r'[0-9]', password))
        
        if not (has_letter and has_number):
            return False, "Password must contain at least one letter and one number"
        
        return True, "Valid password"
    
    def is_admin_or_coach(self):
        """Check if user is admin or coach"""
        return self.role in ['super_admin', 'org_admin', 'center_admin', 'coach']
    
    def is_student(self):
        """Check if user is student"""
        return self.role == 'student'
    
    def is_organization_admin(self):
        """Check if user can manage their organization"""
        return self.role in ['super_admin', 'org_admin']
    
    def get_role_display_name(self):
        """Get human-readable role name"""
        role_names = {
            'super_admin': 'Super Administrator',
            'org_admin': 'Organization Administrator', 
            'center_admin': 'Center Administrator',
            'coach': 'Coach',
            'student': 'Student'
        }
        return role_names.get(self.role, 'Unknown Role') 