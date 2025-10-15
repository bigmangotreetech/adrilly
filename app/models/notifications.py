from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, List

class Notification:
    """
    Notification    model for managing user notifications and alerts.
    """
    def __init__(self,
                 _id: ObjectId,
                 user_id: ObjectId,
                 organization_id: ObjectId,
                 type: str,  # 'class_reminder', 'announcement', 'mention', etc.
                 title: str,
                 message: str,
                 status: str = 'unread',  # 'unread', 'read', 'archived'
                 priority: str = 'normal',  # 'low', 'normal', 'high', 'urgent'
                 action_url: Optional[str] = None,
                 action_text: Optional[str] = None,
                 target_type: Optional[str] = None,  # 'class', 'post', 'comment', etc.
                 target_id: Optional[ObjectId] = None,
                 channels: Optional[List[str]] = None,  # 'in_app', 'email', 'sms', 'whatsapp'
                 delivery_status: Optional[Dict[str, str]] = None,  # {'email': 'sent', 'sms': 'failed'}
                 scheduled_for: Optional[datetime] = None,
                 expires_at: Optional[datetime] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.user_id = user_id
        self.organization_id = organization_id
        self.type = type
        self.title = title
        self.message = message
        self.status = status
        self.priority = priority
        self.action_url = action_url
        self.action_text = action_text
        self.target_type = target_type
        self.target_id = target_id
        self.channels = channels or ['in_app']
        self.delivery_status = delivery_status or {}
        self.scheduled_for = scheduled_for
        self.expires_at = expires_at
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @classmethod
    def from_dict(cls, data: dict) -> 'Notification':
        return cls(
            _id=data.get('_id'),
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id'),
            type=data.get('type'),
            title=data.get('title'),
            message=data.get('message'),
            status=data.get('status', 'unread'),
            priority=data.get('priority', 'normal'),
            action_url=data.get('action_url'),
            action_text=data.get('action_text'),
            target_type=data.get('target_type'),
            target_id=data.get('target_id'),
            channels=data.get('channels'),
            delivery_status=data.get('delivery_status'),
            scheduled_for=data.get('scheduled_for'),
            expires_at=data.get('expires_at'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'status': self.status,
            'priority': self.priority,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'channels': self.channels,
            'delivery_status': self.delivery_status,
            'scheduled_for': self.scheduled_for,
            'expires_at': self.expires_at,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
