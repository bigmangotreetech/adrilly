from datetime import datetime
from bson import ObjectId

class OrgHoliday:
    """Organization Holiday model for managing organization-specific holiday associations"""
    
    def __init__(self, holiday_id, organization_id, is_active=True, 
                 custom_name=None, custom_description=None, affects_scheduling=True,
                 created_by=None, notes=None):
        """
        Initialize organization holiday association
        
        Args:
            holiday_id: Reference to master holiday in holidays collection
            organization_id: Organization that adopted this holiday
            is_active: Whether this holiday is active for the organization
            custom_name: Custom name override for the organization
            custom_description: Custom description override
            affects_scheduling: Whether to block scheduling on this day
            created_by: User who imported/created this association
            notes: Additional notes for the organization
        """
        self.holiday_id = ObjectId(holiday_id) if holiday_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.is_active = is_active
        self.custom_name = custom_name
        self.custom_description = custom_description
        self.affects_scheduling = affects_scheduling
        self.created_by = ObjectId(created_by) if created_by else None
        self.notes = notes
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.imported_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert org holiday to dictionary"""
        data = {
            'holiday_id': self.holiday_id,
            'organization_id': self.organization_id,
            'is_active': self.is_active,
            'custom_name': self.custom_name,
            'custom_description': self.custom_description,
            'affects_scheduling': self.affects_scheduling,
            'created_by': self.created_by,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'imported_at': self.imported_at
        }
        
        # Include _id if it exists
        if hasattr(self, '_id'):
            data['_id'] = self._id
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create org holiday from dictionary"""
        org_holiday = cls(
            holiday_id=data['holiday_id'],
            organization_id=data['organization_id'],
            is_active=data.get('is_active', True),
            custom_name=data.get('custom_name'),
            custom_description=data.get('custom_description'),
            affects_scheduling=data.get('affects_scheduling', True),
            created_by=data.get('created_by'),
            notes=data.get('notes')
        )
        
        # Set additional attributes
        if '_id' in data:
            org_holiday._id = data['_id']
        if 'created_at' in data:
            org_holiday.created_at = data['created_at']
        if 'updated_at' in data:
            org_holiday.updated_at = data['updated_at']
        if 'imported_at' in data:
            org_holiday.imported_at = data['imported_at']
        
        return org_holiday
    
    def update(self, **kwargs):
        """Update org holiday fields"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        
    def deactivate(self):
        """Deactivate this holiday for the organization"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
        
    def activate(self):
        """Activate this holiday for the organization"""
        self.is_active = True
        self.updated_at = datetime.utcnow()
