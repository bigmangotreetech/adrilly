from datetime import datetime
from bson import ObjectId
from typing import Optional, List, Dict

class Organization:
    """
    Organization model representing coaching centers or educational institutions.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 type: str,  # 'coaching_center', 'school', etc.
                 status: str,  # 'active', 'inactive', 'suspended'
                 contact_email: str,
                 contact_phone: str,
                 address: Dict[str, str],
                 admin_id: ObjectId,
                 subscription_plan: str,
                 subscription_status: str,
                 features_enabled: List[str],
                 settings: Optional[Dict] = None,
                 logo_url: Optional[str] = None,
                 website: Optional[str] = None,
                 social_links: Optional[Dict[str, str]] = None,
                 working_hours: Optional[Dict] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.type = type
        self.status = status
        self.contact_email = contact_email
        self.contact_phone = contact_phone
        self.address = address
        self.admin_id = admin_id
        self.subscription_plan = subscription_plan
        self.subscription_status = subscription_status
        self.features_enabled = features_enabled
        self.settings = settings or {}
        self.logo_url = logo_url
        self.website = website
        self.social_links = social_links or {}
        self.working_hours = working_hours or {}
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Organization':
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            type=data.get('type'),
            status=data.get('status'),
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone'),
            address=data.get('address', {}),
            admin_id=data.get('admin_id'),
            subscription_plan=data.get('subscription_plan'),
            subscription_status=data.get('subscription_status'),
            features_enabled=data.get('features_enabled', []),
            settings=data.get('settings'),
            logo_url=data.get('logo_url'),
            website=data.get('website'),
            social_links=data.get('social_links'),
            working_hours=data.get('working_hours'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'name': self.name,
            'type': self.type,
            'status': self.status,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'address': self.address,
            'admin_id': self.admin_id,
            'subscription_plan': self.subscription_plan,
            'subscription_status': self.subscription_status,
            'features_enabled': self.features_enabled,
            'settings': self.settings,
            'logo_url': self.logo_url,
            'website': self.website,
            'social_links': self.social_links,
            'working_hours': self.working_hours,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
