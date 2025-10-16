from datetime import datetime
from bson import ObjectId
import re

class Lead:
    """Lead model for contact form submissions"""
    
    def __init__(self, name, email, phone, center_name, city, notes=None):
        self.name = name
        self.email = email
        self.phone = self._normalize_phone_number(phone) if phone else ''
        self.center_name = center_name
        self.city = city
        self.notes = notes or ''
        self.status = 'new'  # 'new', 'contacted', 'converted', 'closed'
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.contacted_at = None
        self.converted_at = None
    
    def _normalize_phone_number(self, phone_number):
        """Normalize phone number format for consistency"""
        # Remove all non-digit characters
        cleaned = re.sub(r'[^\d\+]', '', phone_number)
        cleaned = cleaned.replace('+91', '')
        cleaned = cleaned.replace('+1', '')
        cleaned = cleaned.replace('+', '')
        return cleaned
    
    def to_dict(self):
        """Convert lead to dictionary"""
        lead_dict = {
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'center_name': self.center_name,
            'city': self.city,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'contacted_at': self.contacted_at,
            'converted_at': self.converted_at
        }
        
        # Only include _id if it exists
        if hasattr(self, '_id') and self._id is not None:
            lead_dict['_id'] = str(self._id)
        
        return lead_dict
    
    @classmethod
    def from_dict(cls, data):
        """Create lead from dictionary"""
        lead = cls(
            name=data['name'],
            email=data['email'],
            phone=data['phone'],
            center_name=data['center_name'],
            city=data['city'],
            notes=data.get('notes', '')
        )
        
        # Set additional attributes if they exist
        if '_id' in data:
            lead._id = data['_id']
        if 'status' in data:
            lead.status = data['status']
        if 'created_at' in data:
            lead.created_at = data['created_at']
        if 'updated_at' in data:
            lead.updated_at = data['updated_at']
        if 'contacted_at' in data:
            lead.contacted_at = data['contacted_at']
        if 'converted_at' in data:
            lead.converted_at = data['converted_at']
        
        return lead
    
    @staticmethod
    def validate_name(name):
        """Validate name format"""
        if not name or len(name.strip()) == 0:
            return False, "Name is required"
        
        trimmed_name = name.strip()
        
        if len(trimmed_name) < 2:
            return False, "Name must be at least 2 characters long"
        
        if len(trimmed_name) > 100:
            return False, "Name is too long (max 100 characters)"
        
        # Only allow letters, spaces, hyphens, apostrophes, and periods
        pattern = r'^[a-zA-Z\s\-\'.]+$'
        if not re.match(pattern, trimmed_name):
            return False, "Name can only contain letters, spaces, hyphens, apostrophes, and periods"
        
        return True, "Valid name"
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email or len(email.strip()) == 0:
            return False, "Email is required"
        
        trimmed_email = email.strip()
        
        # Comprehensive email regex pattern (RFC 5322 compliant)
        pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        if not re.match(pattern, trimmed_email):
            return False, "Please enter a valid email address (e.g., name@example.com)"
        
        if len(trimmed_email) > 254:  # RFC 5321 limit
            return False, "Email address is too long"
        
        return True, "Valid email"
    
    @staticmethod
    def validate_phone(phone):
        """Validate phone number format"""
        if not phone or len(phone.strip()) == 0:
            return False, "Phone number is required"
        
        trimmed_phone = phone.strip()
        
        # Check if input contains only valid phone characters
        valid_chars_pattern = r'^[\d\s\-\+\(\)]+$'
        if not re.match(valid_chars_pattern, trimmed_phone):
            return False, "Phone number can only contain digits, spaces, hyphens, parentheses, and plus sign"
        
        # Remove all non-digit characters for validation
        cleaned = re.sub(r'[^\d]', '', phone)
        
        if len(cleaned) == 0:
            return False, "Phone number must contain digits"
        
        # Should be between 10 and 15 digits
        if len(cleaned) < 10:
            return False, "Phone number must be at least 10 digits"
        
        if len(cleaned) > 15:
            return False, "Phone number is too long (max 15 digits)"
        
        return True, "Valid phone number"
    
    @staticmethod
    def validate_center_name(center_name):
        """Validate center name"""
        if not center_name or len(center_name.strip()) == 0:
            return False, "Center name is required"
        
        trimmed_name = center_name.strip()
        
        if len(trimmed_name) < 2:
            return False, "Center name must be at least 2 characters long"
        
        if len(trimmed_name) > 200:
            return False, "Center name is too long (max 200 characters)"
        
        # Allow letters, numbers, spaces, and common punctuation
        pattern = r'^[a-zA-Z0-9\s\-\'.&,()]+$'
        if not re.match(pattern, trimmed_name):
            return False, "Center name can only contain letters, numbers, spaces, and common punctuation"
        
        return True, "Valid center name"
    
    @staticmethod
    def validate_city(city):
        """Validate city"""
        if not city or len(city.strip()) == 0:
            return False, "City is required"
        
        trimmed_city = city.strip()
        
        if len(trimmed_city) < 2:
            return False, "City must be at least 2 characters long"
        
        if len(trimmed_city) > 100:
            return False, "City name is too long (max 100 characters)"
        
        # Only allow letters, spaces, hyphens, apostrophes, and periods (no numbers)
        pattern = r'^[a-zA-Z\s\-\'.]+$'
        if not re.match(pattern, trimmed_city):
            return False, "City name can only contain letters, spaces, hyphens, apostrophes, and periods"
        
        return True, "Valid city"
    
    def update_status(self, new_status):
        """Update lead status"""
        valid_statuses = ['new', 'contacted', 'converted', 'closed']
        if new_status not in valid_statuses:
            return False
        
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if new_status == 'contacted' and not self.contacted_at:
            self.contacted_at = datetime.utcnow()
        elif new_status == 'converted' and not self.converted_at:
            self.converted_at = datetime.utcnow()
        
        return True

