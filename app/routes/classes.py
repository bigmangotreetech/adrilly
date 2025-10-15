from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from app.extensions import mongo
from app.models.class_schedule import Class
from app.models.user import User
from app.models.attendance import Attendance
from app.routes.auth import require_role
from marshmallow import Schema, fields, ValidationError
from datetime import datetime
from bson import ObjectId
from app.utils.auth import jwt_or_session_required, require_role_hybrid, get_current_user_info
from app.helpers.app_helper import get_user_info_from_session_or_claims
classes_bp = Blueprint('classes', __name__, url_prefix='/api/classes')



# Request schemas
class CreateClassSchema(Schema):
    title = fields.Str(required=True)
    coach_id = fields.Str(required=True)
    scheduled_at = fields.DateTime(required=True)
    duration_minutes = fields.Int(required=False, missing=60)
    location = fields.Dict(required=False)
    group_ids = fields.List(fields.Str(), required=False)
    student_ids = fields.List(fields.Str(), required=False)
    sport = fields.Str(required=False)
    level = fields.Str(required=False)
    notes = fields.Str(required=False)
    max_students = fields.Int(required=False)

class UpdateClassSchema(Schema):
    title = fields.Str(required=False)
    coach_id = fields.Str(required=False)
    scheduled_at = fields.DateTime(required=False)
    duration_minutes = fields.Int(required=False)
    location = fields.Dict(required=False)
    group_ids = fields.List(fields.Str(), required=False)
    student_ids = fields.List(fields.Str(), required=False)
    sport = fields.Str(required=False)
    level = fields.Str(required=False)
    notes = fields.Str(required=False)
    max_students = fields.Int(required=False)
    status = fields.Str(required=False, validate=lambda x: x in ['scheduled', 'ongoing', 'completed', 'cancelled'])

@classes_bp.route('', methods=['POST'])
@jwt_required()

def create_class():
    """Create a new class"""
    try:
        schema = CreateClassSchema()
        data = schema.load(request.json)
        
        # Get current user and organization
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        organization_id = user_info.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Create new class
        new_class = Class(
            title=data['title'],
            organization_id=ObjectId(organization_id),
            coach_id=ObjectId(data['coach_id']),
            scheduled_at=data['scheduled_at'],
            duration_minutes=data.get('duration_minutes', 60),
            location=data.get('location', {}),
            group_ids=[ObjectId(gid) for gid in data.get('group_ids', [])],
            student_ids=[ObjectId(sid) for sid in data.get('student_ids', [])],
            sport=data.get('sport'),
            level=data.get('level'),
            notes=data.get('notes')
        )
        
        if 'max_students' in data:
            new_class.max_students = data['max_students']
        
        result = mongo.db.classes.insert_one(new_class.to_dict())
        new_class._id = result.inserted_id
        
        return jsonify({
            'message': 'Class created successfully',
            'class': new_class.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('', methods=['GET'])
@jwt_or_session_required()
def get_classes():
    # """Get classes (filtered by user role and organization)"""
    # try:
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = user_info.get('role')
        user_id = user_info.get('user_id')
        organization_id = user_info.get('organization_id')
        
        # Build query based on user role
        query = {}
        
        if organization_id:
            query['organization_id'] = ObjectId(organization_id)
        
        if user_role == 'student':
            # Students can only see classes they're enrolled in
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if user_data:
                user_groups = user_data.get('groups', [])
                query['$or'] = [
                    {'student_ids': ObjectId(user_id)},
                    {'group_ids': {'$in': [ObjectId(gid) for gid in user_groups]}}
                ]
        elif user_role == 'coach':
            # Coaches can see classes they're assigned to
            query['coach_id'] = user_id
        # Admins can see all classes in their organization
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        sport = request.args.get('sport')
        
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query['scheduled_at'] = {'$gte': start_date}
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                if 'scheduled_at' in query:
                    query['scheduled_at']['$lte'] = end_date
                else:
                    query['scheduled_at'] = {'$lte': end_date}
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        if status:
            query['status'] = status
        
        if sport:
            query['sport'] = sport
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        # Execute query
        classes_cursor = mongo.db.classes.find(query).sort('scheduled_at', 1).skip(skip).limit(per_page)
        classes = [Class.from_dict(class_data).to_dict() for class_data in classes_cursor]
        
        for class_doc in classes:
            class_doc['_id'] = str(class_doc['_id'])
            if class_doc.get('coach_id'):
                class_doc['coach_id'] = str(class_doc['coach_id'])
            if class_doc.get('organization_id'):
                class_doc['organization_id'] = str(class_doc['organization_id'])
            if class_doc.get('student_ids'):
                class_doc['student_ids'] = [str(s) for s in class_doc['student_ids']]
            if class_doc['scheduled_at']:
                class_doc['scheduled_at'] = class_doc['scheduled_at'].isoformat()
            if class_doc['created_at']:
                class_doc['created_at'] = class_doc['created_at'].isoformat()
            if class_doc['updated_at']:
                class_doc['updated_at'] = class_doc['updated_at'].isoformat()
            if class_doc['cancelled_at']:
                class_doc['cancelled_at'] = class_doc['cancelled_at'].isoformat()
            if class_doc['recurring']:
                class_doc['recurring'] = str(class_doc['recurring'])
            else:
                class_doc['recurring'] = 'No'
            if class_doc.get('organization_id'):
                class_doc['organization_id'] = str(class_doc['organization_id'])
            if class_doc.get('coach_id'):
                class_doc['coach_id'] = str(class_doc['coach_id'])
            if class_doc.get('group_ids'):
                class_doc['group_ids'] = [str(gid) for gid in class_doc['group_ids']]
            if class_doc.get('student_ids'):
                class_doc['student_ids'] = [str(sid) for sid in class_doc['student_ids']]
            if class_doc.get('location'):
                if class_doc['location'].get('center_id'):
                    class_doc['location']['center_id'] = str(class_doc['location']['center_id'])
            if class_doc.get('schedule_item_id'):
                class_doc['schedule_item_id'] = str(class_doc['schedule_item_id'])
            
            if class_doc.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': ObjectId(class_doc['coach_id'])})
                if coach:
                    class_doc['coach_name'] = coach.get('name', 'Unknown')
        
        # Get total count
        total = mongo.db.classes.count_documents(query)
        
        print(classes)
        return jsonify({
            'classes': classes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    # except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('/<class_id>', methods=['GET'])
@jwt_or_session_required()
def get_class(class_id):
    """Get a specific class"""
    try:
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        user = get_current_user_info()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = user.get('role')
        user_id = user.get('user_id')
        organization_id = user.get('organization_id')
        
        # Verify user has access to this class
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'student':
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            user_groups = user_data.get('groups', []) if user_data else []
            
            is_enrolled = (
                ObjectId(user_id) in class_obj.student_ids or
                any(ObjectId(gid) in class_obj.group_ids for gid in user_groups)
            )
            
            if not is_enrolled:
                return jsonify({'error': 'Access denied'}), 403
        
        elif user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get additional details
        result = class_obj.to_dict()
        
        # Add coach details
        coach_data = mongo.db.users.find_one({'_id': class_obj.coach_id})
        if coach_data:
            result['coach'] = {
                'id': str(coach_data['_id']),
                'name': coach_data['name'],
                'phone_number': coach_data.get('phone_number')
            }
        
        # Add student count
        total_students = len(class_obj.student_ids)
        for group_id in class_obj.group_ids:
            group_students = mongo.db.users.count_documents({
                'groups': str(group_id),
                'role': 'student'
            })
            total_students += group_students
        
        result['student_count'] = total_students
        
        return jsonify({'class': result}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('/<class_id>', methods=['PUT'])
@jwt_or_session_required()

def update_class(class_id):
    # """Update a class"""
    # try:
        schema = UpdateClassSchema()
        data = schema.load(request.json)
        
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = user_info.get('role')
        user_id = user_info.get('user_id')
        organization_id = user_info.get('organization_id')
        
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        update_data = {
            'updated_at': datetime.utcnow()
        }
        
        for field in ['title', 'scheduled_at', 'duration_minutes', 'location', 
                     'sport', 'level', 'notes', 'max_students', 'status']:
            if field in data:
                update_data[field] = data[field]
        
        if 'coach_id' in data:
            update_data['coach_id'] = ObjectId(data['coach_id'])
        
        if 'group_ids' in data:
            update_data['group_ids'] = [ObjectId(gid) for gid in data['group_ids']]
        
        if 'student_ids' in data:
            update_data['student_ids'] = [ObjectId(sid) for sid in data['student_ids']]
        
        result = mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            updated_class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            updated_class = Class.from_dict(updated_class_data)
            return jsonify({
                'message': 'Class updated successfully',
            }), 200
        else:
            return jsonify({'error': 'No changes made'}), 400
    
    # except ValidationError as e:
    #     return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    # except Exception as e:
    #     return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('/<class_id>', methods=['DELETE'])
@jwt_or_session_required()

def delete_class(class_id):
    """Delete a class"""
    try:
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = user_info.get('role')
        user_id = user_info.get('user_id')
        organization_id = user_info.get('organization_id')
        
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Delete class and related attendance records
        mongo.db.classes.delete_one({'_id': ObjectId(class_id)})
        mongo.db.attendance.delete_many({'class_id': ObjectId(class_id)})
        
        return jsonify({'message': 'Class deleted successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('/<class_id>/students', methods=['GET'])
@jwt_or_session_required()
def get_class_students(class_id):
    """Get all students enrolled in a class"""
    try:
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        organization_id = user_info.get('organization_id')
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get direct students
        students = list(mongo.db.users.find({
            '_id': {'$in': class_obj.student_ids},
            'role': 'student'
        }))
        
        # Get students from groups
        for group_id in class_obj.group_ids:
            group_students = list(mongo.db.users.find({
                'groups': str(group_id),
                'role': 'student'
            }))
            
            # Avoid duplicates
            existing_ids = {str(s['_id']) for s in students}
            for student in group_students:
                if str(student['_id']) not in existing_ids:
                    students.append(student)
        
        # Format response
        students_data = []
        for student_data in students:
            student = User.from_dict(student_data)
            students_data.append({
                '_id': str(student._id),
                'name': student.name,
                'phone_number': student.phone_number,
                'profile_data': student.profile_data
            })
        
        print(students_data)
        return jsonify({
            'students': students_data,
            'total': len(students_data)
        }), 200
    
    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal server error'}), 500

@classes_bp.route('/<class_id>/send-reminder', methods=['POST'])
@jwt_or_session_required()

def send_class_reminder(class_id):
    """Send reminder for a specific class"""
    try:
        from app.services.whatsapp_service import WhatsAppService
        
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        organization_id = user_info.get('organization_id')
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        whatsapp_service = WhatsAppService()
        success, message = whatsapp_service.send_class_reminder(class_id)
        
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 