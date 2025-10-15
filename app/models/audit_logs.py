from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, Any

class AuditLog:
    """
    Audit log model for tracking important system events and changes.
    """
    def __init__(self,
                 _id: ObjectId,
                 action: str,  # 'create', 'update', 'delete', 'login', etc.
                 entity_type: str,  # 'user', 'class', 'payment', etc.
                 entity_id: ObjectId,
                 user_id: ObjectId,
                 organization_id: Optional[ObjectId] = None,
                 changes: Optional[Dict[str, Dict[str, Any]]] = None,  # {'field': {'old': value, 'new': value}}
                 ip_address: Optional[str] = None,
                 user_agent: Optional[str] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None):
        self._id = _id
        self.action = action
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.user_id = user_id
        self.organization_id = organization_id
        self.changes = changes or {}
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'AuditLog':
        return cls(
            _id=data.get('_id'),
            action=data.get('action'),
            entity_type=data.get('entity_type'),
            entity_id=data.get('entity_id'),
            user_id=data.get('user_id'),
            organization_id=data.get('organization_id'),
            changes=data.get('changes'),
            ip_address=data.get('ip_address'),
            user_agent=data.get('user_agent'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'changes': self.changes,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'metadata': self.metadata,
            'created_at': self.created_at
        }
