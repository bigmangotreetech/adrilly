from datetime import datetime
from bson import ObjectId

class Rubric:
    """Rubric model for defining progress criteria per sport"""
    
    def __init__(self, name, organization_id, sport, criteria=None, 
                 scoring_scale=None, description=None):
        self.name = name
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.sport = sport
        self.criteria = criteria or []  # List of criteria with weights
        self.scoring_scale = scoring_scale or {'min': 1, 'max': 10}
        self.description = description
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # Default criteria for common sports if none provided
        if not self.criteria:
            self.criteria = self._get_default_criteria(sport)
    
    def _get_default_criteria(self, sport):
        """Get default criteria based on sport"""
        defaults = {
            'football': [
                {'name': 'Dribbling', 'weight': 20, 'description': 'Ball control and dribbling skills'},
                {'name': 'Passing', 'weight': 20, 'description': 'Accuracy and technique in passing'},
                {'name': 'Shooting', 'weight': 20, 'description': 'Goal scoring ability'},
                {'name': 'Defense', 'weight': 20, 'description': 'Defensive positioning and tackling'},
                {'name': 'Physical Fitness', 'weight': 20, 'description': 'Stamina and physical condition'}
            ],
            'basketball': [
                {'name': 'Shooting', 'weight': 25, 'description': 'Field goal and free throw accuracy'},
                {'name': 'Dribbling', 'weight': 20, 'description': 'Ball handling skills'},
                {'name': 'Passing', 'weight': 20, 'description': 'Assist and team play'},
                {'name': 'Defense', 'weight': 20, 'description': 'Defensive stance and rebounding'},
                {'name': 'Game IQ', 'weight': 15, 'description': 'Court awareness and decision making'}
            ],
            'tennis': [
                {'name': 'Forehand', 'weight': 20, 'description': 'Forehand stroke technique'},
                {'name': 'Backhand', 'weight': 20, 'description': 'Backhand stroke technique'},
                {'name': 'Serve', 'weight': 25, 'description': 'Serving power and accuracy'},
                {'name': 'Volley', 'weight': 15, 'description': 'Net play and volleys'},
                {'name': 'Footwork', 'weight': 20, 'description': 'Court movement and positioning'}
            ]
        }
        return defaults.get(sport.lower(), [
            {'name': 'Technique', 'weight': 30, 'description': 'Technical skills'},
            {'name': 'Physical', 'weight': 30, 'description': 'Physical attributes'},
            {'name': 'Mental', 'weight': 20, 'description': 'Mental strength'},
            {'name': 'Tactical', 'weight': 20, 'description': 'Game understanding'}
        ])
    
    def to_dict(self):
        """Convert rubric to dictionary"""
        data = {
            'name': self.name,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'sport': self.sport,
            'criteria': self.criteria,
            'scoring_scale': self.scoring_scale,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create rubric from dictionary"""
        rubric = cls(
            name=data['name'],
            organization_id=data.get('organization_id'),
            sport=data['sport'],
            criteria=data.get('criteria', []),
            scoring_scale=data.get('scoring_scale'),
            description=data.get('description')
        )
        
        # Set additional attributes
        if '_id' in data:
            rubric._id = data['_id']
        if 'is_active' in data:
            rubric.is_active = data['is_active']
        if 'created_at' in data:
            rubric.created_at = data['created_at']
        if 'updated_at' in data:
            rubric.updated_at = data['updated_at']
        
        return rubric

class Progress:
    """Progress model for tracking student improvement"""
    
    def __init__(self, student_id, rubric_id, evaluator_id, scores=None, 
                 notes=None, assessment_date=None):
        self.student_id = ObjectId(student_id) if student_id else None
        self.rubric_id = ObjectId(rubric_id) if rubric_id else None
        self.evaluator_id = ObjectId(evaluator_id) if evaluator_id else None  # Coach who evaluated
        self.scores = scores or {}  # {criteria_name: score}
        self.notes = notes
        self.assessment_date = assessment_date or datetime.utcnow()
        self.overall_score = self._calculate_overall_score()
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.class_id = None  # Optional: link to specific class
    
    def _calculate_overall_score(self):
        """Calculate weighted overall score"""
        if not self.scores:
            return 0
        
        # This would need rubric data to calculate properly
        # For now, return simple average
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0
    
    def to_dict(self):
        """Convert progress to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'student_id': str(self.student_id) if self.student_id else None,
            'rubric_id': str(self.rubric_id) if self.rubric_id else None,
            'evaluator_id': str(self.evaluator_id) if self.evaluator_id else None,
            'scores': self.scores,
            'notes': self.notes,
            'assessment_date': self.assessment_date,
            'overall_score': round(self.overall_score, 2),
            'class_id': str(self.class_id) if self.class_id else None,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create progress from dictionary"""
        progress = cls(
            student_id=data.get('student_id'),
            rubric_id=data.get('rubric_id'),
            evaluator_id=data.get('evaluator_id'),
            scores=data.get('scores', {}),
            notes=data.get('notes'),
            assessment_date=data.get('assessment_date')
        )
        
        # Set additional attributes
        if '_id' in data:
            progress._id = data['_id']
        if 'overall_score' in data:
            progress.overall_score = data['overall_score']
        if 'class_id' in data:
            progress.class_id = ObjectId(data['class_id']) if data['class_id'] else None
        if 'created_at' in data:
            progress.created_at = data['created_at']
        if 'updated_at' in data:
            progress.updated_at = data['updated_at']
        
        return progress
    
    def update_scores(self, new_scores, evaluator_id=None):
        """Update progress scores"""
        self.scores.update(new_scores)
        self.overall_score = self._calculate_overall_score()
        self.updated_at = datetime.utcnow()
        
        if evaluator_id:
            self.evaluator_id = ObjectId(evaluator_id)

class ProgressSummary:
    """Summary model for student progress over time"""
    
    def __init__(self, student_id, rubric_id, period_start, period_end,
                 assessments_count=0, latest_score=0, first_score=0,
                 improvement=0, trend_data=None):
        self.student_id = ObjectId(student_id) if student_id else None
        self.rubric_id = ObjectId(rubric_id) if rubric_id else None
        self.period_start = period_start
        self.period_end = period_end
        self.assessments_count = assessments_count
        self.latest_score = latest_score
        self.first_score = first_score
        self.improvement = improvement
        self.trend_data = trend_data or []  # [{date, score}, ...]
        self.created_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert progress summary to dictionary"""
        return {
            'student_id': str(self.student_id) if self.student_id else None,
            'rubric_id': str(self.rubric_id) if self.rubric_id else None,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'assessments_count': self.assessments_count,
            'latest_score': round(self.latest_score, 2),
            'first_score': round(self.first_score, 2),
            'improvement': round(self.improvement, 2),
            'trend_data': self.trend_data,
            'created_at': self.created_at
        } 