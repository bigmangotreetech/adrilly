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
    
    def __init__(self, phone_number, name, email=None, role='student', password=None, 
                 organization_id=None, organization_ids=None, groups=None, profile_data=None, created_by=None, billing_start_date=None,
                 subscription_ids=None, parent_id=None, age=None, gender=None):
        self.phone_number = self._normalize_phone_number(phone_number) if phone_number else ''
        self.name = name
        self.email = email
        self.role = role
        self.password_hash = generate_password_hash(password) if password else None
        
        # Support both single organization_id (backward compatibility) and multiple organization_ids
        if organization_ids is not None:
            # If organization_ids is provided, use it
            if isinstance(organization_ids, list):
                self.organization_ids = [ObjectId(oid) if oid and not isinstance(oid, ObjectId) else oid for oid in organization_ids if oid]
            else:
                self.organization_ids = [ObjectId(organization_ids)] if organization_ids else []
        elif organization_id is not None:
            # If only organization_id provided, create list with single org
            self.organization_ids = [ObjectId(organization_id)] if organization_id else []
        else:
            self.organization_ids = []
        
        # Keep organization_id for backward compatibility (points to first/primary org)
        self.organization_id = self.organization_ids[0] if self.organization_ids else None
        
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
        self.first_name = ''
        self.last_name = ''

        self.subscription_ids = [ObjectId(sid) for sid in subscription_ids] if subscription_ids else []
        
        # Profile picture
        self.profile_picture_url = None
        
        # Billing information
        self.billing_start_date = billing_start_date
        
        # Child profile fields
        self.parent_id = ObjectId(parent_id) if parent_id else None
        self.age = age
        self.gender = gender
        
        # Botle Coins (1 coin = 1 rupee) - rewards/points system
        self.botle_coins = 0
        
        # Achievements (for coaches and admins)
        self.achievements = []
        
        # Multi-tenant specific fields
        self.can_create_organizations = (role in ['super_admin'])
        self.can_manage_organization = (role in ['super_admin', 'org_admin'])
        self.can_manage_coaches = (role in ['super_admin', 'org_admin', 'center_admin'])
        self.can_manage_students = (role in ['super_admin', 'org_admin', 'center_admin', 'coach'])
        
        # Organization-specific permissions
        self.permissions = self._get_default_permissions(role)
    
    def _normalize_phone_number(self, phone_number):
        """Normalize phone number format for consistency"""
        # Remove all non-digit characters including + and -
        print(phone_number)
        cleaned = re.sub(r'[^\d\+]', '', phone_number)
        cleaned = cleaned.replace('+91', '')
        cleaned = cleaned.replace('+1', '')
        cleaned = cleaned.replace('+', '')
        
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
        
        if not self.organization_ids:
            return False
        
        # Check if target_org_id is in user's organization_ids
        target_org_str = str(target_org_id) if target_org_id else None
        return any(str(org_id) == target_org_str for org_id in self.organization_ids)
    
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
        elif self.organization_ids:
            return [str(org_id) for org_id in self.organization_ids]
        else:
            return []
    
    def add_organization(self, organization_id):
        """Add user to an organization"""
        org_id = ObjectId(organization_id) if organization_id and not isinstance(organization_id, ObjectId) else organization_id
        if org_id and org_id not in self.organization_ids:
            self.organization_ids.append(org_id)
            # Update primary organization_id if this is the first one
            if not self.organization_id:
                self.organization_id = org_id
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_organization(self, organization_id):
        """Remove user from an organization"""
        org_id = ObjectId(organization_id) if organization_id and not isinstance(organization_id, ObjectId) else organization_id
        if org_id in self.organization_ids:
            self.organization_ids.remove(org_id)
            # Update primary organization_id if it was removed
            if self.organization_id == org_id:
                self.organization_id = self.organization_ids[0] if self.organization_ids else None
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def set_primary_organization(self, organization_id):
        """Set the primary organization for the user"""
        org_id = ObjectId(organization_id) if organization_id and not isinstance(organization_id, ObjectId) else organization_id
        if org_id in self.organization_ids:
            # Move it to the front of the list
            self.organization_ids = [org_id] + [oid for oid in self.organization_ids if oid != org_id]
            self.organization_id = org_id
            self.updated_at = datetime.utcnow()
            return True
        return False
    
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
            'organization_id': self.organization_id if self.organization_id else None,  # Backward compatibility
            'organization_ids': [str(org_id) for org_id in self.organization_ids] if self.organization_ids else [],  # New field
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
            'billing_start_date': self.billing_start_date,
            'subscription_ids': [str(sid) for sid in self.subscription_ids] if self.subscription_ids else [],
            'parent_id': str(self.parent_id) if self.parent_id else None,
            'age': self.age,
            'gender': self.gender,
            'botle_coins': self.botle_coins,
            'achievements': self.achievements
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
        # Handle both organization_ids (new) and organization_id (backward compatibility)
        org_ids = data.get('organization_ids')
        org_id = data.get('organization_id')
        
        user = cls(
            phone_number=data['phone_number'],
            name=data['name'],
            role=data.get('role', 'student'),
            organization_ids=org_ids,  # Use organization_ids if available
            organization_id=org_id if not org_ids else None,  # Fallback to organization_id
            groups=data.get('groups', []),
            profile_data=data.get('profile_data', {}),
            created_by=data.get('created_by'),
            subscription_ids=data.get('subscription_ids', []),
            parent_id=data.get('parent_id'),
            age=data.get('age'),
            gender=data.get('gender')
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
        if 'profile_picture_url' in data:
            user.profile_picture_url = data['profile_picture_url']
        if 'parent_id' in data and data['parent_id']:
            user.parent_id = ObjectId(data['parent_id']) if isinstance(data['parent_id'], str) else data['parent_id']
        if 'age' in data:
            user.age = data['age']
        if 'gender' in data:
            user.gender = data['gender']
        if 'botle_coins' in data:
            user.botle_coins = data['botle_coins']
        else:
            # Default to 0 for existing users without botle_coins
            user.botle_coins = 0
        if 'achievements' in data:
            user.achievements = data['achievements']
        else:
            user.achievements = []
        
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