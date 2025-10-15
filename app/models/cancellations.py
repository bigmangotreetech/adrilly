from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict
from decimal import Decimal

class Cancellation:
    """
    Cancellation model for tracking cancelled classes and refunds.
    """
    def __init__(self,
                 _id: ObjectId,
                 class_id: ObjectId,
                 organization_id: ObjectId,
                 cancelled_by: ObjectId,  # user_id who cancelled
                 reason: str,
                 type: str,  # 'class', 'booking', 'subscription'
                 status: str,  # 'pending', 'processed', 'refunded'
                 scheduled_at: datetime,  # original scheduled time
                 cancelled_at: datetime = None,
                 refund_amount: Optional[Decimal] = None,
                 refund_status: Optional[str] = None,
                 refund_id: Optional[ObjectId] = None,
                 affected_students: Optional[list[ObjectId]] = None,
                 notification_sent: bool = False,
                 rescheduled_to: Optional[datetime] = None,
                 notes: Optional[str] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.class_id = class_id
        self.organization_id = organization_id
        self.cancelled_by = cancelled_by
        self.reason = reason
        self.type = type
        self.status = status
        self.scheduled_at = scheduled_at
        self.cancelled_at = cancelled_at or datetime.utcnow()
        self.refund_amount = refund_amount
        self.refund_status = refund_status
        self.refund_id = refund_id
        self.affected_students = affected_students or []
        self.notification_sent = notification_sent
        self.rescheduled_to = rescheduled_to
        self.notes = notes
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Cancellation':
        refund_amount = data.get('refund_amount')
        if refund_amount is not None:
            refund_amount = Decimal(str(refund_amount))
            
        return cls(
            _id=data.get('_id'),
            class_id=data.get('class_id'),
            organization_id=data.get('organization_id'),
            cancelled_by=data.get('cancelled_by'),
            reason=data.get('reason'),
            type=data.get('type'),
            status=data.get('status'),
            scheduled_at=data.get('scheduled_at'),
            cancelled_at=data.get('cancelled_at'),
            refund_amount=refund_amount,
            refund_status=data.get('refund_status'),
            refund_id=data.get('refund_id'),
            affected_students=data.get('affected_students'),
            notification_sent=data.get('notification_sent', False),
            rescheduled_to=data.get('rescheduled_to'),
            notes=data.get('notes'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'class_id': self.class_id,
            'organization_id': self.organization_id,
            'cancelled_by': self.cancelled_by,
            'reason': self.reason,
            'type': self.type,
            'status': self.status,
            'scheduled_at': self.scheduled_at,
            'cancelled_at': self.cancelled_at,
            'refund_amount': str(self.refund_amount) if self.refund_amount else None,
            'refund_status': self.refund_status,
            'refund_id': self.refund_id,
            'affected_students': self.affected_students,
            'notification_sent': self.notification_sent,
            'rescheduled_to': self.rescheduled_to,
            'notes': self.notes,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
