from datetime import datetime
from bson import ObjectId
from typing import Optional, List, Dict

class User:
    """
    User model representing all users in the system (students, coaches, admins).
    """
    def __init__(self,
                 _id: ObjectId,
                 email: str,
                 phone_number: str,
                 name: str,
                 role: str,  # 'student', 'coach', 'admin', 'super_admin'
                 organization_id: Optional[ObjectId] = None,
                 status: str = 'active',  # 'active', 'inactive', 'suspended'
                 password_hash: Optional[str] = None,
                 profile_picture: Optional[str] = None,
                 address: Optional[Dict[str, str]] = None,
                 emergency_contact: Optional[Dict[str, str]] = None,
                 preferences: Optional[Dict] = None,
                 metadata: Optional[Dict] = None,
                 last_login: Optional[datetime] = None,
                 email_verified: bool = False,
                 phone_verified: bool = False,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.email = email
        self.phone_number = phone_number
        self.name = name
        self.role = role
        self.organization_id = organization_id
        self.status = status
        self.password_hash = password_hash
        self.profile_picture = profile_picture
        self.address = address or {}
        self.emergency_contact = emergency_contact or {}
        self.preferences = preferences or {}
        self.metadata = metadata or {}
        self.last_login = last_login
        self.email_verified = email_verified
        self.phone_verified = phone_verified
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @property
    def full_name(self) -> str:
        return self.name

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(
            _id=data.get('_id'),
            email=data.get('email'),
            phone_number=data.get('phone_number'),
            name=data.get('name'),
            role=data.get('role'),
            organization_id=data.get('organization_id'),
            status=data.get('status', 'active'),
            password_hash=data.get('password_hash'),
            profile_picture=data.get('profile_picture'),
            address=data.get('address'),
            emergency_contact=data.get('emergency_contact'),
            preferences=data.get('preferences'),
            metadata=data.get('metadata'),
            last_login=data.get('last_login'),
            email_verified=data.get('email_verified', False),
            phone_verified=data.get('phone_verified', False),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'email': self.email,
            'phone_number': self.phone_number,
            'name': self.name,
            'role': self.role,
            'organization_id': self.organization_id,
            'status': self.status,
            'password_hash': self.password_hash,
            'profile_picture': self.profile_picture,
            'address': self.address,
            'emergency_contact': self.emergency_contact,
            'preferences': self.preferences,
            'metadata': self.metadata,
            'last_login': self.last_login,
            'email_verified': self.email_verified,
            'phone_verified': self.phone_verified,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
