from datetime import datetime, date
from bson import ObjectId

class Holiday:
    """Holiday model for managing public holidays and organization closures"""
    
    def __init__(self, name, date_observed, organization_id=None, country_code='IN', 
                 is_public_holiday=True, description=None, affects_scheduling=True,
                 locations=None, holiday_types=None, source='manual', is_enabled=True, 
                 is_imported=False, api_data=None):
        self.name = name
        self.date_observed = date_observed if isinstance(date_observed, date) else date_observed.date()
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.country_code = country_code  # ISO country code
        self.is_public_holiday = is_public_holiday  # True for public holidays, False for org-specific
        self.description = description
        self.affects_scheduling = affects_scheduling  # Whether to block scheduling on this day
        self.locations = locations or 'All India'  # Geographic locations where holiday applies
        self.holiday_types = holiday_types or ['public']  # Types: national, local, religious, observance
        self.source = source  # Source: manual, calendarific_api, etc.
        self.is_enabled = is_enabled  # Whether holiday is currently enabled
        self.is_imported = is_imported  # Whether holiday was imported from external source
        self.api_data = api_data  # Store original API data for reference
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.imported_at = datetime.utcnow() if is_imported else None
        self.created_by = None  # User who added this holiday
        self.year = self.date_observed.year
        self.is_active = True
    
    def to_dict(self):
        """Convert holiday to dictionary"""
        data = {
            'name': self.name,
            'date_observed': self.date_observed,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'country_code': self.country_code,
            'is_public_holiday': self.is_public_holiday,
            'description': self.description,
            'affects_scheduling': self.affects_scheduling,
            'locations': self.locations,
            'holiday_types': self.holiday_types,
            'source': self.source,
            'is_enabled': self.is_enabled,
            'is_imported': self.is_imported,
            'api_data': self.api_data,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'imported_at': self.imported_at,
            'created_by': str(self.created_by) if self.created_by else None,
            'year': self.year,
            'is_active': self.is_active
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create holiday from dictionary"""
        holiday = cls(
            name=data['name'],
            date_observed=data['date_observed'],
            organization_id=data.get('organization_id'),
            country_code=data.get('country_code', 'IN'),
            is_public_holiday=data.get('is_public_holiday', True),
            description=data.get('description'),
            affects_scheduling=data.get('affects_scheduling', True),
            locations=data.get('locations', 'All India'),
            holiday_types=data.get('holiday_types', ['public']),
            source=data.get('source', 'manual'),
            is_enabled=data.get('is_enabled', True),
            is_imported=data.get('is_imported', False),
            api_data=data.get('api_data')
        )
        
        # Set additional attributes
        if '_id' in data:
            holiday._id = data['_id']
        if 'created_at' in data:
            holiday.created_at = data['created_at']
        if 'updated_at' in data:
            holiday.updated_at = data['updated_at']
        if 'imported_at' in data:
            holiday.imported_at = data['imported_at']
        if 'created_by' in data:
            holiday.created_by = ObjectId(data['created_by']) if data['created_by'] else None
        if 'year' in data:
            holiday.year = data['year']
        if 'is_active' in data:
            holiday.is_active = data['is_active']
        
        return holiday
    
    def is_today(self):
        """Check if holiday is today"""
        return self.date_observed == date.today()
    
    def is_this_year(self):
        """Check if holiday is in current year"""
        return self.year == date.today().year
    
    def days_until(self):
        """Get number of days until this holiday"""
        today = date.today()
        if self.date_observed < today:
            return 0
        return (self.date_observed - today).days
    
    def is_upcoming(self, days_ahead=30):
        """Check if holiday is upcoming within specified days"""
        days_until = self.days_until()
        return 0 < days_until <= days_ahead

class HolidayCalendar:
    """Helper class for managing holiday calendars and API integration"""
    
    # Common Indian public holidays (static data)
    INDIAN_HOLIDAYS_2024 = [
        {'name': 'New Year\'s Day', 'date': '2024-01-01', 'description': 'Start of the Gregorian calendar year'},
        {'name': 'Republic Day', 'date': '2024-01-26', 'description': 'Constitution Day of India'},
        {'name': 'Holi', 'date': '2024-03-25', 'description': 'Festival of Colors'},
        {'name': 'Good Friday', 'date': '2024-03-29', 'description': 'Christian holiday'},
        {'name': 'Ram Navami', 'date': '2024-04-17', 'description': 'Birth of Lord Rama'},
        {'name': 'Independence Day', 'date': '2024-08-15', 'description': 'Independence Day of India'},
        {'name': 'Krishna Janmashtami', 'date': '2024-08-26', 'description': 'Birth of Lord Krishna'},
        {'name': 'Gandhi Jayanti', 'date': '2024-10-02', 'description': 'Birthday of Mahatma Gandhi'},
        {'name': 'Dussehra', 'date': '2024-10-12', 'description': 'Victory of good over evil'},
        {'name': 'Diwali', 'date': '2024-11-01', 'description': 'Festival of Lights'},
        {'name': 'Christmas Day', 'date': '2024-12-25', 'description': 'Birth of Jesus Christ'},
    ]
    
    INDIAN_HOLIDAYS_2025 = [
        {'name': 'New Year\'s Day', 'date': '2025-01-01', 'description': 'Start of the Gregorian calendar year'},
        {'name': 'Republic Day', 'date': '2025-01-26', 'description': 'Constitution Day of India'},
        {'name': 'Holi', 'date': '2025-03-14', 'description': 'Festival of Colors'},
        {'name': 'Good Friday', 'date': '2025-04-18', 'description': 'Christian holiday'},
        {'name': 'Ram Navami', 'date': '2025-04-06', 'description': 'Birth of Lord Rama'},
        {'name': 'Independence Day', 'date': '2025-08-15', 'description': 'Independence Day of India'},
        {'name': 'Krishna Janmashtami', 'date': '2025-08-16', 'description': 'Birth of Lord Krishna'},
        {'name': 'Gandhi Jayanti', 'date': '2025-10-02', 'description': 'Birthday of Mahatma Gandhi'},
        {'name': 'Dussehra', 'date': '2025-10-02', 'description': 'Victory of good over evil'},
        {'name': 'Diwali', 'date': '2025-10-20', 'description': 'Festival of Lights'},
        {'name': 'Christmas Day', 'date': '2025-12-25', 'description': 'Birth of Jesus Christ'},
    ]
    
    @classmethod
    def get_holidays_for_year(cls, year, country_code='IN'):
        """Get holidays for a specific year and country"""
        if country_code == 'IN':
            if year == 2024:
                return cls.INDIAN_HOLIDAYS_2024
            elif year == 2025:
                return cls.INDIAN_HOLIDAYS_2025
        
        # For other countries or years, could integrate with holiday API
        return []
    
    @classmethod
    def import_holidays_for_organization(cls, organization_id, year, country_code='IN'):
        """Import public holidays for an organization"""
        from app.extensions import mongo
        
        holidays_data = cls.get_holidays_for_year(year, country_code)
        imported_holidays = []
        
        for holiday_data in holidays_data:
            holiday_date = datetime.strptime(holiday_data['date'], '%Y-%m-%d').date()
            
            # Check if holiday already exists
            existing = mongo.db.holidays.find_one({
                'organization_id': ObjectId(organization_id),
                'date_observed': holiday_date,
                'name': holiday_data['name']
            })
            
            if not existing:
                holiday = Holiday(
                    name=holiday_data['name'],
                    date_observed=holiday_date,
                    organization_id=organization_id,
                    country_code=country_code,
                    is_public_holiday=True,
                    description=holiday_data['description'],
                    affects_scheduling=True
                )
                
                result = mongo.db.holidays.insert_one(holiday.to_dict())
                holiday._id = result.inserted_id
                imported_holidays.append(holiday)
        
        return imported_holidays
    
    @classmethod
    def check_holiday_conflict(cls, organization_id, scheduled_date):
        """Check if a date conflicts with any holidays"""
        from app.extensions import mongo
        
        if isinstance(scheduled_date, datetime):
            scheduled_date = scheduled_date.date()
        
        holiday = mongo.db.holidays.find_one({
            'organization_id': ObjectId(organization_id),
            'date_observed': scheduled_date,
            'affects_scheduling': True,
            'is_active': True
        })
        
        if holiday:
            return Holiday.from_dict(holiday)
        
        return None
