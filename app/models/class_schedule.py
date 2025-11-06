from datetime import datetime
from bson import ObjectId

class Class:
    """Enhanced class model for scheduling training sessions with cancellation support"""
    
    def __init__(self, title, organization_id, coach_id, scheduled_at, 
                 duration_minutes=60, location=None, group_ids=None, 
                 student_ids=None, sport=None, level=None, notes=None,
                 schedule_item_id=None, price=0, is_bookable=True):
        self.title = title
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.coach_id = ObjectId(coach_id) if coach_id else None
        self.scheduled_at = scheduled_at
        self.duration_minutes = duration_minutes
        self.location = location or {}  # {'name': 'Field 1', 'address': '...'}
        self.group_ids = [ObjectId(gid) for gid in (group_ids or [])]
        self.student_ids = [ObjectId(sid) for sid in (student_ids or [])]
        self.sport = sport
        self.level = level
        self.notes = notes
        self.status = 'scheduled'  # 'scheduled', 'ongoing', 'completed', 'cancelled'
        self.max_students = None
        self.reminder_sent = False
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.recurring = None  # For future: recurring class settings
        self.schedule_item_id = ObjectId(schedule_item_id) if schedule_item_id else None  # ID of the schedule item that created this class
        self.price = price
        self.is_bookable = is_bookable  # Inherited from activity, default True
        # Enhanced cancellation fields
        self.cancellation_reason = None  # Reason for cancellation
        self.cancelled_by = None  # User ID who cancelled the class
        self.cancelled_at = None  # When the class was cancelled
        self.cancellation_type = None  # 'coach', 'weather', 'facility', 'holiday', 'emergency'
        self.replacement_class_id = None  # ID of replacement class if rescheduled
        self.notification_sent = False  # Whether cancellation notifications were sent
        self.refund_required = False  # Whether refund is needed
        self.refund_processed = False  # Whether refund has been processed
    
    def to_dict(self):
        """Convert class to dictionary"""
        data = {
            'title': self.title,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'coach_id': str(self.coach_id) if self.coach_id else None,
            'scheduled_at': self.scheduled_at,
            'duration_minutes': self.duration_minutes,
            'location': self.location,
            'group_ids': [str(gid) for gid in self.group_ids],
            'student_ids': [str(sid) for sid in self.student_ids],
            'sport': self.sport,
            'level': self.level,
            'notes': self.notes,
            'status': self.status,
            'max_students': self.max_students,
            'reminder_sent': self.reminder_sent,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'recurring': self.recurring,
            'schedule_item_id': str(self.schedule_item_id) if self.schedule_item_id else None,
            'price': self.price,
            'cancellation_reason': self.cancellation_reason,
            'cancelled_by': str(self.cancelled_by) if self.cancelled_by else None,
            'cancelled_at': self.cancelled_at,
            'cancellation_type': self.cancellation_type,
            'replacement_class_id': str(self.replacement_class_id) if self.replacement_class_id else None,
            'notification_sent': self.notification_sent,
            'refund_required': self.refund_required,
            'refund_processed': self.refund_processed,
            'is_bookable': self.is_bookable,
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create class from dictionary"""
        class_obj = cls(
            title=data['title'],
            organization_id=data.get('organization_id'),
            coach_id=data.get('coach_id'),
            scheduled_at=data['scheduled_at'],
            duration_minutes=data.get('duration_minutes', 60),
            location=data.get('location', {}),
            group_ids=data.get('group_ids', []),
            student_ids=data.get('student_ids', []),
            sport=data.get('sport'),
            level=data.get('level'),
            notes=data.get('notes'),
            schedule_item_id=data.get('schedule_item_id'),
            price=data.get('price', 0)
        )
        
        # Set additional attributes
        if '_id' in data:
            class_obj._id = data['_id']
        if 'status' in data:
            class_obj.status = data['status']
        if 'max_students' in data:
            class_obj.max_students = data['max_students']
        if 'reminder_sent' in data:
            class_obj.reminder_sent = data['reminder_sent']
        if 'created_at' in data:
            class_obj.created_at = data['created_at']
        if 'updated_at' in data:
            class_obj.updated_at = data['updated_at']
        if 'recurring' in data:
            class_obj.recurring = data['recurring']
        
        # Set cancellation attributes
        if 'cancellation_reason' in data:
            class_obj.cancellation_reason = data['cancellation_reason']
        if 'cancelled_by' in data:
            class_obj.cancelled_by = ObjectId(data['cancelled_by']) if data['cancelled_by'] else None
        if 'cancelled_at' in data:
            class_obj.cancelled_at = data['cancelled_at']
        if 'cancellation_type' in data:
            class_obj.cancellation_type = data['cancellation_type']
        if 'replacement_class_id' in data:
            class_obj.replacement_class_id = ObjectId(data['replacement_class_id']) if data['replacement_class_id'] else None
        if 'notification_sent' in data:
            class_obj.notification_sent = data['notification_sent']
        if 'refund_required' in data:
            class_obj.refund_required = data['refund_required']
        if 'refund_processed' in data:
            class_obj.refund_processed = data['refund_processed']
        if 'is_bookable' in data:
            class_obj.is_bookable = data['is_bookable']
        else:
            class_obj.is_bookable = True  # Default to True if not present
        return class_obj
    
    def get_all_student_ids(self):
        """Get all student IDs (direct + from groups)"""
        # This would need to be implemented in the service layer
        # to fetch group members and combine with direct student assignments
        return self.student_ids
    
    def is_past(self):
        """Check if class is in the past"""
        return self.scheduled_at < datetime.utcnow()
    
    def is_today(self):
        """Check if class is today"""
        today = datetime.utcnow().date()
        return self.scheduled_at.date() == today
    
    def cancel_class(self, reason, cancelled_by, cancellation_type='manual', refund_required=False):
        """Cancel the class with proper tracking"""
        self.status = 'cancelled'
        self.cancellation_reason = reason
        self.cancelled_by = ObjectId(cancelled_by) if cancelled_by else None
        self.cancelled_at = datetime.utcnow()
        self.cancellation_type = cancellation_type
        self.refund_required = refund_required
        self.updated_at = datetime.utcnow()
    
    def can_be_cancelled(self):
        """Check if class can be cancelled"""
        if self.status in ['completed', 'cancelled']:
            return False
        # Don't allow cancellation if class has already started
        if self.status == 'ongoing':
            return False
        return True
    
    def is_cancelled(self):
        """Check if class is cancelled"""
        return self.status == 'cancelled'
    
    def get_cancellation_notice_hours(self):
        """Get hours until class starts (for cancellation notice)"""
        if not self.scheduled_at:
            return 0
        time_diff = self.scheduled_at - datetime.utcnow()
        return max(0, time_diff.total_seconds() / 3600)
    
    def requires_short_notice_alert(self, min_hours=24):
        """Check if cancellation is happening with short notice"""
        return self.get_cancellation_notice_hours() < min_hours 