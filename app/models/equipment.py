from datetime import datetime
from bson import ObjectId

class Equipment:
    """Equipment model for marketplace listings"""
    
    def __init__(self, title, description, price, owner_id, organization_id=None,
                 category=None, condition=None, images=None, contact_info=None, 
                 location=None, negotiable=True):
        self.title = title
        self.description = description
        self.price = float(price)
        self.owner_id = ObjectId(owner_id) if owner_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.category = category  # 'balls', 'equipment', 'apparel', 'accessories'
        self.condition = condition or 'good'  # 'new', 'excellent', 'good', 'fair', 'poor'
        self.images = images or []  # List of image URLs
        self.contact_info = contact_info or {}
        self.status = 'available'  # 'available', 'sold', 'reserved', 'inactive'
        self.location = location
        self.tags = []  # For search and categorization
        self.views_count = 0
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.featured = False
        self.negotiable = negotiable
    
    def to_dict(self):
        """Convert equipment to dictionary"""
        data = {
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'owner_id': str(self.owner_id) if self.owner_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'category': self.category,
            'condition': self.condition,
            'images': self.images,
            'contact_info': self.contact_info,
            'status': self.status,
            'location': self.location,
            'tags': self.tags,
            'views_count': self.views_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'featured': self.featured,
            'negotiable': self.negotiable
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create equipment from dictionary"""
        equipment = cls(
            title=data['title'],
            description=data['description'],
            price=data['price'],
            owner_id=data.get('owner_id'),
            organization_id=data.get('organization_id'),
            category=data.get('category'),
            condition=data.get('condition'),
            images=data.get('images', []),
            contact_info=data.get('contact_info', {})
        )
        
        # Set additional attributes
        if '_id' in data:
            equipment._id = data['_id']
        if 'status' in data:
            equipment.status = data['status']
        if 'location' in data:
            equipment.location = data['location']
        if 'tags' in data:
            equipment.tags = data['tags']
        if 'views_count' in data:
            equipment.views_count = data['views_count']
        if 'created_at' in data:
            equipment.created_at = data['created_at']
        if 'updated_at' in data:
            equipment.updated_at = data['updated_at']
        if 'featured' in data:
            equipment.featured = data['featured']
        if 'negotiable' in data:
            equipment.negotiable = data['negotiable']
        
        return equipment
    
    def mark_sold(self):
        """Mark equipment as sold"""
        self.status = 'sold'
        self.updated_at = datetime.utcnow()
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        # Note: In a real application, you might want to update this
        # directly in the database without updating the updated_at field
    
    def add_tag(self, tag):
        """Add a tag to the equipment"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def remove_tag(self, tag):
        """Remove a tag from the equipment"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()

class EquipmentCategory:
    """Equipment category model for organizing marketplace"""
    
    def __init__(self, name, description=None, parent_category_id=None,
                 organization_id=None):
        self.name = name
        self.description = description
        self.parent_category_id = ObjectId(parent_category_id) if parent_category_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.is_active = True
        self.sort_order = 0
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert category to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'name': self.name,
            'description': self.description,
            'parent_category_id': str(self.parent_category_id) if self.parent_category_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create category from dictionary"""
        category = cls(
            name=data['name'],
            description=data.get('description'),
            parent_category_id=data.get('parent_category_id'),
            organization_id=data.get('organization_id')
        )
        
        # Set additional attributes
        if '_id' in data:
            category._id = data['_id']
        if 'is_active' in data:
            category.is_active = data['is_active']
        if 'sort_order' in data:
            category.sort_order = data['sort_order']
        if 'created_at' in data:
            category.created_at = data['created_at']
        if 'updated_at' in data:
            category.updated_at = data['updated_at']
        
        return category 