from datetime import datetime
from bson import ObjectId
from typing import Optional, List, Dict

class ActivityLink:
    """
    Model for storing shareable activity/class links
    """
    def __init__(self,
                 _id: ObjectId,
                 schedule_item_ids: List[str],
                 organization_id: ObjectId,
                 created_by: ObjectId,
                 link_token: str,
                 status: str = 'active',  # 'active', 'expired', 'disabled'
                 expires_at: Optional[datetime] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.schedule_item_ids = schedule_item_ids
        self.organization_id = organization_id
        self.created_by = created_by
        self.link_token = link_token
        self.status = status
        self.expires_at = expires_at
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'ActivityLink':
        return cls(
            _id=data.get('_id'),
            schedule_item_ids=data.get('schedule_item_ids', []),
            organization_id=data.get('organization_id'),
            created_by=data.get('created_by'),
            link_token=data.get('link_token'),
            status=data.get('status', 'active'),
            expires_at=data.get('expires_at'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': str(self._id) if self._id else None,
            'schedule_item_ids': self.schedule_item_ids,
            'organization_id': str(self.organization_id),
            'created_by': str(self.created_by),
            'link_token': self.link_token,
            'status': self.status,
            'expires_at': self.expires_at,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
