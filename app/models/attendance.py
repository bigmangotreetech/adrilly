from datetime import datetime, date
from bson import ObjectId
from typing import Optional, Dict, List
from dataclasses import dataclass

@dataclass
class AttendanceSummary:
    """
    Attendance summary model for aggregating attendance statistics.
    """
    total_students: int
    present_count: int
    absent_count: int
    late_count: int
    date: date
    organization_id: ObjectId
    class_id: Optional[ObjectId] = None
    coach_id: Optional[ObjectId] = None
    center_id: Optional[ObjectId] = None
    group_id: Optional[ObjectId] = None
    metadata: Optional[Dict] = None

    @property
    def attendance_rate(self) -> float:
        """Calculate attendance rate as percentage"""
        if self.total_students == 0:
            return 0.0
        return (self.present_count / self.total_students) * 100

    @property
    def absent_rate(self) -> float:
        """Calculate absence rate as percentage"""
        if self.total_students == 0:
            return 0.0
        return (self.absent_count / self.total_students) * 100

    @property
    def late_rate(self) -> float:
        """Calculate late arrival rate as percentage"""
        if self.total_students == 0:
            return 0.0
        return (self.late_count / self.total_students) * 100

    @classmethod
    def from_dict(cls, data: dict) -> 'AttendanceSummary':
        return cls(
            total_students=data.get('total_students', 0),
            present_count=data.get('present_count', 0),
            absent_count=data.get('absent_count', 0),
            late_count=data.get('late_count', 0),
            date=data.get('date'),
            organization_id=data.get('organization_id'),
            class_id=data.get('class_id'),
            coach_id=data.get('coach_id'),
            center_id=data.get('center_id'),
            group_id=data.get('group_id'),
            metadata=data.get('metadata')
        )

    def to_dict(self) -> dict:
        return {
            'total_students': self.total_students,
            'present_count': self.present_count,
            'absent_count': self.absent_count,
            'late_count': self.late_count,
            'date': self.date,
            'organization_id': self.organization_id,
            'class_id': self.class_id,
            'coach_id': self.coach_id,
            'center_id': self.center_id,
            'group_id': self.group_id,
            'metadata': self.metadata,
            'attendance_rate': self.attendance_rate,
            'absent_rate': self.absent_rate,
            'late_rate': self.late_rate
        }

    @staticmethod
    def aggregate_by_date(attendances: List['Attendance']) -> 'AttendanceSummary':
        """Create summary from a list of attendance records for a specific date"""
        if not attendances:
            return None
        
        first_record = attendances[0]
        present_count = sum(1 for a in attendances if a.status == 'present')
        late_count = sum(1 for a in attendances if a.status == 'late')
        absent_count = sum(1 for a in attendances if a.status == 'absent')
        
        return AttendanceSummary(
            total_students=len(attendances),
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            date=first_record.scheduled_at.date(),
            organization_id=first_record.organization_id,
            class_id=first_record.class_id,
            metadata={
                'generated_at': datetime.utcnow(),
                'source': 'attendance_records'
            }
        )

class Attendance:
    """
    Attendance model for tracking student attendance in classes.
    """
    def __init__(self,
                 _id: ObjectId,
                 class_id: ObjectId,
                 student_id: ObjectId,
                 organization_id: ObjectId,
                 status: str,  # 'present', 'absent', 'late'
                 scheduled_at: datetime,
                 checked_in_at: Optional[datetime] = None,
                 checked_in_by: Optional[ObjectId] = None,
                 notes: Optional[str] = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        self._id = _id
        self.class_id = class_id
        self.student_id = student_id
        self.organization_id = organization_id
        self.status = status
        self.scheduled_at = scheduled_at
        self.checked_in_at = checked_in_at
        self.checked_in_by = checked_in_by
        self.notes = notes
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def from_dict(cls, data: dict) -> 'Attendance':
        return cls(
            _id=data.get('_id'),
            class_id=data.get('class_id'),
            student_id=data.get('student_id'),
            organization_id=data.get('organization_id'),
            status=data.get('status'),
            scheduled_at=data.get('scheduled_at'),
            checked_in_at=data.get('checked_in_at'),
            checked_in_by=data.get('checked_in_by'),
            notes=data.get('notes'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self) -> dict:
        return {
            '_id': self._id,
            'class_id': self.class_id,
            'student_id': self.student_id,
            'organization_id': self.organization_id,
            'status': self.status,
            'scheduled_at': self.scheduled_at,
            'checked_in_at': self.checked_in_at,
            'checked_in_by': self.checked_in_by,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }