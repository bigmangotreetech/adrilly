from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict
from decimal import Decimal
import razorpay
import os

class PaymentPlan:
    """
    Payment plan model for tracking all financial transactions in the system.
    """
    def __init__(self,
                 _id: Optional[ObjectId] = None,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 amount: Optional[Decimal] = None,
                 currency: str = 'INR'):
        self._id = _id
        self.name = name
        self.description = description
        self.amount = amount
        self.currency = currency

class Payment:
    """
    Payment model for tracking all financial transactions in the system.
    """
    PAYMENT_STATUSES = ['pending', 'completed', 'failed', 'refunded']
    PAYMENT_TYPES = ['class_fee', 'subscription', 'equipment_rental']
    PAYMENT_METHODS = ['cash', 'card', 'upi', 'netbanking']

    def __init__(self,
                 _id: Optional[ObjectId] = None,
                 organization_id: Optional[ObjectId] = None,
                 student_id: Optional[ObjectId] = None,
                 class_id: Optional[ObjectId] = None,
                 amount: Optional[Decimal] = None,
                 currency: str = 'INR',
                 status: str = 'pending',
                 payment_method: Optional[str] = None,
                 type: str = 'class_fee',
                 reference_id: Optional[str] = None,
                 description: Optional[str] = None,
                 metadata: Optional[Dict] = None,
                 transaction_id: Optional[str] = None,
                 payment_gateway: Optional[str] = None,
                 gateway_response: Optional[Dict] = None,
                 refund_details: Optional[Dict] = None,
                 created_by: Optional[ObjectId] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        
        self._id = _id
        self.organization_id = organization_id
        self.student_id = student_id
        self.class_id = class_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.payment_method = payment_method
        self.type = type
        self.reference_id = reference_id
        self.description = description
        self.metadata = metadata or {}
        self.transaction_id = transaction_id
        self.payment_gateway = payment_gateway
        self.gateway_response = gateway_response or {}
        self.refund_details = refund_details or {}
        self.created_by = created_by
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Payment':
        if not data:
            return None
            
        return cls(
            _id=data.get('_id'),
            organization_id=data.get('organization_id'),
            student_id=data.get('student_id'),
            class_id=data.get('class_id'),
            amount=Decimal(str(data.get('amount', '0'))),
            currency=data.get('currency', 'INR'),
            status=data.get('status', 'pending'),
            payment_method=data.get('payment_method'),
            type=data.get('type', 'class_fee'),
            reference_id=data.get('reference_id'),
            description=data.get('description'),
            metadata=data.get('metadata', {}),
            transaction_id=data.get('transaction_id'),
            payment_gateway=data.get('payment_gateway'),
            gateway_response=data.get('gateway_response', {}),
            refund_details=data.get('refund_details', {}),
            created_by=data.get('created_by'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'organization_id': self.organization_id,
            'student_id': self.student_id,
            'class_id': self.class_id,
            'amount': str(self.amount),
            'currency': self.currency,
            'status': self.status,
            'payment_method': self.payment_method,
            'type': self.type,
            'reference_id': self.reference_id,
            'description': self.description,
            'metadata': self.metadata,
            'transaction_id': self.transaction_id,
            'payment_gateway': self.payment_gateway,
            'gateway_response': self.gateway_response,
            'refund_details': self.refund_details,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    def mark_paid(self, amount: Optional[float] = None, payment_method: Optional[str] = None,
                 reference: Optional[str] = None, marked_by: Optional[str] = None,
                 notes: Optional[str] = None):
        """Mark a payment as paid with additional details"""
        self.status = 'completed'
        self.payment_method = payment_method
        self.reference_id = reference
        self.updated_at = datetime.utcnow()
        
        if amount:
            self.amount = Decimal(str(amount))
        
        if marked_by:
            self.metadata['marked_by'] = marked_by
            
        if notes:
            self.metadata['notes'] = notes

    @staticmethod
    def verify_razorpay_payment(payment_id: str, amount: Decimal) -> Dict:
        """Verify a Razorpay payment"""
        try:
            client = razorpay.Client(
                auth=(os.getenv('RAZORPAY_KEY_ID'), os.getenv('RAZORPAY_KEY_SECRET'))
            )
            
            # Fetch payment details from Razorpay
            payment_details = client.payment.fetch(payment_id)
            
            # Verify payment amount (amount in paise)
            expected_amount = int(amount * 100)
            if payment_details['amount'] != expected_amount:
                raise ValueError('Payment amount mismatch')
                
            if payment_details['status'] != 'captured':
                raise ValueError('Payment not captured')
                
            return payment_details
            
        except Exception as e:
            raise ValueError(f'Payment verification failed: {str(e)}')

    def record_razorpay_payment(self, payment_details: Dict):
        """Record Razorpay payment details"""
        self.payment_gateway = 'razorpay'
        self.transaction_id = payment_details['id']
        self.gateway_response = payment_details
        self.status = 'completed'
        self.payment_method = payment_details.get('method', 'online')
        self.updated_at = datetime.utcnow()