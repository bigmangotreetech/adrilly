from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.progress import Rubric, Progress, ProgressSummary
from app.routes.auth import require_role
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, timedelta
from bson import ObjectId

progress_bp = Blueprint('progress', __name__, url_prefix='/api/progress')

# Request schemas
class CreateRubricSchema(Schema):
    name = fields.Str(required=True)
    sport = fields.Str(required=True)
    criteria = fields.List(fields.Dict(), required=False)
    scoring_scale = fields.Dict(required=False)
    description = fields.Str(required=False)

class CreateProgressSchema(Schema):
    student_id = fields.Str(required=True)
    rubric_id = fields.Str(required=True)
    scores = fields.Dict(required=True)
    notes = fields.Str(required=False)
    assessment_date = fields.DateTime(required=False)

@progress_bp.route('/rubrics', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def create_rubric():
    """Create a new progress rubric"""
    try:
        schema = CreateRubricSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Create new rubric
        new_rubric = Rubric(
            name=data['name'],
            organization_id=organization_id,
            sport=data['sport'],
            criteria=data.get('criteria'),
            scoring_scale=data.get('scoring_scale'),
            description=data.get('description')
        )
        
        result = mongo.db.rubrics.insert_one(new_rubric.to_dict())
        new_rubric._id = result.inserted_id
        
        return jsonify({
            'message': 'Rubric created successfully',
            'rubric': new_rubric.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@progress_bp.route('/rubrics', methods=['GET'])
@jwt_required()
def get_rubrics():
    """Get all rubrics for the organization"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        sport = request.args.get('sport')
        query = {'organization_id': ObjectId(organization_id)}
        
        if sport:
            query['sport'] = sport
        
        rubrics_cursor = mongo.db.rubrics.find(query)
        rubrics = [Rubric.from_dict(rubric_data).to_dict() for rubric_data in rubrics_cursor]
        
        return jsonify({'rubrics': rubrics}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@progress_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def create_progress():
    """Create a new progress assessment"""
    try:
        schema = CreateProgressSchema()
        data = schema.load(request.json)
        
        user_id = get_jwt_identity()
        
        # Create new progress record
        new_progress = Progress(
            student_id=data['student_id'],
            rubric_id=data['rubric_id'],
            evaluator_id=user_id,
            scores=data['scores'],
            notes=data.get('notes'),
            assessment_date=data.get('assessment_date')
        )
        
        result = mongo.db.progress.insert_one(new_progress.to_dict())
        new_progress._id = result.inserted_id
        
        return jsonify({
            'message': 'Progress assessment created successfully',
            'progress': new_progress.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@progress_bp.route('/student/<student_id>', methods=['GET'])
@jwt_required()
def get_student_progress(student_id):
    """Get progress history for a student"""
    try:
        claims = get_jwt()
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        
        # Students can only view their own progress
        if user_role == 'student' and user_id != student_id:
            return jsonify({'error': 'Access denied'}), 403
        
        rubric_id = request.args.get('rubric_id')
        query = {'student_id': ObjectId(student_id)}
        
        if rubric_id:
            query['rubric_id'] = ObjectId(rubric_id)
        
        progress_records = list(mongo.db.progress.find(query).sort('assessment_date', -1))
        progress_data = [Progress.from_dict(record).to_dict() for record in progress_records]
        
        return jsonify({
            'progress': progress_data,
            'total': len(progress_data)
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 