from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict

class ClassPicture:
    """
    ClassPicture model for storing images taken during classes.
    """
    def __init__(self,
                 _id: ObjectId,
                 class_id: ObjectId,
                 organization_id: ObjectId,
                 uploaded_by: ObjectId,
                 file_url: str,
                 file_type: str,  # 'image/jpeg', 'image/png', etc.
                 file_size: int,  # in bytes
                 status: str = 'active',  # 'active', 'deleted'
                 caption: Optional[str] = None,
                 tags: Optional[list[str]] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.class_id = class_id
        self.organization_id = organization_id
        self.uploaded_by = uploaded_by
        self.file_url = file_url
        self.file_type = file_type
        self.file_size = file_size
        self.status = status
        self.caption = caption
        self.tags = tags or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'ClassPicture':
        return cls(
            _id=data.get('_id'),
            class_id=data.get('class_id'),
            organization_id=data.get('organization_id'),
            uploaded_by=data.get('uploaded_by'),
            file_url=data.get('file_url'),
            file_type=data.get('file_type'),
            file_size=data.get('file_size'),
            status=data.get('status', 'active'),
            caption=data.get('caption'),
            tags=data.get('tags'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'class_id': self.class_id,
            'organization_id': self.organization_id,
            'uploaded_by': self.uploaded_by,
            'file_url': self.file_url,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'status': self.status,
            'caption': self.caption,
            'tags': self.tags,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
