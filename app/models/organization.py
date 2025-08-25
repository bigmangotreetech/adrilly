from datetime import datetime
from bson import ObjectId
import uuid
import secrets
import string

class Organization:
    """Organization model for coaching centers"""
    
    def __init__(self, name, owner_id, contact_info=None, address=None, 
                 activities=None, settings=None, logo_url=None, banner_url=None, 
                 whatsapp_number=None, description=None):
        self.name = name
        self.owner_id = ObjectId(owner_id) if owner_id else None
        self.contact_info = contact_info or {}
        self.address = address or {}
        self.activities = activities or []  # List of activities offered
        self.settings = settings or {}  # Custom settings and configurations
        
        # New fields for organization branding and contact
        self.logo_url = logo_url  # URL to organization logo
        self.banner_url = banner_url  # URL to organization banner
        self.whatsapp_number = whatsapp_number  # WhatsApp contact number
        self.description = description  # Organization description
        
        # Shareable link and verification fields
        self.signup_slug = self._generate_unique_slug()  # Unique URL slug for signup
        self.signup_token = self._generate_signup_token()  # Secure token for signup link
        self.center_code = self._generate_center_code()  # 6-digit verification code
        self.signup_enabled = True  # Whether signup is currently enabled
        self.max_signups_per_day = 50  # Rate limiting for signups
        self.signup_requires_approval = False  # Whether signups need admin approval
        
        # System fields
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.subscription_status = 'active'  # 'active', 'trial', 'expired'
        self.subscription_expires_at = None
    
    def _generate_unique_slug(self):
        """Generate a unique URL slug for the organization"""
        # Create a base slug from organization name (this will be set later)
        base_slug = uuid.uuid4().hex[:8]  # 8 character random slug
        return base_slug
    
    def _generate_signup_token(self):
        """Generate a secure token for signup links"""
        return secrets.token_urlsafe(32)  # 32-byte URL-safe token
    
    def _generate_center_code(self):
        """Generate a 6-digit verification code"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    def regenerate_signup_credentials(self):
        """Regenerate signup slug, token, and center code for security"""
        self.signup_slug = self._generate_unique_slug()
        self.signup_token = self._generate_signup_token()
        self.center_code = self._generate_center_code()
        self.updated_at = datetime.utcnow()
    
    def get_signup_url(self, base_url="https://adrilly.com"):
        """Get the complete signup URL for this organization"""
        return f"{base_url}/signup/{self.signup_slug}?token={self.signup_token}"
    
    def verify_signup_token(self, token):
        """Verify if the provided token matches the organization's signup token"""
        return secrets.compare_digest(self.signup_token, token)
    
    def verify_center_code(self, code):
        """Verify if the provided code matches the organization's center code"""
        return self.center_code == code.strip()
    
    def to_dict(self):
        """Convert organization to dictionary"""
        data = {
            'name': self.name,
            'owner_id': str(self.owner_id) if self.owner_id else None,
            'contact_info': self.contact_info,
            'address': self.address,
            'activities': self.activities,
            'settings': self.settings,
            'logo_url': self.logo_url,
            'banner_url': self.banner_url,
            'whatsapp_number': self.whatsapp_number,
            'description': self.description,
            'signup_slug': self.signup_slug,
            'signup_token': self.signup_token,
            'center_code': self.center_code,
            'signup_enabled': self.signup_enabled,
            'max_signups_per_day': self.max_signups_per_day,
            'signup_requires_approval': self.signup_requires_approval,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'subscription_status': self.subscription_status,
            'subscription_expires_at': self.subscription_expires_at
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create organization from dictionary"""
        org = cls(
            name=data['name'],
            owner_id=data.get('owner_id'),
            contact_info=data.get('contact_info', {}),
            address=data.get('address', {}),
            activities=data.get('activities', []),
            settings=data.get('settings', {}),
            logo_url=data.get('logo_url'),
            banner_url=data.get('banner_url'),
            whatsapp_number=data.get('whatsapp_number'),
            description=data.get('description')
        )
        
        # Set additional attributes
        if '_id' in data:
            org._id = data['_id']
        if 'signup_slug' in data:
            org.signup_slug = data['signup_slug']
        if 'signup_token' in data:
            org.signup_token = data['signup_token']
        if 'center_code' in data:
            org.center_code = data['center_code']
        if 'signup_enabled' in data:
            org.signup_enabled = data['signup_enabled']
        if 'max_signups_per_day' in data:
            org.max_signups_per_day = data['max_signups_per_day']
        if 'signup_requires_approval' in data:
            org.signup_requires_approval = data['signup_requires_approval']
        if 'is_active' in data:
            org.is_active = data['is_active']
        if 'created_at' in data:
            org.created_at = data['created_at']
        if 'updated_at' in data:
            org.updated_at = data['updated_at']
        if 'subscription_status' in data:
            org.subscription_status = data['subscription_status']
        if 'subscription_expires_at' in data:
            org.subscription_expires_at = data['subscription_expires_at']
        
        return org

class Group:
    """Group model for organizing students"""
    
    def __init__(self, name, organization_id, coach_id=None, sport=None, 
                 level=None, description=None, max_students=None):
        self.name = name
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.coach_id = ObjectId(coach_id) if coach_id else None
        self.sport = sport
        self.level = level  # 'beginner', 'intermediate', 'advanced'
        self.description = description
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.max_students = max_students
        self.current_students = 0
    
    def to_dict(self):
        """Convert group to dictionary"""
        data = {
            'name': self.name,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'coach_id': str(self.coach_id) if self.coach_id else None,
            'sport': self.sport,
            'level': self.level,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'max_students': self.max_students,
            'current_students': self.current_students
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create group from dictionary"""
        group = cls(
            name=data['name'],
            organization_id=data.get('organization_id'),
            coach_id=data.get('coach_id'),
            sport=data.get('sport'),
            level=data.get('level'),
            description=data.get('description')
        )
        
        # Set additional attributes
        if '_id' in data:
            group._id = data['_id']
        if 'is_active' in data:
            group.is_active = data['is_active']
        if 'created_at' in data:
            group.created_at = data['created_at']
        if 'updated_at' in data:
            group.updated_at = data['updated_at']
        if 'max_students' in data:
            group.max_students = data['max_students']
        if 'current_students' in data:
            group.current_students = data['current_students']
        
        return group 