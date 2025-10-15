from datetime import datetime
from bson import ObjectId
from typing import Dict, Optional

class Feedback:
    """
    Feedback model for storing student feedback on classes
    """
    def __init__(self,
                 class_id: ObjectId,
                 student_id: ObjectId,
                 coach_id: ObjectId,
                 activity_id: ObjectId,
                 organization_id: ObjectId,
                 metrics: Dict[str, int],  # metric_name: rating (1-5)
                 notes: Optional[str] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self.class_id = class_id
        self.student_id = student_id
        self.coach_id = coach_id
        self.activity_id = activity_id
        self.organization_id = organization_id
        self.metrics = metrics  # e.g., {"Technique": 4, "Effort": 5, "Teamwork": 3}
        self.notes = notes
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Feedback':
        """Create feedback from dictionary"""
        return cls(
            class_id=ObjectId(data['class_id']) if isinstance(data.get('class_id'), str) else data.get('class_id'),
            student_id=ObjectId(data['student_id']) if isinstance(data.get('student_id'), str) else data.get('student_id'),
            coach_id=ObjectId(data['coach_id']) if isinstance(data.get('coach_id'), str) else data.get('coach_id'),
            activity_id=ObjectId(data['activity_id']) if isinstance(data.get('activity_id'), str) else data.get('activity_id'),
            organization_id=ObjectId(data['organization_id']) if isinstance(data.get('organization_id'), str) else data.get('organization_id'),
            metrics=data.get('metrics', {}),
            notes=data.get('notes'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        """Convert feedback to dictionary"""
        data = {
            'class_id': str(self.class_id) if self.class_id else None,
            'student_id': str(self.student_id) if self.student_id else None,
            'coach_id': str(self.coach_id) if self.coach_id else None,
            'activity_id': str(self.activity_id) if self.activity_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'metrics': self.metrics,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    def update_metrics(self, metrics: Dict[str, int]):
        """Update feedback metrics"""
        self.metrics = metrics
        self.updated_at = datetime.utcnow()
    
    def update_notes(self, notes: str):
        """Update feedback notes"""
        self.notes = notes
        self.updated_at = datetime.utcnow()

