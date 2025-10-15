from datetime import datetime, date
from bson import ObjectId
from typing import Optional, Dict

class Holiday:
    """
    Holiday model for tracking public holidays and their impact on schedules.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 date: date,
                 type: str,  # 'public', 'religious', 'local'
                 country: str = 'IN',
                 state: Optional[str] = None,
                 description: Optional[str] = None,
                 observance_rules: Optional[Dict] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.date = date
        self.type = type
        self.country = country
        self.state = state
        self.description = description
        self.observance_rules = observance_rules or {}
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Holiday':
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            date=data.get('date'),
            type=data.get('type'),
            country=data.get('country', 'IN'),
            state=data.get('state'),
            description=data.get('description'),
            observance_rules=data.get('observance_rules'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'name': self.name,
            'date': self.date,
            'type': self.type,
            'country': self.country,
            'state': self.state,
            'description': self.description,
            'observance_rules': self.observance_rules,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
