from datetime import datetime, timedelta
from bson import ObjectId
from typing import Dict, List, Optional
import uuid

class Attendance:
    """Enhanced attendance model for comprehensive tracking and analytics"""
    
    def __init__(self, class_id, student_id, status='pending', 
                 marked_by=None, notes=None, check_in_time=None):
        self.class_id = ObjectId(class_id) if class_id else None
        self.student_id = ObjectId(student_id) if student_id else None
        self.status = status  # 'pending', 'present', 'absent', 'late', 'excused', 'no_show'
        self.marked_by = ObjectId(marked_by) if marked_by else None  # Who marked attendance
        self.notes = notes
        self.check_in_time = check_in_time
        self.rsvp_response = None  # 'yes', 'no', 'maybe'
        self.rsvp_timestamp = None
        self.whatsapp_message_id = None  # For tracking WhatsApp responses
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # Enhanced tracking fields
        self.attendance_id = str(uuid.uuid4())  # Unique identifier
        self.check_out_time = None  # When student left
        self.actual_duration = None  # Minutes attended
        self.auto_marked = False  # Whether attendance was auto-marked
        self.verification_method = None  # 'manual', 'whatsapp_rsvp', 'qr_code', 'biometric'
        self.location_verified = False  # Whether location was verified
        self.coach_override = False  # Whether coach manually overrode
        self.participation_score = None  # 1-5 rating for class participation
        self.behavior_notes = None  # Behavioral observations
        self.late_arrival_minutes = 0  # How many minutes late
        self.early_departure_minutes = 0  # How many minutes early departure
        
        # Academic tracking
        self.skill_assessment = {}  # Dict of skill -> rating
        self.homework_completed = None  # Boolean for homework completion
        self.equipment_brought = None  # Boolean for required equipment
        self.dress_code_compliant = None  # Boolean for dress code
        
        # Health and safety
        self.health_check_passed = None  # Boolean for health screening
        self.temperature_recorded = None  # Float for temperature if recorded
        self.medical_notes = None  # Any medical observations
        
        # Analytics metadata
        self.weather_condition = None  # Weather during class
        self.class_size_that_day = 0  # Total students in class that day
        self.makeup_for_class_id = None  # If this is a makeup class
        
        # Communication tracking
        self.reminder_sent = False  # Whether reminder was sent
        self.reminder_response_time = None  # How quickly student responded
        self.follow_up_required = False  # Whether follow-up is needed
    
    def to_dict(self):
        """Convert attendance to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'class_id': str(self.class_id) if self.class_id else None,
            'student_id': str(self.student_id) if self.student_id else None,
            'status': self.status,
            'marked_by': str(self.marked_by) if self.marked_by else None,
            'notes': self.notes,
            'check_in_time': self.check_in_time,
            'rsvp_response': self.rsvp_response,
            'rsvp_timestamp': self.rsvp_timestamp,
            'whatsapp_message_id': self.whatsapp_message_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            
            # Enhanced fields
            'attendance_id': self.attendance_id,
            'check_out_time': self.check_out_time,
            'actual_duration': self.actual_duration,
            'auto_marked': self.auto_marked,
            'verification_method': self.verification_method,
            'location_verified': self.location_verified,
            'coach_override': self.coach_override,
            'participation_score': self.participation_score,
            'behavior_notes': self.behavior_notes,
            'late_arrival_minutes': self.late_arrival_minutes,
            'early_departure_minutes': self.early_departure_minutes,
            'skill_assessment': self.skill_assessment,
            'homework_completed': self.homework_completed,
            'equipment_brought': self.equipment_brought,
            'dress_code_compliant': self.dress_code_compliant,
            'health_check_passed': self.health_check_passed,
            'temperature_recorded': self.temperature_recorded,
            'medical_notes': self.medical_notes,
            'weather_condition': self.weather_condition,
            'class_size_that_day': self.class_size_that_day,
            'makeup_for_class_id': str(self.makeup_for_class_id) if self.makeup_for_class_id else None,
            'reminder_sent': self.reminder_sent,
            'reminder_response_time': self.reminder_response_time,
            'follow_up_required': self.follow_up_required
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create attendance from dictionary"""
        attendance = cls(
            class_id=data.get('class_id'),
            student_id=data.get('student_id'),
            status=data.get('status', 'pending'),
            marked_by=data.get('marked_by'),
            notes=data.get('notes'),
            check_in_time=data.get('check_in_time')
        )
        
        # Set additional attributes
        if '_id' in data:
            attendance._id = data['_id']
        if 'rsvp_response' in data:
            attendance.rsvp_response = data['rsvp_response']
        if 'rsvp_timestamp' in data:
            attendance.rsvp_timestamp = data['rsvp_timestamp']
        if 'whatsapp_message_id' in data:
            attendance.whatsapp_message_id = data['whatsapp_message_id']
        if 'created_at' in data:
            attendance.created_at = data['created_at']
        if 'updated_at' in data:
            attendance.updated_at = data['updated_at']
        
        return attendance
    
    def mark_present(self, marked_by=None, check_in_time=None):
        """Mark student as present"""
        self.status = 'present'
        self.marked_by = ObjectId(marked_by) if marked_by else None
        self.check_in_time = check_in_time or datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_absent(self, marked_by=None, notes=None):
        """Mark student as absent"""
        self.status = 'absent'
        self.marked_by = ObjectId(marked_by) if marked_by else None
        if notes:
            self.notes = notes
        self.updated_at = datetime.utcnow()
    
    def update_rsvp(self, response, message_id=None):
        """Update RSVP response from WhatsApp"""
        self.rsvp_response = response
        self.rsvp_timestamp = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        if message_id:
            self.whatsapp_message_id = message_id
        
        # Calculate response time if reminder was sent
        if self.reminder_sent and self.rsvp_timestamp:
            response_time = (self.rsvp_timestamp - self.created_at).total_seconds() / 60
            self.reminder_response_time = round(response_time, 2)
        
        # Auto-mark attendance based on RSVP
        if response == 'yes':
            self.status = 'present'
            self.auto_marked = True
            self.verification_method = 'whatsapp_rsvp'
        elif response == 'no':
            self.status = 'absent'
            self.auto_marked = True
            self.verification_method = 'whatsapp_rsvp'
        # 'maybe' keeps status as 'pending'
    
    def check_in_student(self, check_in_time: datetime = None, location_verified: bool = False,
                        temperature: float = None, health_check: bool = True) -> bool:
        """Enhanced check-in with health and location verification"""
        check_in_time = check_in_time or datetime.utcnow()
        self.check_in_time = check_in_time
        self.location_verified = location_verified
        self.health_check_passed = health_check
        self.temperature_recorded = temperature
        
        # Determine if student is late
        # This would require class start time - placeholder logic
        # self.late_arrival_minutes = calculate_late_minutes(check_in_time, class_start_time)
        
        if self.late_arrival_minutes > 0:
            self.status = 'late'
        else:
            self.status = 'present'
        
        self.verification_method = 'manual'
        self.updated_at = datetime.utcnow()
        return True
    
    def check_out_student(self, check_out_time: datetime = None):
        """Handle student check-out and calculate duration"""
        check_out_time = check_out_time or datetime.utcnow()
        self.check_out_time = check_out_time
        
        if self.check_in_time:
            duration = (check_out_time - self.check_in_time).total_seconds() / 60
            self.actual_duration = round(duration, 2)
        
        self.updated_at = datetime.utcnow()
    
    def add_skill_assessment(self, skill: str, rating: int, notes: str = None):
        """Add or update skill assessment for the student"""
        if not self.skill_assessment:
            self.skill_assessment = {}
        
        self.skill_assessment[skill] = {
            'rating': max(1, min(5, rating)),  # Ensure rating is 1-5
            'notes': notes,
            'assessed_at': datetime.utcnow()
        }
        self.updated_at = datetime.utcnow()
    
    def set_participation_score(self, score: int, behavior_notes: str = None):
        """Set participation score and behavior notes"""
        self.participation_score = max(1, min(5, score))  # Ensure score is 1-5
        if behavior_notes:
            self.behavior_notes = behavior_notes
        self.updated_at = datetime.utcnow()
    
    def mark_equipment_and_dress_code(self, equipment_brought: bool, dress_code_compliant: bool,
                                    homework_completed: bool = None):
        """Mark equipment, dress code, and homework completion"""
        self.equipment_brought = equipment_brought
        self.dress_code_compliant = dress_code_compliant
        if homework_completed is not None:
            self.homework_completed = homework_completed
        self.updated_at = datetime.utcnow()
    
    def override_attendance(self, new_status: str, marked_by: str, reason: str):
        """Allow coach to override attendance with reason"""
        old_status = self.status
        self.status = new_status
        self.marked_by = ObjectId(marked_by)
        self.coach_override = True
        
        # Add to notes
        override_note = f"Overridden from '{old_status}' to '{new_status}' by coach. Reason: {reason}"
        if self.notes:
            self.notes += f" | {override_note}"
        else:
            self.notes = override_note
        
        self.updated_at = datetime.utcnow()
    
    def mark_as_makeup(self, original_class_id: str):
        """Mark this attendance as a makeup for another class"""
        self.makeup_for_class_id = ObjectId(original_class_id)
        if self.notes:
            self.notes += f" | Makeup class for {original_class_id}"
        else:
            self.notes = f"Makeup class for {original_class_id}"
        self.updated_at = datetime.utcnow()
    
    def set_follow_up_required(self, required: bool, reason: str = None):
        """Mark if follow-up is required"""
        self.follow_up_required = required
        if required and reason:
            if self.notes:
                self.notes += f" | Follow-up required: {reason}"
            else:
                self.notes = f"Follow-up required: {reason}"
        self.updated_at = datetime.utcnow()
    
    def get_attendance_score(self) -> float:
        """Calculate overall attendance score based on various factors"""
        base_score = 0
        
        # Base attendance score
        if self.status == 'present':
            base_score = 100
        elif self.status == 'late':
            # Deduct points for being late
            late_penalty = min(50, self.late_arrival_minutes * 2)
            base_score = 100 - late_penalty
        elif self.status == 'excused':
            base_score = 75
        else:
            base_score = 0
        
        # Participation bonus
        if self.participation_score:
            participation_bonus = (self.participation_score - 3) * 5  # -10 to +10
            base_score += participation_bonus
        
        # Equipment and preparation bonus
        if self.equipment_brought:
            base_score += 5
        if self.dress_code_compliant:
            base_score += 5
        if self.homework_completed:
            base_score += 10
        
        # Early departure penalty
        if self.early_departure_minutes > 0:
            early_penalty = min(20, self.early_departure_minutes)
            base_score -= early_penalty
        
        return max(0, min(100, base_score))
    
    def is_at_risk(self) -> bool:
        """Determine if student is at risk based on attendance patterns"""
        # This would be enhanced with historical data analysis
        risk_factors = 0
        
        if self.status in ['absent', 'no_show']:
            risk_factors += 2
        if self.late_arrival_minutes > 15:
            risk_factors += 1
        if self.participation_score and self.participation_score < 3:
            risk_factors += 1
        if not self.equipment_brought:
            risk_factors += 1
        if not self.homework_completed:
            risk_factors += 1
        
        return risk_factors >= 3
    
    def get_summary_dict(self) -> Dict:
        """Get a summary dictionary for reporting"""
        return {
            'attendance_id': self.attendance_id,
            'status': self.status,
            'check_in_time': self.check_in_time,
            'check_out_time': self.check_out_time,
            'actual_duration': self.actual_duration,
            'late_arrival_minutes': self.late_arrival_minutes,
            'participation_score': self.participation_score,
            'attendance_score': self.get_attendance_score(),
            'auto_marked': self.auto_marked,
            'verification_method': self.verification_method,
            'rsvp_response': self.rsvp_response,
            'is_at_risk': self.is_at_risk(),
            'follow_up_required': self.follow_up_required
        }

class AttendanceSummary:
    """Summary model for attendance statistics"""
    
    def __init__(self, student_id, period_start, period_end, 
                 total_classes=0, present_count=0, absent_count=0, 
                 late_count=0, excused_count=0):
        self.student_id = ObjectId(student_id) if student_id else None
        self.period_start = period_start
        self.period_end = period_end
        self.total_classes = total_classes
        self.present_count = present_count
        self.absent_count = absent_count
        self.late_count = late_count
        self.excused_count = excused_count
        self.attendance_rate = (present_count / total_classes * 100) if total_classes > 0 else 0
        self.created_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert attendance summary to dictionary"""
        return {
            'student_id': str(self.student_id) if self.student_id else None,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'total_classes': self.total_classes,
            'present_count': self.present_count,
            'absent_count': self.absent_count,
            'late_count': self.late_count,
            'excused_count': self.excused_count,
            'attendance_rate': round(self.attendance_rate, 2),
            'created_at': self.created_at
        } 