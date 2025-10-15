from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict
from decimal import Decimal

class Booking:
    """
    Booking model for tracking class reservations and one-time experiences.
    """
    def __init__(self,
                 _id: ObjectId,
                 class_id: ObjectId,
                 student_id: ObjectId,
                 organization_id: ObjectId,
                 status: str,  # 'pending', 'confirmed', 'cancelled', 'completed'
                 booking_type: str,  # 'regular', 'trial', 'one_time'
                 scheduled_at: datetime,
                 amount: Optional[Decimal] = None,
                 payment_status: Optional[str] = None,
                 payment_id: Optional[ObjectId] = None,
                 cancellation_reason: Optional[str] = None,
                 cancellation_time: Optional[datetime] = None,
                 notes: Optional[str] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.class_id = class_id
        self.student_id = student_id
        self.organization_id = organization_id
        self.status = status
        self.booking_type = booking_type
        self.scheduled_at = scheduled_at
        self.amount = amount
        self.payment_status = payment_status
        self.payment_id = payment_id
        self.cancellation_reason = cancellation_reason
        self.cancellation_time = cancellation_time
        self.notes = notes
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Booking':
        amount = data.get('amount')
        if amount is not None:
            amount = Decimal(str(amount))
            
        return cls(
            _id=data.get('_id'),
            class_id=data.get('class_id'),
            student_id=data.get('student_id'),
            organization_id=data.get('organization_id'),
            status=data.get('status'),
            booking_type=data.get('booking_type'),
            scheduled_at=data.get('scheduled_at'),
            amount=amount,
            payment_status=data.get('payment_status'),
            payment_id=data.get('payment_id'),
            cancellation_reason=data.get('cancellation_reason'),
            cancellation_time=data.get('cancellation_time'),
            notes=data.get('notes'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'class_id': self.class_id,
            'student_id': self.student_id,
            'organization_id': self.organization_id,
            'status': self.status,
            'booking_type': self.booking_type,
            'scheduled_at': self.scheduled_at,
            'amount': str(self.amount) if self.amount else None,
            'payment_status': self.payment_status,
            'payment_id': self.payment_id,
            'cancellation_reason': self.cancellation_reason,
            'cancellation_time': self.cancellation_time,
            'notes': self.notes,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
