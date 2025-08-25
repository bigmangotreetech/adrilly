from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.attendance import Attendance, AttendanceSummary
from app.models.class_schedule import Class
from app.routes.auth import require_role
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, timedelta
from bson import ObjectId

attendance_bp = Blueprint('attendance', __name__, url_prefix='/api/attendance')

# Request schemas
class MarkAttendanceSchema(Schema):
    student_id = fields.Str(required=True)
    status = fields.Str(required=True, validate=lambda x: x in ['present', 'absent', 'late', 'excused'])
    notes = fields.Str(required=False)
    check_in_time = fields.DateTime(required=False)

class UpdateAttendanceSchema(Schema):
    status = fields.Str(required=False, validate=lambda x: x in ['present', 'absent', 'late', 'excused'])
    notes = fields.Str(required=False)
    check_in_time = fields.DateTime(required=False)

@attendance_bp.route('/class/<class_id>', methods=['GET'])
@jwt_required()
@require_role(['admin', 'coach'])
def get_class_attendance(class_id):
    """Get attendance for a specific class"""
    try:
        # Verify class exists and user has access
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get attendance records
        attendance_records = list(mongo.db.attendance.find({'class_id': ObjectId(class_id)}))
        
        # Get all students for this class
        all_students = []
        
        # Direct students
        direct_students = list(mongo.db.users.find({
            '_id': {'$in': class_obj.student_ids},
            'role': 'student'
        }))
        all_students.extend(direct_students)
        
        # Students from groups
        for group_id in class_obj.group_ids:
            group_students = list(mongo.db.users.find({
                'groups': str(group_id),
                'role': 'student'
            }))
            
            existing_ids = {str(s['_id']) for s in all_students}
            for student in group_students:
                if str(student['_id']) not in existing_ids:
                    all_students.append(student)
        
        # Build response with attendance status
        attendance_data = []
        attendance_map = {str(record['student_id']): record for record in attendance_records}
        
        for student_data in all_students:
            student_id = str(student_data['_id'])
            attendance_record = attendance_map.get(student_id)
            
            student_attendance = {
                'student': {
                    'id': student_id,
                    'name': student_data['name'],
                    'phone_number': student_data.get('phone_number')
                },
                'attendance': {
                    'status': 'pending',
                    'rsvp_response': None,
                    'check_in_time': None,
                    'notes': None,
                    'marked_by': None
                }
            }
            
            if attendance_record:
                attendance_obj = Attendance.from_dict(attendance_record)
                student_attendance['attendance'] = {
                    'id': str(attendance_record['_id']),
                    'status': attendance_obj.status,
                    'rsvp_response': attendance_obj.rsvp_response,
                    'check_in_time': attendance_obj.check_in_time,
                    'notes': attendance_obj.notes,
                    'marked_by': str(attendance_obj.marked_by) if attendance_obj.marked_by else None,
                    'created_at': attendance_obj.created_at,
                    'updated_at': attendance_obj.updated_at
                }
            
            attendance_data.append(student_attendance)
        
        # Calculate summary
        summary = {
            'total_students': len(attendance_data),
            'present': len([a for a in attendance_data if a['attendance']['status'] == 'present']),
            'absent': len([a for a in attendance_data if a['attendance']['status'] == 'absent']),
            'late': len([a for a in attendance_data if a['attendance']['status'] == 'late']),
            'excused': len([a for a in attendance_data if a['attendance']['status'] == 'excused']),
            'pending': len([a for a in attendance_data if a['attendance']['status'] == 'pending'])
        }
        
        return jsonify({
            'class': class_obj.to_dict(),
            'attendance': attendance_data,
            'summary': summary
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@attendance_bp.route('/class/<class_id>/mark', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def mark_attendance(class_id):
    """Mark attendance for a student in a class"""
    try:
        schema = MarkAttendanceSchema()
        data = schema.load(request.json)
        
        # Verify class exists and user has access
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        # Check permissions
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if attendance record already exists
        existing_attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(data['student_id'])
        })
        
        if existing_attendance:
            # Update existing record
            attendance = Attendance.from_dict(existing_attendance)
            attendance.status = data['status']
            attendance.marked_by = ObjectId(user_id)
            attendance.updated_at = datetime.utcnow()
            
            if data.get('notes'):
                attendance.notes = data['notes']
            
            if data.get('check_in_time'):
                attendance.check_in_time = data['check_in_time']
            elif data['status'] == 'present':
                attendance.check_in_time = datetime.utcnow()
            
            mongo.db.attendance.update_one(
                {'_id': existing_attendance['_id']},
                {'$set': attendance.to_dict()}
            )
            
            return jsonify({
                'message': 'Attendance updated successfully',
                'attendance': attendance.to_dict()
            }), 200
        else:
            # Create new attendance record
            new_attendance = Attendance(
                class_id=class_id,
                student_id=data['student_id'],
                status=data['status'],
                marked_by=user_id,
                notes=data.get('notes'),
                check_in_time=data.get('check_in_time')
            )
            
            if data['status'] == 'present' and not new_attendance.check_in_time:
                new_attendance.check_in_time = datetime.utcnow()
            
            result = mongo.db.attendance.insert_one(new_attendance.to_dict())
            new_attendance._id = result.inserted_id
            
            return jsonify({
                'message': 'Attendance marked successfully',
                'attendance': new_attendance.to_dict()
            }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@attendance_bp.route('/<attendance_id>', methods=['PUT'])
@jwt_required()
@require_role(['admin', 'coach'])
def update_attendance(attendance_id):
    """Update an attendance record"""
    try:
        schema = UpdateAttendanceSchema()
        data = schema.load(request.json)
        
        attendance_data = mongo.db.attendance.find_one({'_id': ObjectId(attendance_id)})
        if not attendance_data:
            return jsonify({'error': 'Attendance record not found'}), 404
        
        attendance = Attendance.from_dict(attendance_data)
        
        # Check if user has permission to update this attendance
        class_data = mongo.db.classes.find_one({'_id': attendance.class_id})
        if not class_data:
            return jsonify({'error': 'Associated class not found'}), 404
        
        class_obj = Class.from_dict(class_data)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        
        if organization_id != str(class_obj.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        if user_role == 'coach' and str(class_obj.coach_id) != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        update_data = {
            'updated_at': datetime.utcnow(),
            'marked_by': ObjectId(user_id)
        }
        
        if 'status' in data:
            update_data['status'] = data['status']
            if data['status'] == 'present' and not attendance.check_in_time:
                update_data['check_in_time'] = datetime.utcnow()
        
        if 'notes' in data:
            update_data['notes'] = data['notes']
        
        if 'check_in_time' in data:
            update_data['check_in_time'] = data['check_in_time']
        
        mongo.db.attendance.update_one(
            {'_id': ObjectId(attendance_id)},
            {'$set': update_data}
        )
        
        # Get updated record
        updated_attendance_data = mongo.db.attendance.find_one({'_id': ObjectId(attendance_id)})
        updated_attendance = Attendance.from_dict(updated_attendance_data)
        
        return jsonify({
            'message': 'Attendance updated successfully',
            'attendance': updated_attendance.to_dict()
        }), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@attendance_bp.route('/student/<student_id>/summary', methods=['GET'])
@jwt_required()
def get_student_attendance_summary(student_id):
    """Get attendance summary for a student"""
    try:
        # Check permissions
        claims = get_jwt()
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        organization_id = claims.get('organization_id')
        
        # Students can only view their own attendance, coaches/admins can view any student
        if user_role == 'student' and user_id != student_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get date range parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).date()
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        else:
            start_date = (datetime.utcnow() - timedelta(days=30)).date()
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        else:
            end_date = datetime.utcnow().date()
        
        # Build query for classes in date range
        class_query = {
            'scheduled_at': {
                '$gte': datetime.combine(start_date, datetime.min.time()),
                '$lte': datetime.combine(end_date, datetime.max.time())
            }
        }
        
        if organization_id:
            class_query['organization_id'] = ObjectId(organization_id)
        
        # Find classes student was enrolled in
        user_data = mongo.db.users.find_one({'_id': ObjectId(student_id)})
        if not user_data:
            return jsonify({'error': 'Student not found'}), 404
        
        user_groups = user_data.get('groups', [])
        
        class_query['$or'] = [
            {'student_ids': ObjectId(student_id)},
            {'group_ids': {'$in': [ObjectId(gid) for gid in user_groups]}}
        ]
        
        classes = list(mongo.db.classes.find(class_query))
        class_ids = [class_data['_id'] for class_data in classes]
        
        # Get attendance records for these classes
        attendance_records = list(mongo.db.attendance.find({
            'student_id': ObjectId(student_id),
            'class_id': {'$in': class_ids}
        }))
        
        # Calculate summary
        total_classes = len(classes)
        attendance_map = {str(record['class_id']): record for record in attendance_records}
        
        present_count = 0
        absent_count = 0
        late_count = 0
        excused_count = 0
        
        for class_data in classes:
            class_id = str(class_data['_id'])
            attendance_record = attendance_map.get(class_id)
            
            if attendance_record:
                status = attendance_record['status']
                if status == 'present':
                    present_count += 1
                elif status == 'absent':
                    absent_count += 1
                elif status == 'late':
                    late_count += 1
                elif status == 'excused':
                    excused_count += 1
            else:
                # No attendance record means pending/absent
                absent_count += 1
        
        summary = AttendanceSummary(
            student_id=student_id,
            period_start=start_date,
            period_end=end_date,
            total_classes=total_classes,
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            excused_count=excused_count
        )
        
        return jsonify({
            'summary': summary.to_dict(),
            'details': {
                'student': {
                    'id': str(user_data['_id']),
                    'name': user_data['name']
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@attendance_bp.route('/rsvp/<attendance_id>', methods=['POST'])
def update_rsvp(attendance_id):
    """Update RSVP response (public endpoint for WhatsApp integration)"""
    try:
        data = request.json
        response = data.get('response', '').lower()
        
        if response not in ['yes', 'no', 'maybe']:
            return jsonify({'error': 'Invalid response. Use yes, no, or maybe'}), 400
        
        attendance_data = mongo.db.attendance.find_one({'_id': ObjectId(attendance_id)})
        if not attendance_data:
            return jsonify({'error': 'Attendance record not found'}), 404
        
        attendance = Attendance.from_dict(attendance_data)
        attendance.update_rsvp(response, data.get('message_id'))
        
        mongo.db.attendance.update_one(
            {'_id': ObjectId(attendance_id)},
            {'$set': attendance.to_dict()}
        )
        
        return jsonify({
            'message': 'RSVP updated successfully',
            'response': response
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 