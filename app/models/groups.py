from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, List

class Group:
    """
    Group model for managing student batches and training groups.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 organization_id: ObjectId,
                 type: str,  # 'batch', 'team', 'class_group'
                 status: str,  # 'active', 'inactive', 'archived'
                 coach_id: ObjectId,
                 center_id: Optional[ObjectId] = None,
                 description: Optional[str] = None,
                 max_students: Optional[int] = None,
                 level: Optional[str] = None,  # 'beginner', 'intermediate', 'advanced'
                 age_group: Optional[str] = None,
                 schedule_pattern: Optional[Dict] = None,
                 members: Optional[List[ObjectId]] = None,  # student IDs
                 equipment_required: Optional[List[str]] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.organization_id = organization_id
        self.type = type
        self.status = status
        self.coach_id = coach_id
        self.center_id = center_id
        self.description = description
        self.max_students = max_students
        self.level = level
        self.age_group = age_group
        self.schedule_pattern = schedule_pattern or {}
        self.members = members or []
        self.equipment_required = equipment_required or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @property
    def current_size(self) -> int:
        return len(self.members)

    @property
    def has_capacity(self) -> bool:
        if self.max_students is None:
            return True
        return len(self.members) < self.max_students

    @classmethod
    def from_dict(cls, data: dict) -> 'Group':
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            organization_id=data.get('organization_id'),
            type=data.get('type'),
            status=data.get('status'),
            coach_id=data.get('coach_id'),
            center_id=data.get('center_id'),
            description=data.get('description'),
            max_students=data.get('max_students'),
            level=data.get('level'),
            age_group=data.get('age_group'),
            schedule_pattern=data.get('schedule_pattern'),
            members=data.get('members'),
            equipment_required=data.get('equipment_required'),
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
            'coach_id': self.coach_id,
            'center_id': self.center_id,
            'description': self.description,
            'max_students': self.max_students,
            'level': self.level,
            'age_group': self.age_group,
            'schedule_pattern': self.schedule_pattern,
            'members': self.members,
            'equipment_required': self.equipment_required,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
