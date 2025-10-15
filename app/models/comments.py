from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, List

class Comment:
    """
    Comment model for storing user comments on posts and other content.
    """
    def __init__(self,
                 _id: ObjectId,
                 content: str,
                 user_id: ObjectId,
                 organization_id: ObjectId,
                 target_type: str,  # 'post', 'class', 'progress', etc.
                 target_id: ObjectId,
                 status: str = 'active',  # 'active', 'hidden', 'deleted'
                 parent_id: Optional[ObjectId] = None,  # for nested comments
                 mentions: Optional[List[ObjectId]] = None,  # mentioned user IDs
                 attachments: Optional[List[Dict]] = None,
                 likes_count: int = 0,
                 replies_count: int = 0,
                 edited: bool = False,
                 edited_at: Optional[datetime] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.content = content
        self.user_id = user_id
        self.organization_id = organization_id
        self.target_type = target_type
        self.target_id = target_id
        self.status = status
        self.parent_id = parent_id
        self.mentions = mentions or []
        self.attachments = attachments or []
        self.likes_count = likes_count
        self.replies_count = replies_count
        self.edited = edited
        self.edited_at = edited_at
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Comment':
        return cls(
            _id=data.get('_id'),
            content=data.get('content'),
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id'),
            target_type=data.get('target_type'),
            target_id=data.get('target_id'),
            status=data.get('status', 'active'),
            parent_id=data.get('parent_id'),
            mentions=data.get('mentions'),
            attachments=data.get('attachments'),
            likes_count=data.get('likes_count', 0),
            replies_count=data.get('replies_count', 0),
            edited=data.get('edited', False),
            edited_at=data.get('edited_at'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'content': self.content,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'status': self.status,
            'parent_id': self.parent_id,
            'mentions': self.mentions,
            'attachments': self.attachments,
            'likes_count': self.likes_count,
            'replies_count': self.replies_count,
            'edited': self.edited,
            'edited_at': self.edited_at,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
