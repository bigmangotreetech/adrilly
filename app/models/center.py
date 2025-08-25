from datetime import datetime
from bson import ObjectId

class Center:
    """Center/Location model for training facilities"""
    
    def __init__(self, name, organization_id, address=None, contact_info=None, 
                 facilities=None, capacity=None, operating_hours=None, 
                 coaches=None, created_by=None):
        self.name = name
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.address = address or {}  # Complete address information
        self.contact_info = contact_info or {}  # Phone, email for this center
        self.facilities = facilities or []  # List of available facilities (fields, courts, etc.)
        self.capacity = capacity or {}  # Capacity information (max students, etc.)
        self.operating_hours = operating_hours or {}  # Operating hours by day
        self.coaches = coaches or []  # List of coach IDs associated with this center
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.created_by = ObjectId(created_by) if created_by else None
        
        # Additional fields
        self.description = None
        self.amenities = []  # Parking, WiFi, Changing rooms, etc.
        self.images = []  # URLs to center images
        self.banner_url = None  # Center banner image
        self.logo_url = None  # Center logo image
        self.location_coordinates = None  # Latitude, longitude if available
    
    def to_dict(self):
        """Convert center to dictionary"""
        data = {
            'name': self.name,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'address': self.address,
            'contact_info': self.contact_info,
            'facilities': self.facilities,
            'capacity': self.capacity,
            'operating_hours': self.operating_hours,
            'coaches': [str(coach_id) for coach_id in self.coaches],
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': str(self.created_by) if self.created_by else None,
            'description': self.description,
            'amenities': self.amenities,
            'images': self.images,
            'banner_url': self.banner_url,
            'logo_url': self.logo_url,
            'location_coordinates': self.location_coordinates
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create center from dictionary"""
        center = cls(
            name=data['name'],
            organization_id=data.get('organization_id'),
            address=data.get('address', {}),
            contact_info=data.get('contact_info', {}),
            facilities=data.get('facilities', []),
            capacity=data.get('capacity', {}),
            operating_hours=data.get('operating_hours', {}),
            coaches=[ObjectId(coach_id) for coach_id in data.get('coaches', [])],
            created_by=data.get('created_by')
        )
        
        # Set additional fields
        center.is_active = data.get('is_active', True)
        center.created_at = data.get('created_at', datetime.utcnow())
        center.updated_at = data.get('updated_at', datetime.utcnow())
        center.description = data.get('description')
        center.amenities = data.get('amenities', [])
        center.images = data.get('images', [])
        center.location_coordinates = data.get('location_coordinates')
        
        if '_id' in data:
            center._id = ObjectId(data['_id'])
        
        return center
    
    def add_coach(self, coach_id):
        """Add a coach to this center"""
        coach_id = ObjectId(coach_id) if coach_id else None
        if coach_id and coach_id not in self.coaches:
            self.coaches.append(coach_id)
            self.updated_at = datetime.utcnow()
    
    def remove_coach(self, coach_id):
        """Remove a coach from this center"""
        coach_id = ObjectId(coach_id) if coach_id else None
        if coach_id in self.coaches:
            self.coaches.remove(coach_id)
            self.updated_at = datetime.utcnow()
    
    def is_coach_assigned(self, coach_id):
        """Check if a coach is assigned to this center"""
        coach_id = ObjectId(coach_id) if coach_id else None
        return coach_id in self.coaches
    
    def get_operating_hours_for_day(self, day):
        """Get operating hours for a specific day"""
        return self.operating_hours.get(day.lower(), {})
    
    def is_open_at_time(self, day, time):
        """Check if center is open at a specific day and time"""
        hours = self.get_operating_hours_for_day(day)
        if not hours or not hours.get('open_time') or not hours.get('close_time'):
            return False
        
        # Simple time comparison (assumes 24-hour format HH:MM)
        open_time = hours['open_time']
        close_time = hours['close_time']
        
        return open_time <= time <= close_time
    
    def update_info(self, **kwargs):
        """Update center information"""
        updatable_fields = [
            'name', 'address', 'contact_info', 'facilities', 'capacity',
            'operating_hours', 'description', 'amenities', 'location_coordinates'
        ]
        
        for field, value in kwargs.items():
            if field in updatable_fields:
                setattr(self, field, value)
        
        self.updated_at = datetime.utcnow()


class Facility:
    """Individual facility within a center (e.g., Football Field 1, Basketball Court A)"""
    
    def __init__(self, name, facility_type, capacity=None, amenities=None, 
                 booking_rules=None, hourly_rate=None):
        self.name = name
        self.facility_type = facility_type  # 'football_field', 'basketball_court', 'swimming_pool', etc.
        self.capacity = capacity or {}  # Max students, spectators, etc.
        self.amenities = amenities or []  # Lighting, sound system, etc.
        self.booking_rules = booking_rules or {}  # Minimum booking time, advance notice, etc.
        self.hourly_rate = hourly_rate  # Cost per hour if applicable
        self.is_active = True
        self.maintenance_schedule = []  # List of maintenance periods
    
    def to_dict(self):
        """Convert facility to dictionary"""
        return {
            'name': self.name,
            'facility_type': self.facility_type,
            'capacity': self.capacity,
            'amenities': self.amenities,
            'booking_rules': self.booking_rules,
            'hourly_rate': self.hourly_rate,
            'is_active': self.is_active,
            'maintenance_schedule': self.maintenance_schedule
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create facility from dictionary"""
        facility = cls(
            name=data['name'],
            facility_type=data['facility_type'],
            capacity=data.get('capacity', {}),
            amenities=data.get('amenities', []),
            booking_rules=data.get('booking_rules', {}),
            hourly_rate=data.get('hourly_rate')
        )
        
        facility.is_active = data.get('is_active', True)
        facility.maintenance_schedule = data.get('maintenance_schedule', [])
        
        return facility 