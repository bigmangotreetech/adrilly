from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, List
from decimal import Decimal

class Equipment:
    """
    Equipment model for tracking sports and training equipment inventory.
    """
    def __init__(self,
                 _id: ObjectId,
                 name: str,
                 organization_id: ObjectId,
                 type: str,  # 'sports', 'training', 'safety', etc.
                 status: str,  # 'available', 'in_use', 'maintenance', 'retired'
                 quantity: int,
                 center_id: Optional[ObjectId] = None,
                 description: Optional[str] = None,
                 specifications: Optional[Dict] = None,
                 condition: Optional[str] = None,
                 purchase_date: Optional[datetime] = None,
                 purchase_price: Optional[Decimal] = None,
                 rental_price: Optional[Decimal] = None,
                 maintenance_history: Optional[List[Dict]] = None,
                 current_assignment: Optional[Dict] = None,
                 images: Optional[List[str]] = None,
                 metadata: Optional[Dict] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.name = name
        self.organization_id = organization_id
        self.type = type
        self.status = status
        self.quantity = quantity
        self.center_id = center_id
        self.description = description
        self.specifications = specifications or {}
        self.condition = condition
        self.purchase_date = purchase_date
        self.purchase_price = purchase_price
        self.rental_price = rental_price
        self.maintenance_history = maintenance_history or []
        self.current_assignment = current_assignment or {}
        self.images = images or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Equipment':
        purchase_price = data.get('purchase_price')
        if purchase_price is not None:
            purchase_price = Decimal(str(purchase_price))
            
        rental_price = data.get('rental_price')
        if rental_price is not None:
            rental_price = Decimal(str(rental_price))
            
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            organization_id=data.get('organization_id'),
            type=data.get('type'),
            status=data.get('status'),
            quantity=data.get('quantity'),
            center_id=data.get('center_id'),
            description=data.get('description'),
            specifications=data.get('specifications'),
            condition=data.get('condition'),
            purchase_date=data.get('purchase_date'),
            purchase_price=purchase_price,
            rental_price=rental_price,
            maintenance_history=data.get('maintenance_history'),
            current_assignment=data.get('current_assignment'),
            images=data.get('images'),
            metadata=data.get('metadata'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'name': self.name,
            'organization_id': self.organization_id,
            'type': self.type,
            'status': self.status,
            'quantity': self.quantity,
            'center_id': self.center_id,
            'description': self.description,
            'specifications': self.specifications,
            'condition': self.condition,
            'purchase_date': self.purchase_date,
            'purchase_price': str(self.purchase_price) if self.purchase_price else None,
            'rental_price': str(self.rental_price) if self.rental_price else None,
            'maintenance_history': self.maintenance_history,
            'current_assignment': self.current_assignment,
            'images': self.images,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }