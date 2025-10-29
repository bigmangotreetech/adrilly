from datetime import datetime
from bson import ObjectId
from typing import Optional

class CoinTransaction:
    """
    Model for tracking Botle Coin transactions
    Records all coin earnings and redemptions for audit trail
    """
    
    # Transaction types
    TYPE_EARNED = 'earned'
    TYPE_REDEEMED = 'redeemed'
    TYPE_AWARDED = 'awarded'  # Manual awards by admin
    TYPE_DEDUCTED = 'deducted'  # Manual deductions by admin
    
    # Earning reasons
    REASON_SELF_BOOKING = 'self_booking'  # +5 coins
    REASON_OTHER_BOOKING = 'other_booking'  # +15 coins
    REASON_WEEKLY_ATTENDANCE = 'weekly_attendance'  # +10 coins (4 classes in a week)
    REASON_MANUAL_AWARD = 'manual_award'
    REASON_CLASS_REDEMPTION = 'class_redemption'
    REASON_MANUAL_DEDUCTION = 'manual_deduction'
    
    def __init__(self, 
                 user_id: ObjectId,
                 amount: int,
                 transaction_type: str,
                 reason: str,
                 description: Optional[str] = None,
                 reference_id: Optional[ObjectId] = None,
                 reference_type: Optional[str] = None,
                 balance_before: int = 0,
                 balance_after: int = 0,
                 created_by: Optional[ObjectId] = None):
        """
        Initialize a coin transaction
        
        Args:
            user_id: User who owns the coins
            amount: Number of coins (positive for earn, negative for spend)
            transaction_type: TYPE_EARNED, TYPE_REDEEMED, etc.
            reason: Specific reason code
            description: Human-readable description
            reference_id: Related object ID (class_id, booking_id, etc.)
            reference_type: Type of reference (class, booking, etc.)
            balance_before: Coin balance before transaction
            balance_after: Coin balance after transaction
            created_by: User who created the transaction (for manual awards)
        """
        self.user_id = ObjectId(user_id) if user_id else None
        self.amount = amount
        self.transaction_type = transaction_type
        self.reason = reason
        self.description = description or self._generate_description(reason, amount)
        self.reference_id = ObjectId(reference_id) if reference_id else None
        self.reference_type = reference_type
        self.balance_before = balance_before
        self.balance_after = balance_after
        self.created_by = ObjectId(created_by) if created_by else None
        self.created_at = datetime.utcnow()
    
    def _generate_description(self, reason: str, amount: int) -> str:
        """Generate human-readable description based on reason"""
        descriptions = {
            self.REASON_SELF_BOOKING: f'Booked a class (+{amount} coins)',
            self.REASON_OTHER_BOOKING: f'Helped someone book a class (+{amount} coins)',
            self.REASON_WEEKLY_ATTENDANCE: f'Attended 4 classes this week (+{amount} coins)',
            self.REASON_MANUAL_AWARD: f'Manual award (+{amount} coins)',
            self.REASON_CLASS_REDEMPTION: f'Redeemed coins for class booking (-{abs(amount)} coins)',
            self.REASON_MANUAL_DEDUCTION: f'Manual deduction (-{abs(amount)} coins)',
        }
        return descriptions.get(reason, f'Coin transaction ({amount} coins)')
    
    def to_dict(self) -> dict:
        """Convert transaction to dictionary"""
        transaction_dict = {
            'user_id': str(self.user_id) if self.user_id else None,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'reason': self.reason,
            'description': self.description,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'created_at': self.created_at,
        }
        
        if self.reference_id:
            transaction_dict['reference_id'] = str(self.reference_id)
        if self.reference_type:
            transaction_dict['reference_type'] = self.reference_type
        if self.created_by:
            transaction_dict['created_by'] = str(self.created_by)
        
        # Include _id if it exists
        if hasattr(self, '_id') and self._id is not None:
            transaction_dict['_id'] = str(self._id)
        
        return transaction_dict
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CoinTransaction':
        """Create transaction from dictionary"""
        transaction = cls(
            user_id=data['user_id'],
            amount=data['amount'],
            transaction_type=data['transaction_type'],
            reason=data['reason'],
            description=data.get('description'),
            reference_id=data.get('reference_id'),
            reference_type=data.get('reference_type'),
            balance_before=data.get('balance_before', 0),
            balance_after=data.get('balance_after', 0),
            created_by=data.get('created_by'),
        )
        
        if '_id' in data:
            transaction._id = data['_id']
        if 'created_at' in data:
            transaction.created_at = data['created_at']
        
        return transaction

