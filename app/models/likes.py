from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict

class Like:
    """
    Like model for tracking user likes on posts, comments, and other content.
    """
    def __init__(self,
                 _id: ObjectId,
                 user_id: ObjectId,
                 organization_id: ObjectId,
                 target_type: str,  # 'post', 'comment', 'progress'
                 target_id: ObjectId,
                 status: str = 'active',  # 'active', 'removed'
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.user_id = user_id
        self.organization_id = organization_id
        self.target_type = target_type
        self.target_id = target_id
        self.status = status
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Like':
        return cls(
            _id=data.get('_id'),
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id'),
            target_type=data.get('target_type'),
            target_id=data.get('target_id'),
            status=data.get('status', 'active'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'status': self.status,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
