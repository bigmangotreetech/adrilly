from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional, List, Dict

class Class:
    """
    Class model representing scheduled classes in the coaching center.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 organization_id: ObjectId,
                 coach_id: ObjectId,
                 scheduled_at: datetime,
                 duration: int,  # in minutes
                 max_students: int,
                 type: str,  # 'regular', 'workshop', 'special'
                 status: str,  # 'scheduled', 'in_progress', 'completed', 'cancelled'
                 description: Optional[str] = None,
                 location: Optional[str] = None,
                 equipment_required: Optional[List[str]] = None,
                 metadata: Optional[Dict] = None,
                 recurring: bool = False,
                 recurring_pattern: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.organization_id = organization_id
        self.coach_id = coach_id
        self.scheduled_at = scheduled_at
        self.duration = duration
        self.max_students = max_students
        self.type = type
        self.status = status
        self.description = description
        self.location = location
        self.equipment_required = equipment_required or []
        self.metadata = metadata or {}
        self.recurring = recurring
        self.recurring_pattern = recurring_pattern or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @property
    def end_time(self) -> datetime:
        return self.scheduled_at + timedelta(minutes=self.duration)

    @classmethod
    def from_dict(cls, data: dict) -> 'Class':
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            organization_id=data.get('organization_id'),
            coach_id=data.get('coach_id'),
            scheduled_at=data.get('scheduled_at'),
            duration=data.get('duration'),
            max_students=data.get('max_students'),
            type=data.get('type'),
            status=data.get('status'),
            description=data.get('description'),
            location=data.get('location'),
            equipment_required=data.get('equipment_required'),
            metadata=data.get('metadata'),
            recurring=data.get('recurring', False),
            recurring_pattern=data.get('recurring_pattern'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'name': self.name,
            'organization_id': self.organization_id,
            'coach_id': self.coach_id,
            'scheduled_at': self.scheduled_at,
            'duration': self.duration,
            'max_students': self.max_students,
            'type': self.type,
            'status': self.status,
            'description': self.description,
            'location': self.location,
            'equipment_required': self.equipment_required,
            'metadata': self.metadata,
            'recurring': self.recurring,
            'recurring_pattern': self.recurring_pattern,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
