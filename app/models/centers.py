from datetime import datetime, time
from bson import ObjectId
from typing import Optional, List, Dict

class Center:
    """
    Center model representing physical locations or branches of an organization.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 organization_id: ObjectId,
                 type: str,  # 'main', 'branch'
                 status: str,  # 'active', 'inactive'
                 address: Dict[str, str],
                 contact_phone: str,
                 manager_id: Optional[ObjectId] = None,
                 capacity: Optional[int] = None,
                 facilities: Optional[List[str]] = None,
                 working_hours: Optional[Dict[str, Dict[str, time]]] = None,
                 location: Optional[Dict[str, float]] = None,  # {latitude: float, longitude: float}
                 description: Optional[str] = None,
                 images: Optional[List[str]] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.organization_id = organization_id
        self.type = type
        self.status = status
        self.address = address
        self.contact_phone = contact_phone
        self.manager_id = manager_id
        self.capacity = capacity
        self.facilities = facilities or []
        self.working_hours = working_hours or {}
        self.location = location or {}
        self.description = description
        self.images = images or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Center':
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            organization_id=data.get('organization_id'),
            type=data.get('type'),
            status=data.get('status'),
            address=data.get('address', {}),
            contact_phone=data.get('contact_phone'),
            manager_id=data.get('manager_id'),
            capacity=data.get('capacity'),
            facilities=data.get('facilities'),
            working_hours=data.get('working_hours'),
            location=data.get('location'),
            description=data.get('description'),
            images=data.get('images'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'name': self.name,
            'organization_id': self.organization_id,
            'type': self.type,
            'status': self.status,
            'address': self.address,
            'contact_phone': self.contact_phone,
            'manager_id': self.manager_id,
            'capacity': self.capacity,
            'facilities': self.facilities,
            'working_hours': self.working_hours,
            'location': self.location,
            'description': self.description,
            'images': self.images,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
