from datetime import datetime
from bson import ObjectId
from typing import Optional, List

class Activity:
    """
    Activity model representing user activities and interactions in the system.
    """
    def __init__(self,
                 _id: ObjectId,
                 user_id: ObjectId,
                 organization_id: ObjectId,
                 default_coach_id: Optional[ObjectId] = None,
                 action: str,
                 target_id: Optional[ObjectId] = None,
                 target_type: Optional[str] = None,
                 metadata: Optional[dict] = None,
                 created_at: datetime = None,
                 price: Optional[float] = None,
                 feedback_metrics: Optional[List[str]] = None):
        self._id = _id
        self.user_id = user_id
        self.organization_id = organization_id
        self.default_coach_id = default_coach_id
        self.action = action
        self.target_id = target_id
        self.target_type = target_type
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.price = price
        self.feedback_metrics = feedback_metrics or []

    @classmethod
    def from_dict(cls, data: dict) -> 'Activity':
        return cls(
            _id=data.get('_id'),
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id'),
            default_coach_id=data.get('default_coach_id'),
            action=data.get('action'),
            target_id=data.get('target_id'),
            target_type=data.get('target_type'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            price=data.get('price'),
            feedback_metrics=data.get('feedback_metrics', [])
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'default_coach_id': self.default_coach_id,
            'action': self.action,
            'target_id': self.target_id,
            'target_type': self.target_type,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'price': self.price,
            'feedback_metrics': self.feedback_metrics
        }
