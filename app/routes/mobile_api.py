from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.services.auth_service import AuthService
from app.services.file_upload_service import FileUploadService
from app.services.coin_service import CoinService
from app.models.coin_transaction import CoinTransaction
from app.routes.auth import require_role
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, timedelta, date
from bson import ObjectId
import jwt
import hmac
import hashlib
import base64
import json
import os
import uuid
from werkzeug.utils import secure_filename

mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/mobile-api')

def make_json_serializable(obj):
    """Convert MongoDB objects to JSON serializable format"""
    if isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    else:
        return obj

def convert_instruction_keys_to_str(class_doc):
    """Convert instruction keys to strings if instructions is a dict"""
    if class_doc and isinstance(class_doc, dict):
        instructions = class_doc.get('instructions')
        if instructions and isinstance(instructions, dict):
            # Convert all keys to strings
            class_doc['instructions'] = {str(k): v for k, v in instructions.items()}
        instructions_sent_by = class_doc.get('instructions_sent_by')
        if instructions_sent_by:
            class_doc['instructions_sent_by'] = str(instructions_sent_by)
    return class_doc

def get_effective_user_id():
    """
    Get the effective user ID to use for API calls.
    Checks for X-Active-Profile-Id header and validates if the authenticated user
    has permission to access that profile (i.e., it's their child).
    Returns the active profile ID if valid, otherwise returns the JWT user ID.
    """
    # Get the authenticated user ID from JWT
    jwt_user_id = get_jwt_identity()
    
    # Check if there's an active profile ID in the header
    active_profile_id = request.headers.get('X-Active-Profile-Id')
    
    # If no active profile header or it's the same as JWT user, return JWT user ID
    if not active_profile_id or str(active_profile_id) == str(jwt_user_id):
        return jwt_user_id
    
    # Validate that the active profile is a child of the authenticated user
    try:
        child = mongo.db.users.find_one({
            '_id': ObjectId(active_profile_id),
            'parent_id': ObjectId(jwt_user_id),
            'is_active': True
        })
        
        if child:
            # Valid child profile, return the child's ID
            return active_profile_id
        else:
            # Not a valid child, return JWT user ID
            current_app.logger.warning(
                f"User {jwt_user_id} attempted to access profile {active_profile_id} without permission"
            )
            return jwt_user_id
    except Exception as e:
        current_app.logger.error(f"Error validating active profile: {str(e)}")
        return jwt_user_id

# QR Attendance Utilities
QR_SECRET_KEY = "qr_attendance_secret_2024"  # In production, use environment variable
QR_TOKEN_VALIDITY_MINUTES = 15

def generate_qr_token(payload):
    """Generate a signed token for QR codes"""
    # Add timestamp and expiry
    payload['issued_at'] = datetime.utcnow().isoformat()
    payload['expires_at'] = (datetime.utcnow() + timedelta(minutes=QR_TOKEN_VALIDITY_MINUTES)).isoformat()
    
    # Convert to JSON string
    payload_json = json.dumps(payload, sort_keys=True)
    
    # Create HMAC signature
    signature = hmac.new(
        QR_SECRET_KEY.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Combine payload and signature
    token_data = {
        'payload': payload,
        'signature': signature
    }
    
    # Base64 encode for QR code
    token_string = base64.b64encode(json.dumps(token_data).encode()).decode()
    return token_string

def validate_qr_token(token_string):
    """Validate and decode a QR token"""
    try:
        # Decode from base64
        token_data = json.loads(base64.b64decode(token_string).decode())
        
        payload = token_data['payload']
        provided_signature = token_data['signature']
        
        # Recreate signature
        payload_json = json.dumps(payload, sort_keys=True)
        expected_signature = hmac.new(
            QR_SECRET_KEY.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None, "Invalid token signature"
        
        # Check expiry
        expires_at = datetime.fromisoformat(payload['expires_at'])
        if datetime.utcnow() > expires_at:
            return None, "Token has expired"
        
        return payload, None
    
    except Exception as e:
        return None, f"Invalid token format: {str(e)}"

def resolve_active_class(center_id, scan_time=None):
    """Resolve which class is currently active for a center"""
    if scan_time is None:
        scan_time = datetime.utcnow()
    
    # Look for classes within the time window (15 minutes before/after start time)
    time_window = timedelta(minutes=15)
    start_window = scan_time - time_window
    end_window = scan_time + time_window
    
    # Query for classes at this center around this time
    classes_cursor = mongo.db.classes.find({
        'center_id': ObjectId(center_id),
        'scheduled_at': {
            '$gte': start_window,
            '$lte': end_window
        },
        'status': {'$ne': 'cancelled'}
    }).sort('scheduled_at', 1)
    
    classes = list(classes_cursor)
    
    if not classes:
        return None, "No active class found for this center at this time"
    
    # Return the closest class to the scan time
    closest_class = min(classes, key=lambda c: abs((c['scheduled_at'] - scan_time).total_seconds()))
    return closest_class, None

# Request schemas
class OTPRequestSchema(Schema):
    phone_number = fields.Str(required=True)

class OTPVerifySchema(Schema):
    phone_number = fields.Str(required=True)
    otp = fields.Str(required=True)
    name = fields.Str(required=False)

class LoginSchema(Schema):
    phone_number = fields.Str(required=True)
    password = fields.Str(required=True)

class MarkAttendanceSchema(Schema):
    class_id = fields.Str(required=True)
    student_id = fields.Str(required=True)
    status = fields.Str(required=True, validate=lambda x: x in ['present', 'absent', 'late', 'excused'])
    notes = fields.Str(required=False)

class UpdateProfileSchema(Schema):
    name = fields.Str(required=False)
    profile_data = fields.Dict(required=False)

class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True)

# Authentication endpoints
@mobile_api_bp.route('/auth/request-otp', methods=['POST'])
def request_otp():
    """Request OTP for phone number"""
    try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = OTPRequestSchema()
        data = schema.load(request.json)
        
        result, status_code = AuthService.request_otp(data['phone_number'])
        print(result)
        print(status_code)
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"OTP request error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP and login/register user"""
    try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = OTPVerifySchema()
        data = schema.load(request.json)
        print(data)
        result, status_code = AuthService.verify_otp(
            data['phone_number'],
            data['otp'],
        )

        print(result)
        print(status_code)
        return jsonify(result), status_code
    
    except ValidationError as e:
        print(e)
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"OTP verification error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/login', methods=['POST'])
def login():
    """Login with phone number and password"""
    try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = LoginSchema()
        data = schema.load(request.json)
        
        result, status_code = AuthService.login_with_password(
            data['phone_number'], 
            data['password']
        )
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        print(current_user_id)
        
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        print(user)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        from flask_jwt_extended import create_access_token
        new_access_token = create_access_token(
            identity=str(user['_id']),
            additional_claims={
                'role': user.get('role', 'student'),
                'organization_id': str(user.get('organization_id', ''))
            }
        )
        
        return jsonify({
            'access_token': new_access_token,
            'message': 'Token refreshed successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    try:
        current_user_id = get_jwt_identity()
        
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Convert ObjectId to string and remove sensitive data
        user['_id'] = str(user['_id'])
        if 'password' in user:
            del user['password']
        if user.get('organization_id'):
            user['organization_id'] = str(user['organization_id'])
            
            # Get primary center name for the user's organization
            primary_center = mongo.db.centers.find_one(
                {'organization_id': ObjectId(user['organization_id']), 'is_active': True},
                sort=[('created_at', 1)]  # Get the first created center as primary
            )
            if primary_center:
                user['primary_center_name'] = primary_center.get('name', 'Unknown Center')
            else:
                user['primary_center_name'] = 'No Center Assigned'
        else:
            user['primary_center_name'] = 'No Organization'

        if user.get('subscription_ids'):
            user['subscription_ids'] = [str(sid) for sid in user['subscription_ids']]
        
        # Ensure botle_coins field exists (default to 0 for existing users)
        if 'botle_coins' not in user:
            user['botle_coins'] = 0
        
        # Check for child profiles
        children_cursor = mongo.db.users.find({
            'parent_id': ObjectId(current_user_id),
            'is_active': True
        }).sort('created_at', -1)
        
        children = []
        for child_data in children_cursor:
            child_data['_id'] = str(child_data['_id'])
            if child_data.get('organization_id'):
                child_data['organization_id'] = str(child_data['organization_id'])
            if child_data.get('parent_id'):
                child_data['parent_id'] = str(child_data['parent_id'])
            if 'password' in child_data:
                del child_data['password']
            # Ensure botle_coins for children too
            if 'botle_coins' not in child_data:
                child_data['botle_coins'] = 0
            children.append(child_data)
        
        user['children'] = children
        user['has_children'] = len(children) > 0

        if user.get('organization_ids'):
            user['organization_ids'] = [str(oid) for oid in user['organization_ids']]
            
        
        return jsonify({'user': user}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = UpdateProfileSchema()
        data = schema.load(request.json)
        
        current_user_id = get_jwt_identity()
        
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'profile_data' in data:
            update_data['profile_data'] = data['profile_data']
        
        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        update_data['updated_at'] = datetime.utcnow()
        
        result = mongo.db.users.update_one(
            {'_id': ObjectId(current_user_id)},
            {'$set': update_data}
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'User not found or no changes made'}), 404
        
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        user['_id'] = str(user['_id'])
        if 'password' in user:
            del user['password']
        if user.get('organization_id'):
            user['organization_id'] = str(user['organization_id'])
        if user.get('subscription_ids'):
            user['subscription_ids'] = [str(sid) for sid in user['subscription_ids']]
        if user.get('organization_ids'):    
            user['organization_ids'] = [str(oid) for oid in user['organization_ids']]
        return jsonify({
            'user': user,
            'message': 'Profile updated successfully'
        }), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Update profile error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = ChangePasswordSchema()
        data = schema.load(request.json)
        
        current_user_id = get_jwt_identity()
        
        result, status_code = AuthService.change_password(
            current_user_id,
            data['current_password'],
            data['new_password']
        )
        return jsonify(result), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Change password error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    try:
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/auth/organizations', methods=['GET'])
@jwt_required()
def get_organizations():
    """Get accessible organizations for the current user"""
    try:
        current_user_id = get_jwt_identity()
        
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        organizations = []
        if user.get('organization_id'):
            org = mongo.db.organizations.find_one({'_id': ObjectId(user['organization_id'])})
            if org:
                org['_id'] = str(org['_id'])
                organizations.append(org)
        
        return jsonify({'organizations': organizations}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get organizations error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Dashboard endpoints
@mobile_api_bp.route('/dashboard/stats/<user_id>', methods=['GET'])
@jwt_required()
def get_dashboard_stats(user_id):
    """Get dashboard statistics for a user"""
    try:
        # Get effective user ID (supports child profiles) - use this if user_id matches
        effective_user_id = get_effective_user_id()
        jwt_user_id = get_jwt_identity()
        
        # If requesting stats for self, use effective user ID (could be child)
        if str(user_id) == str(jwt_user_id):
            user_id = effective_user_id
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # Check permissions
        if jwt_user_id != user_id and current_role not in ['super_admin', 'org_admin', 'coach_admin', 'coach']:
            # Also allow if user is viewing their child's stats
            child_check = mongo.db.users.find_one({
                '_id': ObjectId(user_id),
                'parent_id': ObjectId(jwt_user_id),
                'is_active': True
            })
            if not child_check:
                return jsonify({'error': 'Unauthorized access'}), 403
        
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if str(user.get('organization_id')) != current_org_id and current_role != 'super_admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        stats = {}
        
        if user['role'] == 'coach':
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            today_classes = mongo.db.classes.count_documents({
                'coach_id': ObjectId(user_id),
                'scheduled_at': {'$gte': today, '$lt': tomorrow}
            })
            
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=7)
            print(start_of_week, end_of_week, user_id)
            week_classes = mongo.db.classes.count_documents({
                'coach_id': ObjectId(user_id),
                'scheduled_at': {'$gte': start_of_week, '$lt': end_of_week}
            })
            
            stats = {
                'class_stats': {
                    'todays_classes': today_classes,
                    'recent_classes': week_classes
                }
            }
            print(stats)
        
        elif user['role'] == 'student':
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            
            today_classes = mongo.db.classes.count_documents({
                'student_ids': user_id,
                'scheduled_at': {'$gte': today, '$lt': tomorrow}
            })
            
            thirty_days_ago = today - timedelta(days=30)
            total_classes = mongo.db.classes.count_documents({
                'student_ids': ObjectId(user_id),
                'scheduled_at': {'$gte': thirty_days_ago, '$lt': today}
            })
            
            attended_classes = mongo.db.attendance.count_documents({
                'student_id': ObjectId(user_id),
                'status': {'$in': ['present', 'late']},
                'date': {'$gte': thirty_days_ago.date(), '$lt': today.date()}
            })
            
            attendance_rate = (attended_classes / total_classes * 100) if total_classes > 0 else 0
            
            stats = {
                'class_stats': {
                    'todays_classes': today_classes,
                    'recent_classes': week_classes
                },
                'attendanceRate': round(attendance_rate, 1),
                'totalClasses': total_classes,
                'attendedClasses': attended_classes
                }
        
        else:
            org_filter = {'organization_id': current_org_id} if current_org_id else {}
            
            total_students = mongo.db.users.count_documents({**org_filter, 'role': 'student'})
            total_coaches = mongo.db.users.count_documents({**org_filter, 'role': 'coach'})
            total_classes = mongo.db.classes.count_documents(org_filter)
            
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            today_classes = mongo.db.classes.count_documents({
                **org_filter,
                'scheduled_at': {'$gte': today, '$lt': tomorrow}
            })

            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=7)
            week_classes = mongo.db.classes.count_documents({
                **org_filter,
                'scheduled_at': {'$gte': start_of_week, '$lt': end_of_week}
            })
            
            stats = {
                'totalStudents': total_students,
                'totalCoaches': total_coaches,
                'totalClasses': total_classes,
                'class_stats': {
                    'todays_classes': today_classes,
                    'recent_classes': week_classes
                },
            }
        
        return jsonify(stats), 200
    
    except Exception as e:
        current_app.logger.error(f"Dashboard stats error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Classes endpoints - segregated by role
@mobile_api_bp.route('/student/classes', methods=['GET'])
@jwt_required()
def get_student_classes():
    """Get classes for students"""
    try:
        # Get effective user ID (supports child profiles)
        current_user_id = get_effective_user_id()
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # This endpoint is for students only
        # if current_role not in ['student']:
        #     return jsonify({'error': 'Unauthorized - Student access only'}), 403
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        count_only = request.args.get('count_only') == 'true'
        
        filter_query = {}
        if current_org_id:
            filter_query['organization_id'] = ObjectId(current_org_id)
        
        # Students only see their enrolled classes
        filter_query['student_ids'] = ObjectId(current_user_id)
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                print(start_date)
                date_filter['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                print(end_date)
                date_filter['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filter_query['scheduled_at'] = date_filter
        
        if status:
            filter_query['status'] = status
        
        if count_only:
            count = mongo.db.classes.count_documents(filter_query)
            return jsonify({'total_count': count}), 200
        
        skip = (page - 1) * per_page
        classes_cursor = mongo.db.classes.find(filter_query).sort('scheduled_at', 1).skip(skip).limit(per_page)
        
        classes = []
        for class_doc in classes_cursor:
            print(class_doc)
            class_doc['_id'] = str(class_doc['_id'])
            if class_doc.get('coach_id'):
                class_doc['coach_id'] = str(class_doc['coach_id'])
            if class_doc.get('organization_id'):
                class_doc['organization_id'] = str(class_doc['organization_id'])
            if class_doc.get('student_ids'):
                class_doc['student_ids'] = [str(s) for s in class_doc['student_ids']]
            if class_doc['scheduled_at']:
                class_doc['scheduled_at'] = (class_doc['scheduled_at'] + timedelta(hours=5, minutes=30)).isoformat()
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

            if class_doc.get('cancelled_by'):
                class_doc['cancelled_by'] = str(class_doc['cancelled_by'])
            
            if 'organization_id' in class_doc:
                organization = mongo.db.organizations.find_one({'_id': ObjectId(class_doc['organization_id'])})
                if organization:
                    class_doc['organization_name'] = organization.get('name','')

            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(class_doc)

            classes.append(class_doc)
        
        total_count = mongo.db.classes.count_documents(filter_query)
        
        print(filter_query)
        print(classes)
        
        return jsonify({
            'classes': classes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get student classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/coach/classes', methods=['GET'])
@jwt_required()
def get_coach_classes():
    """Get classes for coaches and org_admins"""
    try:
        current_user_id = get_jwt_identity()
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # This endpoint is for coaches and org_admins
        if current_role not in ['coach', 'coach_admin', 'org_admin', 'super_admin', 'center_admin']:
            return jsonify({'error': 'Unauthorized - Coach/Admin access only'}), 403
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        count_only = request.args.get('count_only') == 'true'
        
        filter_query = {}
        if current_org_id:
            filter_query['organization_id'] = ObjectId(current_org_id)
        
        # For org_admin, show all classes in organization (no coach filter)
        # For coaches, only show their assigned classes
        if current_role == 'org_admin' or current_role == 'super_admin':
            # Org admin sees all classes in their organization
            pass  # No coach_id filter
        else:
            # Regular coaches see only their classes
            filter_query['coach_id'] = ObjectId(current_user_id)
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                print(start_date)
                date_filter['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                print(end_date)
                date_filter['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filter_query['scheduled_at'] = date_filter
        
        if status:
            filter_query['status'] = status
        
        if count_only:
            count = mongo.db.classes.count_documents(filter_query)
            return jsonify({'total_count': count}), 200
        
        skip = (page - 1) * per_page
        classes_cursor = mongo.db.classes.find(filter_query).sort('scheduled_at', 1).skip(skip).limit(per_page)
        
        classes = []
        for class_doc in classes_cursor:
            class_doc['_id'] = str(class_doc['_id'])
            if class_doc.get('coach_id'):
                class_doc['coach_id'] = str(class_doc['coach_id'])
            if class_doc.get('organization_id'):
                class_doc['organization_id'] = str(class_doc['organization_id'])
            if class_doc.get('student_ids'):
                class_doc['student_ids'] = [str(s) for s in class_doc['student_ids']]
            if class_doc['scheduled_at']:
                class_doc['scheduled_at'] = (class_doc['scheduled_at'] + timedelta(hours=5, minutes=30)).isoformat()
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

            if class_doc.get('cancelled_by'):
                class_doc['cancelled_by'] = str(class_doc['cancelled_by'])
            
            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(class_doc)
            
            classes.append(class_doc)
        
        total_count = mongo.db.classes.count_documents(filter_query)
        
        print(filter_query)
        
        return jsonify({
            'classes': classes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get coach classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/student/classes-booked', methods=['GET'])
@jwt_required()
def get_classes_booked():
    """Get classes booked by a user"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        classes_list = []
        bookings = mongo.db.bookings.find({'booked_by': ObjectId(current_user_id)})
        for booking in bookings:
            print('booking', booking)
            class_doc = mongo.db.classes.find_one({'_id': ObjectId(booking['class_id'])})
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

            if class_doc.get('cancelled_by'):
                class_doc['cancelled_by'] = str(class_doc['cancelled_by'])

            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(class_doc)

            booked_for = mongo.db.users.find_one({'_id': ObjectId(booking['student_id'])})
            class_doc['booked_for'] = booked_for.get('name', '')
            
            classes_list.append(class_doc)

        print(classes_list)
        return jsonify({'classes': classes_list}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get classes booked error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>', methods=['GET'])
@jwt_required()
def get_class_details(class_id):
    """Get detailed information about a specific class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        if current_role == 'student' and ObjectId(current_user_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'Unauthorized access'}), 403
        
        if current_role == 'coach' and str(class_doc.get('coach_id')) != current_user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        class_doc['_id'] = str(class_doc['_id'])
        if class_doc.get('coach_id'):
            class_doc['coach_id'] = str(class_doc['coach_id'])
        if class_doc.get('organization_id'):
            class_doc['organization_id'] = str(class_doc['organization_id'])
        if class_doc.get('student_ids'):
            class_doc['student_ids'] = [str(s) for s in class_doc['student_ids']]
        if class_doc.get('group_ids'):
            class_doc['group_ids'] = [str(gid) for gid in class_doc['group_ids']]
        if class_doc.get('location'):
            if class_doc['location'].get('center_id'):
                class_doc['location']['center_id'] = str(class_doc['location']['center_id'])
        
        if class_doc.get('coach_id'):
            coach = mongo.db.users.find_one({'_id': ObjectId(class_doc['coach_id'])})
            if coach:
                class_doc['coach_info'] = {
                    'id': str(coach['_id']),
                    'name': coach.get('name', 'Unknown'),
                    'phone_number': coach.get('phone_number', '')
                }
        
        if current_role in ['coach', 'org_admin', 'coach_admin', 'super_admin'] and class_doc.get('students'):
            students = list(mongo.db.users.find(
                {'_id': {'$in': [ObjectId(s) for s in class_doc['student_ids']]}},
                {'name': 1, 'phone_number': 1}
            ))
            class_doc['student_info'] = [
                {
                    'id': str(student['_id']),
                    'name': student.get('name', 'Unknown'),
                    'phone_number': student.get('phone_number', '')
                }
                for student in students
            ]
        
        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(class_doc)
        
        return jsonify({'class': class_doc}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class details error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Attendance endpoints
@mobile_api_bp.route('/attendance/class/<class_id>', methods=['GET'])
@jwt_required()
@require_role(['coach', 'org_admin', 'coach_admin', 'super_admin'])
def get_class_attendance(class_id):
    """Get attendance for a specific class"""
    try:
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        attendance_records = list(mongo.db.attendance.find({'class_id': ObjectId(class_id)}))
        
        for record in attendance_records:
            record['_id'] = str(record['_id'])
            record['class_id'] = str(record['class_id'])
            record['student_id'] = str(record['student_id'])
            
            student = mongo.db.users.find_one({'_id': ObjectId(record['student_id'])})
            if student:
                record['student_name'] = student.get('name', 'Unknown')
        
        return jsonify({'attendance': attendance_records}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class attendance error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/rsvp-status', methods=['GET'])
@jwt_required()
def get_class_rsvp_status(class_id):
    """Get RSVP status for all students in a class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # Validate class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check permission - coaches, org_admins can see all RSVPs
        if current_role == 'student':
            # Students can only see their own RSVP
            if ObjectId(current_user_id) not in class_doc.get('student_ids', []):
                return jsonify({'error': 'Unauthorized'}), 403
        elif current_role == 'coach':
            # Coach can see RSVPs for their classes
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Unauthorized'}), 403
        elif current_role in ['org_admin', 'super_admin']:
            # Org admin can see RSVPs for all classes in their organization
            if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
                return jsonify({'error': 'Unauthorized'}), 403
        
        # Get all enrolled students
        student_ids = class_doc.get('student_ids', [])
        
        # Get RSVP status for all students
        rsvps = list(mongo.db.rsvps.find({
            'class_id': ObjectId(class_id),
            'student_id': {'$in': [ObjectId(sid) for sid in student_ids]}
        }))
        
        # Create a map of student_id -> rsvp_status
        rsvp_map = {}
        for rsvp in rsvps:
            rsvp_map[str(rsvp['student_id'])] = {
                'status': rsvp.get('rsvp_status'),
                'reason': rsvp.get('reason'),
                'updated_at': rsvp.get('updated_at').isoformat() if rsvp.get('updated_at') else None
            }
        
        # Get student details
        students = list(mongo.db.users.find(
            {'_id': {'$in': [ObjectId(sid) for sid in student_ids]}},
            {'name': 1, 'phone_number': 1}
        ))
        
        # Build response with student info and RSVP status
        rsvp_status_list = []
        for student in students:
            student_id = str(student['_id'])
            rsvp_info = rsvp_map.get(student_id, {'status': None, 'reason': None, 'updated_at': None})
            
            rsvp_status_list.append({
                'student_id': student_id,
                'student_name': student.get('name', 'Unknown'),
                'rsvp_status': rsvp_info['status'],
                'reason': rsvp_info['reason'],
                'updated_at': rsvp_info['updated_at']
            })
        
        return jsonify({
            'rsvp_status': rsvp_status_list,
            'total_students': len(student_ids),
            'responded': len(rsvp_map),
            'not_responded': len(student_ids) - len(rsvp_map)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class RSVP status error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/students/enrolled', methods=['GET'])
@jwt_required()
def get_class_enrolled_students(class_id):
    """Get list of students enrolled in a class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Students can only view if they're enrolled in the class
        if current_role == 'student' and ObjectId(current_user_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get student IDs from the class
        student_ids = class_doc.get('student_ids', [])
        
        if not student_ids:
            return jsonify({'students': []}), 200
        
        # Fetch student details
        students = list(mongo.db.users.find(
            {'_id': {'$in': student_ids}},
            {'name': 1, 'phone_number': 1, 'email': 1, 'profile_picture': 1}
        ))
        
        # Format student data
        formatted_students = []
        for student in students:
            formatted_students.append({
                'id': str(student['_id']),
                'name': student.get('name', 'Unknown'),
                'phone_number': student.get('phone_number', ''),
                'email': student.get('email', ''),
                'profile_picture': student.get('profile_picture', '')
            })
        
        return jsonify({
            'students': formatted_students,
            'total_count': len(formatted_students)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class enrolled students error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/students/attended', methods=['GET'])
@jwt_required()
def get_class_attended_students(class_id):
    """Get list of students who attended a class (marked as present or late)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Students can only view if they're enrolled in the class
        if current_role == 'student' and ObjectId(current_user_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get attendance records for this class (only present and late)
        attendance_records = list(mongo.db.attendance.find({
            'class_id': ObjectId(class_id),
            'status': {'$in': ['present', 'late']}
        }))
        
        if not attendance_records:
            return jsonify({'students': [], 'total_count': 0}), 200
        
        # Get student details for attended students
        student_ids = [record['student_id'] for record in attendance_records]
        students = list(mongo.db.users.find(
            {'_id': {'$in': student_ids}},
            {'name': 1, 'phone_number': 1, 'email': 1, 'profile_picture': 1}
        ))
        
        # Create a map of student_id to student data
        student_map = {str(student['_id']): student for student in students}
        
        # Format student data with attendance info
        formatted_students = []
        for record in attendance_records:
            student_id = str(record['student_id'])
            student = student_map.get(student_id)
            
            if student:
                formatted_students.append({
                    'id': student_id,
                    'name': student.get('name', 'Unknown'),
                    'phone_number': student.get('phone_number', ''),
                    'email': student.get('email', ''),
                    'profile_picture': student.get('profile_picture', ''),
                    'attendance_status': record.get('status', 'present'),
                    'marked_at': record.get('marked_at')
                })
        
        return jsonify({
            'students': formatted_students,
            'total_count': len(formatted_students)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class attended students error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/students/unmarked', methods=['GET'])
@jwt_required()
def get_class_unmarked_students(class_id):
    """Get list of enrolled students whose attendance is not marked yet"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Only coaches and admins can view unmarked students for attendance marking
        if current_role == 'student':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get student IDs from the class
        student_ids = class_doc.get('student_ids', [])
        
        if not student_ids:
            return jsonify({'students': [], 'total_count': 0}), 200
        
        # Get all attendance records for this class (any status)
        attendance_records = list(mongo.db.attendance.find({
            'class_id': ObjectId(class_id)
        }))
        
        # Get student IDs that already have attendance marked
        marked_student_ids = {record['student_id'] for record in attendance_records}
        
        # Filter out students who already have attendance marked
        unmarked_student_ids = [
            sid for sid in student_ids 
            if sid not in marked_student_ids
        ]
        
        if not unmarked_student_ids:
            return jsonify({'students': [], 'total_count': 0}), 200
        
        # Fetch student details for unmarked students
        students = list(mongo.db.users.find(
            {'_id': {'$in': unmarked_student_ids}},
            {'name': 1, 'phone_number': 1, 'email': 1, 'profile_picture': 1}
        ))
        
        # Format student data
        formatted_students = []
        for student in students:
            formatted_students.append({
                'id': str(student['_id']),
                '_id': str(student['_id']),  # Include _id for backward compatibility
                'name': student.get('name', 'Unknown'),
                'phone_number': student.get('phone_number', ''),
                'email': student.get('email', ''),
                'profile_picture': student.get('profile_picture', '')
            })
        
        return jsonify({
            'students': formatted_students,
            'total_count': len(formatted_students)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class unmarked students error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/attendance', methods=['POST'])
@jwt_required()
def mark_attendance():
    # """Mark attendance for a student in a class"""
    # try:
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = MarkAttendanceSchema()
        data = schema.load(request.json)

        current_user_id = get_jwt_identity()
        
        class_id = data['class_id']
        student_id = data['student_id']
        status = data['status']
        notes = data.get('notes', '')
        
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403

        print(class_doc)
        
        if ObjectId(student_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'Student not enrolled in this class'}), 400
        
        existing_attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(student_id)
        })
        
        attendance_data = {
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(student_id),
            'status': status,
            'notes': notes,
            'date': class_doc['scheduled_at'],
            'marked_at': datetime.now(),
            'marked_by': ObjectId(current_user_id)
        }
        
        if existing_attendance:
            mongo.db.attendance.update_one(
                {'_id': existing_attendance['_id']},
                {'$set': attendance_data}
            )
            attendance_id = existing_attendance['_id']
        else:
            result = mongo.db.attendance.insert_one(attendance_data)
            attendance_id = result.inserted_id
        
        attendance_record = mongo.db.attendance.find_one({'_id': attendance_id})
        attendance_record['_id'] = str(attendance_record['_id'])
        attendance_record['class_id'] = str(attendance_record['class_id'])
        attendance_record['student_id'] = str(attendance_record['student_id'])
        attendance_record['marked_by'] = str(attendance_record['marked_by'])
        
        student = mongo.db.users.find_one({'_id': ObjectId(student_id)})
        if student:
            attendance_record['student_name'] = student.get('name', 'Unknown')
        
        return jsonify({
            'message': 'Attendance marked successfully'
        }), 200
    
    # except ValidationError as e:
    #     return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    # except Exception as e:
    #     current_app.logger.error(f"Mark attendance error: {str(e)}")
    #     return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/attendance/student/<student_id>', methods=['GET'])
@jwt_required()
def get_student_attendance(student_id):
    """Get attendance history for a student"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        if current_role == 'student' and current_user_id != student_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        student = mongo.db.users.find_one({'_id': ObjectId(student_id)})
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        if current_org_id and str(student.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        filter_query = {'student_id': ObjectId(student_id)}
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
            if end_date:
                date_filter['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            filter_query['date'] = date_filter
        
        skip = (page - 1) * per_page
        attendance_cursor = mongo.db.attendance.find(filter_query).sort('date', -1).skip(skip).limit(per_page)
        
        attendance_records = []
        for record in attendance_cursor:
            record['_id'] = str(record['_id'])
            record['class_id'] = str(record['class_id'])
            record['student_id'] = str(record['student_id'])
            if record.get('marked_by'):
                record['marked_by'] = str(record['marked_by'])
            
            class_doc = mongo.db.classes.find_one({'_id': ObjectId(record['class_id'])})
            if class_doc:
                record['class_info'] = {
                    'title': class_doc.get('title', 'Unknown'),
                    'scheduled_at': class_doc.get('scheduled_at').isoformat() if class_doc.get('scheduled_at') else None
                }
            
            attendance_records.append(record)
        
        total_count = mongo.db.attendance.count_documents(filter_query)
        
        return jsonify({
            'attendance': attendance_records,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get student attendance error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/attendance/student/<student_id>/summary', methods=['GET'])
@jwt_required()
def get_student_attendance_summary(student_id):
    """Get attendance summary/stats for a student"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        if current_role == 'student' and current_user_id != student_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        student = mongo.db.users.find_one({'_id': ObjectId(student_id)})
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        if current_org_id and str(student.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        total_classes = mongo.db.attendance.count_documents({'student_id': ObjectId(student_id)})
        present_count = mongo.db.attendance.count_documents({
            'student_id': ObjectId(student_id),
            'status': {'$in': ['present', 'late']}
        })
        absent_count = mongo.db.attendance.count_documents({
            'student_id': ObjectId(student_id),
            'status': 'absent'
        })
        
        attendance_rate = (present_count / total_classes * 100) if total_classes > 0 else 0
        
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_total = mongo.db.attendance.count_documents({
            'student_id': ObjectId(student_id),
            'date': {'$gte': start_of_month.date()}
        })
        month_present = mongo.db.attendance.count_documents({
            'student_id': ObjectId(student_id),
            'status': {'$in': ['present', 'late']},
            'date': {'$gte': start_of_month.date()}
        })
        
        return jsonify({
            'summary': {
                'total_classes': total_classes,
                'present_count': present_count,
                'absent_count': absent_count,
                'attendance_rate': round(attendance_rate, 1),
                'this_month': {
                    'total_classes': month_total,
                    'present_count': month_present,
                    'attendance_rate': round((month_present / month_total * 100) if month_total > 0 else 0, 1)
                }
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get attendance summary error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/attendance/stats', methods=['GET'])
@jwt_required()
def get_attendance_stats():
    """Get attendance statistics for the organization"""
    try:
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        if not current_org_id:
            return jsonify({'error': 'Organization not found'}), 404
        
        org_filter = {'organization_id': ObjectId(current_org_id)}
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        recent_classes = list(mongo.db.classes.find({
            **org_filter,
            'scheduled_at': {'$gte': thirty_days_ago}
        }))
        
        total_expected_attendance = 0
        total_actual_attendance = 0
        
        for class_doc in recent_classes:
            student_count = len(class_doc.get('student_ids', []))
            total_expected_attendance += student_count
            
            actual_attendance = mongo.db.attendance.count_documents({
                'class_id': class_doc['_id'],
                'status': {'$in': ['present', 'late']}
            })
            total_actual_attendance += actual_attendance
        
        attendance_rate = (total_actual_attendance / total_expected_attendance * 100) if total_expected_attendance > 0 else 0
        
        return jsonify({
            'attendance_rate': round(attendance_rate, 1),
            'total_expected': total_expected_attendance,
            'total_attended': total_actual_attendance
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get attendance stats error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Payments endpoints
@mobile_api_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_payments():
    """Get payments for the current user or organization"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        filter_query = {}
        if current_org_id:
            filter_query['organization_id'] = ObjectId(current_org_id)
        
        if current_role == 'student':
            filter_query['student_id'] = ObjectId(current_user_id)
        
        if status:
            filter_query['status'] = status
        
        skip = (page - 1) * per_page
        payments_cursor = mongo.db.payments.find(filter_query).sort('due_date', 1).skip(skip).limit(per_page)
        
        payments = []
        for payment in payments_cursor:
            payment['_id'] = str(payment['_id'])
            if payment.get('student_id'):
                payment['student_id'] = str(payment['student_id'])
            if payment.get('organization_id'):
                payment['organization_id'] = str(payment['organization_id'])
            
            if current_role != 'student' and payment.get('student_id'):
                student = mongo.db.users.find_one({'_id': ObjectId(payment['student_id'])})
                if student:
                    payment['student_name'] = student.get('name', 'Unknown')
            
            payments.append(payment)
        
        total_count = mongo.db.payments.count_documents(filter_query)
        
        return jsonify({
            'payments': payments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get payments error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@mobile_api_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """Get users based on role and filters"""
    try:
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        role = request.args.get('role')
        search = request.args.get('search')
        group_id = request.args.get('group_id')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        filter_query = {}
        if current_org_id:
            filter_query['organization_id'] = current_org_id
        
        if role:
            filter_query['role'] = role
            
        if search:
            filter_query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'phone_number': {'$regex': search, '$options': 'i'}}
            ]
            
        if group_id:
            group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
            if group and group.get('students'):
                filter_query['_id'] = {'$in': group['students']}
            else:
                return jsonify({'users': [], 'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': 0,
                    'total_pages': 0
                }}), 200
        
        skip = (page - 1) * per_page
        users_cursor = mongo.db.users.find(filter_query).sort('name', 1).skip(skip).limit(per_page)
        
        users = []
        for user in users_cursor:
            user['_id'] = str(user['_id'])
            if user.get('organization_id'):
                user['organization_id'] = str(user['organization_id'])
            
            # Remove sensitive fields
            user.pop('password', None)
            user.pop('password_hash', None)
            
            users.append(user)
            
        total_count = mongo.db.users.count_documents(filter_query)
        
        return jsonify({
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get users error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# Groups endpoints
@mobile_api_bp.route('/student/attended-classes', methods=['GET'])
@jwt_required()
def get_student_attended_classes():
    """Get all classes that the student has attended (present/late status)"""
    try:
        # Get effective user ID (supports child profiles)
        current_user_id = get_effective_user_id()
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # This endpoint is primarily for students, but allow coaches/admins to query specific students
        target_student_id = request.args.get('student_id', current_user_id)
        
        # Security check: students can only query their own classes
        if current_role == 'student' and target_student_id != current_user_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        # Date filtering parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Query attended classes (present or late status)
        attendance_filter = {
            'student_id': ObjectId(target_student_id),
            'status': {'$in': ['present', 'late']}
        }
        
        # Add date filtering if provided
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
            if end_date:
                date_filter['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            attendance_filter['date'] = date_filter
        
        # Get attendance records sorted by date (most recent first)
        attended_records = list(mongo.db.attendance.find(attendance_filter)
                              .sort('date', -1)
                              .skip(skip)
                              .limit(per_page))
        
        # Enrich with class information
        attended_classes = []
        for record in attended_records:
            try:
                class_doc = mongo.db.classes.find_one({'_id': record['class_id']})
                if not class_doc:
                    continue  # Skip if class not found
                
                # Check organization access
                if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
                    continue
                
                # Safe date conversion
                attendance_date = None
                if record.get('date'):
                    if isinstance(record['date'], datetime):
                        attendance_date = record['date'].strftime('%Y-%m-%d')
                    else:
                        attendance_date = str(record['date'])
                
                # Safe datetime conversion
                marked_at = None
                if record.get('marked_at'):
                    if isinstance(record['marked_at'], datetime):
                        marked_at = record['marked_at'].isoformat()
                    else:
                        marked_at = str(record['marked_at'])
                
                # Safe scheduled_at conversion
                scheduled_at = None
                if class_doc.get('scheduled_at'):
                    if isinstance(class_doc['scheduled_at'], datetime):
                        scheduled_at = class_doc['scheduled_at'].isoformat()
                    else:
                        scheduled_at = str(class_doc['scheduled_at'])
                
                # Format the response
                attended_class = {
                    'attendance_id': str(record['_id']),
                    'attendance_status': record['status'],
                    'attendance_date': attendance_date,
                    'marked_at': marked_at,
                    'notes': record.get('notes', ''),
                    
                    # Class information
                    'class_id': str(class_doc['_id']),
                    'title': class_doc.get('title', 'Unknown'),
                    'scheduled_at': scheduled_at,
                    'duration_minutes': class_doc.get('duration_minutes', 60),
                    'sport': class_doc.get('sport'),
                    'level': class_doc.get('level'),
                    'coach_id': str(class_doc.get('coach_id')) if class_doc.get('coach_id') else None,
                }
                
                # Add coach information
                if class_doc.get('coach_id'):
                    coach = mongo.db.users.find_one({'_id': class_doc['coach_id']})
                    if coach:
                        attended_class['coach_name'] = coach.get('name', 'Unknown')
                        attended_class['coach_phone'] = coach.get('phone_number', '')
                
                # Add location display
                location = class_doc.get('location', {})
                if isinstance(location, dict):
                    if location.get('name'):
                        attended_class['location_display'] = location['name']
                    elif location.get('address'):
                        if isinstance(location['address'], str):
                            attended_class['location_display'] = location['address']
                        else:
                            # Handle complex address object
                            addr_parts = []
                            if location['address'].get('street'):
                                addr_parts.append(location['address']['street'])
                            if location['address'].get('city'):
                                addr_parts.append(location['address']['city'])
                            attended_class['location_display'] = ', '.join(addr_parts) if addr_parts else 'Location TBD'
                    else:
                        attended_class['location_display'] = 'Location TBD'
                else:
                    attended_class['location_display'] = str(location) if location else 'Location TBD'
                
                # Calculate duration display
                duration_minutes = class_doc.get('duration_minutes', 60)
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                if hours > 0 and minutes > 0:
                    attended_class['duration_display'] = f'{hours}h {minutes}m'
                elif hours > 0:
                    attended_class['duration_display'] = f'{hours}h'
                else:
                    attended_class['duration_display'] = f'{minutes}m'

                # Add instructions from class_doc if they exist
                if class_doc.get('instructions'):
                    attended_class['instructions'] = class_doc['instructions']
                
                # Convert instruction keys to strings if instructions is a dict
                convert_instruction_keys_to_str(attended_class)
                
                # Ensure the attended_class is JSON serializable
                serializable_class = make_json_serializable(attended_class)
                attended_classes.append(serializable_class)
                
            except Exception as e:
                current_app.logger.error(f"Error processing attended class record: {str(e)}")
                continue  # Skip this record and continue with others
        
        # Get total count for pagination
        total_count = mongo.db.attendance.count_documents(attendance_filter)
        
        # Calculate summary statistics
        all_attended = mongo.db.attendance.count_documents({
            'student_id': ObjectId(target_student_id),
            'status': {'$in': ['present', 'late']}
        })
        
        # Get recent statistics (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_attended = mongo.db.attendance.count_documents({
            'student_id': ObjectId(target_student_id),
            'status': {'$in': ['present', 'late']},
            'date': {'$gte': thirty_days_ago}
        })

        
        return jsonify({
            'attended_classes': attended_classes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            },
            'summary': {
                'total_attended': all_attended,
                'recent_attended': recent_attended  # Last 30 days
            },
            'message': 'Attended classes retrieved successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get student attended classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/student/next-class', methods=['GET'])
@jwt_required()
def get_student_next_class():
    """Get the student's next upcoming class"""
    try:
        # Get effective user ID (supports child profiles)
        effective_user_id = get_effective_user_id()
        current_user_id = effective_user_id
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        print(current_role)
        current_org_id = claims.get('organization_id')
        
        # This endpoint is primarily for students, but allow coaches/admins to query specific students
        target_student_id = request.args.get('student_id', effective_user_id)
        
        # Get the next upcoming class for the student
        now = datetime.utcnow() - timedelta(hours=1, minutes=30)
        
        filter_query = {
            'scheduled_at': {'$gte': now},
            'status': {'$in': ['scheduled', 'ongoing']}
        }
        
        # Security check: students can only query their own classes
        filter_query['student_ids'] = ObjectId(target_student_id)
        
        
        
        
        if current_org_id:
            filter_query['organization_id'] = ObjectId(current_org_id)

        print(filter_query)
        
        # Find the next class (sorted by scheduled_at ascending)
        next_class = mongo.db.classes.find_one(
            filter_query,
            sort=[('scheduled_at', 1)]
        )

        print('next_class', next_class['scheduled_at'], now, datetime.utcnow())
        if not next_class:
            return jsonify({
                'next_class': None,
                'message': 'No upcoming classes found'
            }), 200

        existing_attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(next_class['_id']),
            'student_id': ObjectId(current_user_id)
        })

        next_class['attendance'] = 'Not marked'
        if existing_attendance is not None:
            next_class['attendance'] = 'Present'
        

        next_class['scheduled_at'] = next_class['scheduled_at'] + timedelta(hours=5, minutes=30)

        # Format the class data
        next_class['_id'] = str(next_class['_id'])
        if next_class.get('coach_id'):
            next_class['coach_id'] = str(next_class['coach_id'])
        if next_class.get('organization_id'):
            next_class['organization_id'] = str(next_class['organization_id'])
        if next_class.get('student_ids'):
            next_class['student_ids'] = [str(s) for s in next_class['student_ids']]
        if next_class.get('group_ids'):
            next_class['group_ids'] = [str(g) for g in next_class['group_ids']]

        if next_class.get('location'):
            if next_class['location'].get('center_id'):
                next_class['location']['center_id'] = str(next_class['location']['center_id'])
        
        # Convert datetime fields to ISO format
        if next_class.get('scheduled_at'):
            next_class['scheduled_at'] = next_class['scheduled_at'].isoformat()
        if next_class.get('created_at'):
            next_class['created_at'] = next_class['created_at'].isoformat()
        if next_class.get('updated_at'):
            next_class['updated_at'] = next_class['updated_at'].isoformat()
        # if next_class.get('cancelled_at'):
        #     next_class['cancelled_at'] = next_class['cancelled_at'].isoformat()
        if next_class.get('schedule_item_id'):
            next_class['schedule_item_id'] = str(next_class['schedule_item_id'])
        
        # Add coach information
        coach = None
        if next_class.get('coach_id'):
            coach = mongo.db.users.find_one({'_id': ObjectId(next_class['coach_id'])}, {'name': 1})
            if coach:
                next_class['coachName'] = coach.get('name', 'Unknown')
        
        # Calculate time until class
        scheduled_time = datetime.fromisoformat(next_class['scheduled_at'].replace('Z', '+00:00'))
        time_until = scheduled_time - now
        
        # Add helpful time calculations
        total_minutes = int(time_until.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        days = total_minutes // (24 * 60)
        
        next_class['time_until'] = {
            'total_minutes': total_minutes,
            'hours': hours,
            'minutes': minutes,
            'days': days,
            'is_today': days == 0,
            'is_tomorrow': days == 1,
            'formatted_time_until': _format_time_until(total_minutes)
        }

        # Add RSVP info to class
        rsvp_info = mongo.db.rsvps.find_one({
            'class_id': ObjectId(next_class['_id']),
            'student_id': ObjectId(current_user_id)
        })

        if rsvp_info:
            next_class['rsvp_done'] = True
            next_class['user_rsvp_status'] = rsvp_info['rsvp_status']
        
        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(next_class)
        
        print(next_class)

        
        return jsonify({
            'next_class': next_class,
            'message': 'Next class retrieved successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get student next class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/coach/next-class', methods=['GET'])
@jwt_required()
def get_coach_next_class():
    """Get the coach's next upcoming class or org_admin's next upcoming class for center"""
    try:
        current_user_id = get_jwt_identity()
        
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        # This endpoint is only for coaches and org_admins
        if current_role not in ['coach', 'coach_admin', 'org_admin', 'super_admin']:
            return jsonify({'error': 'Unauthorized - Coach access only'}), 403
        
        # Get the next upcoming class
        now = datetime.utcnow() - timedelta(hours=1, minutes=30)
        
        filter_query = {
            'scheduled_at': {'$gte': now},
            'status': {'$in': ['scheduled', 'ongoing']}
        }
        
        # For org_admin, show all classes in organization (no coach filter)
        # For coaches, only show their assigned classes
        if current_role == 'org_admin' or current_role == 'super_admin':
            # Org admin sees all classes in their organization
            if current_org_id:
                filter_query['organization_id'] = ObjectId(current_org_id)
        else:
            # Regular coaches see only their classes
            filter_query['coach_id'] = ObjectId(current_user_id)
            if current_org_id:
                filter_query['organization_id'] = ObjectId(current_org_id)

        print(filter_query)
        
        # Find the next class (sorted by scheduled_at ascending)
        next_class = mongo.db.classes.find_one(
            filter_query,
            sort=[('scheduled_at', 1)]
        )

        if not next_class:
            return jsonify({
                'next_class': None,
                'message': 'No upcoming classes found'
            }), 200
            
        
        
        next_class['scheduled_at'] = next_class['scheduled_at'] + timedelta(hours=5, minutes=30)
        # Format the class data
        next_class['_id'] = str(next_class['_id'])
        if next_class.get('coach_id'):
            next_class['coach_id'] = str(next_class['coach_id'])
        if next_class.get('organization_id'):
            next_class['organization_id'] = str(next_class['organization_id'])
        if next_class.get('student_ids'):
            next_class['student_ids'] = [str(s) for s in next_class['student_ids']]
        if next_class.get('group_ids'):
            next_class['group_ids'] = [str(g) for g in next_class['group_ids']]

        if next_class.get('location'):
            if next_class['location'].get('center_id'):
                next_class['location']['center_id'] = str(next_class['location']['center_id'])
        
        # Convert datetime fields to ISO format
        if next_class.get('scheduled_at'):
            next_class['scheduled_at'] = next_class['scheduled_at'].isoformat()
        if next_class.get('created_at'):
            next_class['created_at'] = next_class['created_at'].isoformat()
        if next_class.get('updated_at'):
            next_class['updated_at'] = next_class['updated_at'].isoformat()
        if next_class.get('schedule_item_id'):
            next_class['schedule_item_id'] = str(next_class['schedule_item_id'])
        
        # Add coach information
        coach = mongo.db.users.find_one({'_id': ObjectId(next_class['coach_id'])}, {'name': 1})
        if coach:
            next_class['coachName'] = coach.get('name', 'Unknown')
        
        # Calculate time until class
        scheduled_time = datetime.fromisoformat(next_class['scheduled_at'].replace('Z', '+00:00'))
        time_until = scheduled_time - now
        
        # Add helpful time calculations
        total_minutes = int(time_until.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        days = total_minutes // (24 * 60)
        
        next_class['time_until'] = {
            'total_minutes': total_minutes,
            'hours': hours,
            'minutes': minutes,
            'days': days,
            'is_today': days == 0,
            'is_tomorrow': days == 1,
            'formatted_time_until': _format_time_until(total_minutes)
        }

        # Add student count and info
        student_count = len(next_class.get('student_ids', []))
        next_class['student_count'] = student_count
        
        # Get student names for the class
        if next_class.get('student_ids'):
            student_ids = [ObjectId(sid) for sid in next_class['student_ids']]
            students = list(mongo.db.users.find(
                {'_id': {'$in': student_ids}},
                {'name': 1, 'phone_number': 1}
            ))
            next_class['students_info'] = [
                {
                    'id': str(student['_id']),
                    'name': student.get('name', 'Unknown')
                }
                for student in students
            ]

        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(next_class)
        
        return jsonify({
            'next_class': next_class,
            'message': 'Next class retrieved successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get coach next class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def _format_time_until(total_minutes):
    """Helper function to format time until class in human-readable format"""
    if total_minutes < 0:
        return "Class has started"
    elif total_minutes < 60:
        return f"{total_minutes} minutes"
    elif total_minutes < 24 * 60:
        hours = total_minutes // 60
        minutes = total_minutes % 60
        if minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{hours}h {minutes}m"
    else:
        days = total_minutes // (24 * 60)
        remaining_hours = (total_minutes % (24 * 60)) // 60
        if remaining_hours == 0:
            return f"{days} day{'s' if days != 1 else ''}"
        else:
            return f"{days}d {remaining_hours}h"

@mobile_api_bp.route('/users/groups', methods=['GET'])
@jwt_required()
def get_groups():
    """Get groups/classes available to the current user"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        filter_query = {}
        if current_org_id:
            filter_query['organization_id'] = ObjectId(current_org_id)
        
        if current_role == 'student':
            filter_query['students'] = ObjectId(current_user_id)
        elif current_role == 'coach':
            filter_query['coach_id'] = ObjectId(current_user_id)
        
        groups_cursor = mongo.db.groups.find(filter_query)
        groups = []
        
        for group in groups_cursor:
            group['_id'] = str(group['_id'])
            if group.get('coach_id'):
                group['coach_id'] = str(group['coach_id'])
            if group.get('organization_id'):
                group['organization_id'] = str(group['organization_id'])
            if group.get('students'):
                group['students'] = [str(s) for s in group['students']]
            
            if group.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': ObjectId(group['coach_id'])})
                if coach:
                    group['coach_name'] = coach.get('name', 'Unknown')
            
            group['student_count'] = len(group.get('students', []))
            groups.append(group)
        
        return jsonify({'groups': groups}), 200
    
    except Exception as e:
        current_app.logger.error(f"Get groups error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# QR Attendance endpoints
@mobile_api_bp.route('/attendance/generate-qr', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def generate_qr_code():
    """Generate QR code for attendance marking"""
    try:
        data = request.get_json()
        qr_type = data.get('type')  # 'center' or 'class'
        center_id = data.get('center_id')
        class_id = data.get('class_id')
        
        if qr_type not in ['center', 'class']:
            return jsonify({'error': 'Invalid type. Must be "center" or "class"'}), 400
        
        if qr_type == 'center':
            if not center_id:
                return jsonify({'error': 'center_id is required for center-based QR'}), 400
            
            # Verify center exists and user has access
            center = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
            if not center:
                return jsonify({'error': 'Center not found'}), 404
            
            payload = {
                'center_id': center_id,
                'type': 'center'
            }
        
        elif qr_type == 'class':
            if not class_id:
                return jsonify({'error': 'class_id is required for class-based QR'}), 400
            
            # Verify class exists and user has access
            class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_doc:
                return jsonify({'error': 'Class not found'}), 404
            
            payload = {
                'class_id': class_id,
                'type': 'class'
            }
        
        # Generate signed token
        qr_token = generate_qr_token(payload)
        
        # Calculate expiry time
        valid_until = datetime.utcnow() + timedelta(minutes=QR_TOKEN_VALIDITY_MINUTES)
        
        return jsonify({
            'qrCode': qr_token,
            'type': qr_type,
            'validUntil': valid_until.isoformat(),
            'message': 'QR code generated successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Generate QR code error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/attendance/mark', methods=['POST'])
@jwt_required()
def mark_attendance_from_qr():
    """Mark attendance using QR code"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        qr_token = data.get('qrCode')
        
        if not qr_token:
            return jsonify({'error': 'QR code is required'}), 400
        
        # Validate and decode QR token
        payload, error = validate_qr_token(qr_token)
        if error:
            return jsonify({'error': error}), 400
        
        # Get current user to verify they are a student
        current_user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not current_user or current_user.get('role') != 'student':
            return jsonify({'error': 'Only students can mark attendance'}), 403
        
        class_doc = None
        scan_time = datetime.utcnow()
        
        # Resolve class based on QR type
        if payload['type'] == 'center':
            center_id = payload['center_id']
            class_doc, error = resolve_active_class(center_id, scan_time)
            if error:
                return jsonify({'error': error}), 400
        
        elif payload['type'] == 'class':
            class_id = payload['class_id']
            class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_doc:
                return jsonify({'error': 'Class not found'}), 404
            
            # Check if class is within reasonable time window (30 minutes before to 4 hours after)
            scheduled_time = class_doc['scheduled_at']
            time_diff = (scan_time - scheduled_time).total_seconds() / 60  # in minutes
            
            # if time_diff < -30:  # More than 30 minutes before class
            #     return jsonify({'error': 'Class has not started yet'}), 400
            # elif time_diff > 240:  # More than 4 hours after class
            #     return jsonify({'error': 'Class attendance window has closed'}), 400
        
        # Verify student is enrolled in this class
        student_ids = [str(sid) for sid in class_doc.get('student_ids', [])]
        if current_user_id not in student_ids:
            return jsonify({'error': 'You are not enrolled in this class'}), 403
        
        # Check if attendance is already marked for this class
        existing_attendance = mongo.db.attendance.find_one({
            'class_id': class_doc['_id'],
            'student_id': ObjectId(current_user_id)
        })
        
        if existing_attendance:
            return jsonify({
                'success': False,
                'message': 'Attendance already marked for this class',
                'classId': str(class_doc['_id']),
                'className': class_doc.get('title', 'Unknown'),
                'status': existing_attendance.get('status')
            }), 200
        
        # Mark attendance as present
        attendance_record = {
            'class_id': class_doc['_id'],
            'student_id': ObjectId(current_user_id),
            'status': 'present',
            'date': scan_time.strftime('%Y-%m-%d'),
            'marked_at': scan_time.strftime('%Y-%m-%d %H:%M:%S'),
            'marked_by': ObjectId(current_user_id),
            'method': 'qr_scan',
            'notes': 'Marked via QR code scan'
        }
        
        result = mongo.db.attendance.insert_one(attendance_record)
        
        if result.inserted_id:
            # Check for weekly attendance reward (4 classes in a week)
            weekly_reward_earned = False
            coins_earned = 0
            reward_message = ''
            
            try:
                awarded, message, coins = CoinService.check_weekly_attendance_reward(current_user_id)
                if awarded:
                    weekly_reward_earned = True
                    coins_earned = coins
                    reward_message = message
                    current_app.logger.info(f"User {current_user_id} earned weekly attendance bonus: {coins} coins")
            except Exception as e:
                current_app.logger.error(f"Error checking weekly attendance reward: {str(e)}")
                # Don't fail the attendance marking if coin reward fails
            
            response_data = {
                'success': True,
                'classId': str(class_doc['_id']),
                'className': class_doc.get('title', 'Unknown'),
                'message': 'Attendance marked successfully'
            }
            
            # Add coin reward info if earned
            if weekly_reward_earned:
                response_data['coinsEarned'] = coins_earned
                response_data['coinMessage'] = reward_message
            
            return jsonify(response_data), 200
        else:
            return jsonify({'error': 'Failed to mark attendance'}), 500
    
    except Exception as e:
        current_app.logger.error(f"Mark attendance from QR error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Student Interaction Features
@mobile_api_bp.route('/student/rsvp', methods=['POST'])
@jwt_required()
@require_role(['student'])
def student_rsvp():
    """Student RSVP to a class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        class_id = data.get('class_id')
        rsvp_status = data.get('rsvp_status')  # 'going', 'maybe', 'not_going'
        reason = data.get('reason')  # Required for not_going
        print(data)
        if not class_id or not rsvp_status:
            return jsonify({'error': 'Class ID and RSVP status are required'}), 400
        
        if rsvp_status not in ['going', 'maybe', 'not_going']:
            return jsonify({'error': 'Invalid RSVP status. Must be going, maybe, or not_going'}), 400
            
        if rsvp_status == 'not_going' and not reason:
            return jsonify({'error': 'Reason is required when marking not going'}), 400
        
        # Validate class exists
        class_doc = mongo.db.classes.find_one({
            '_id': ObjectId(class_id),
        })
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check if class is in the future
        if class_doc['scheduled_at'] <= datetime.now():
            return jsonify({'error': 'Cannot RSVP to past classes'}), 400
        
        # Check if student is enrolled
        if ObjectId(current_user_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'You are not enrolled in this class'}), 403
        
        # If marking as not_going, remove student from class
        if rsvp_status == 'not_going':
            # Remove student from class
            result = mongo.db.classes.update_one(
                {'_id': ObjectId(class_id)},
                {
                    '$pull': {'student_ids': ObjectId(current_user_id)},
                    '$set': {'updated_at': datetime.now()}
                }
            )
            
            # Create cancellation record
            cancellation_data = {
                'class_id': ObjectId(class_id),
                'student_id': ObjectId(current_user_id),
                'cancelled_by': ObjectId(current_user_id),
                'cancelled_by_role': 'student',
                'organization_id': ObjectId(current_org_id) if current_org_id else None,
                'cancelled_at': datetime.now(),
                'reason': reason,
                'type': 'rsvp_not_going'  # To distinguish from explicit cancellations
            }
            
            mongo.db.cancellations.insert_one(cancellation_data)
        
        # Update or create RSVP record
        rsvp_data = {
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'rsvp_status': rsvp_status,
            'updated_at': datetime.now()
        }
        
        if reason:
            rsvp_data['reason'] = reason
        
        # Upsert RSVP record
        result = mongo.db.rsvps.update_one(
            {
                'class_id': ObjectId(class_id),
                'student_id': ObjectId(current_user_id)
            },
            {
                '$set': rsvp_data,
                '$setOnInsert': {'created_at': datetime.now()}
            },
            upsert=True
        )
        
        # Get updated class
        updated_class = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        # Format the response
        response_class = make_json_serializable(updated_class)
        
        # Add coach info
        if updated_class.get('coach_id'):
            coach = mongo.db.users.find_one({'_id': updated_class['coach_id']})
            if coach:
                response_class['coach_name'] = coach.get('name', 'Unknown')
        
        # Add RSVP info
        rsvp_info = mongo.db.rsvps.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id)
        })
        
        if rsvp_info:
            response_class['user_rsvp_status'] = rsvp_info['rsvp_status']
            if rsvp_info.get('reason'):
                response_class['user_rsvp_reason'] = rsvp_info['reason']
        
        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(response_class)
        
        response_data = {
            'message': f'RSVP updated to {rsvp_status}',
            'class': response_class
        }
        
        # Add cancellation info if not going
        if rsvp_status == 'not_going':
            response_data['cancellation'] = {
                'reason': reason,
                'cancelled_at': datetime.now().isoformat(),
                'cancelled_by': {
                    'id': current_user_id,
                    'role': 'student'
                }
            }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Student RSVP error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/send-instructions', methods=['POST'])
@jwt_required()
@require_role(['coach', 'org_admin', 'super_admin'])
def send_class_instructions(class_id):
    """Send instructions to students for a class (coach and org_admin only)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        instructions = data.get('instructions', '').strip()
        
        if not instructions:
            return jsonify({'error': 'Instructions are required'}), 400
        
        # Validate class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check if user has permission
        if current_role == 'coach':
            # Coach can only send instructions for their own classes
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Unauthorized - You can only send instructions for your own classes'}), 403
        elif current_role in ['org_admin', 'super_admin']:
            # Org admin can send instructions for any class in their organization
            if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
                return jsonify({'error': 'Unauthorized - Class not in your organization'}), 403
        
        # Check if class has started
        if class_doc['scheduled_at'] <= datetime.utcnow():
            return jsonify({'error': 'Cannot send instructions for classes that have already started'}), 400
        
        # Update class with instructions
        mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {
                '$set': {
                    'instructions': instructions,
                    'instructions_sent_at': datetime.utcnow(),
                    'instructions_sent_by': ObjectId(current_user_id),
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        # Send WhatsApp messages to all enrolled students
        from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
        whatsapp_service = EnhancedWhatsAppService()
        
        student_ids = class_doc.get('student_ids', [])
        sent_count = 0
        failed_count = 0
        
        scheduled_at = class_doc['scheduled_at']
        class_title = class_doc.get('title', 'Class')
        
        for student_id in student_ids:
            try:
                student = mongo.db.users.find_one({'_id': ObjectId(student_id)})
                if student and student.get('phone_number'):
                    phone_number = student['phone_number']
                    student_name = student.get('name', 'Student')
                    
                    # Send instructions using template message
                    success, message = whatsapp_service.send_class_instructions_message(
                        phone_number=phone_number,
                        student_name=student_name,
                        class_title=class_title,
                        scheduled_at=scheduled_at,
                        instructions=instructions
                    )
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                current_app.logger.error(f"Error sending instructions to student {student_id}: {str(e)}")
                failed_count += 1
        
        return jsonify({
            'message': 'Instructions sent successfully',
            'sent_count': sent_count,
            'failed_count': failed_count
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Send class instructions error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/instructions', methods=['GET'])
@jwt_required()
def get_class_instructions(class_id):
    """Get instructions for a class (all authenticated users)"""
    try:
        # Validate class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Get instructions if they exist
        instructions = class_doc.get('instructions')
        instructions_sent_at = class_doc.get('instructions_sent_at')
        instructions_sent_by = class_doc.get('instructions_sent_by')
        
        if not instructions:
            return jsonify({
                'instructions': None,
                'instructions_sent_at': None,
                'instructions_sent_by': None
            }), 200
        
        # Get sender info if available
        sender_info = None
        if instructions_sent_by:
            sender = mongo.db.users.find_one({'_id': instructions_sent_by}, {'name': 1, '_id': 1})
            if sender:
                sender_info = {
                    'id': str(sender['_id']),
                    'name': sender.get('name', 'Unknown')
                }
        
        return jsonify({
            'instructions': instructions,
            'instructions_sent_at': instructions_sent_at.isoformat() if instructions_sent_at else None,
            'instructions_sent_by': sender_info
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get class instructions error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/cancel', methods=['POST'])
@jwt_required()
@require_role(['coach', 'org_admin', 'super_admin'])
def cancel_class(class_id):
    """Cancel a class (coach and org_admin only)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_role = claims.get('role', 'student')
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        reason = data.get('reason', '').strip()
        cancellation_type = data.get('cancellation_type', 'manual')
        refund_required = data.get('refund_required', False)
        send_notifications = data.get('send_notifications', True)
        
        if not reason:
            return jsonify({'error': 'Cancellation reason is required'}), 400
        
        # Validate class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check if user has permission
        if current_role == 'coach':
            # Coach can only cancel their own classes
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Unauthorized - You can only cancel your own classes'}), 403
        elif current_role in ['org_admin', 'super_admin']:
            # Org admin can cancel any class in their organization
            if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
                return jsonify({'error': 'Unauthorized - Class not in your organization'}), 403
        
        # Check if class can be cancelled
        if class_doc.get('status') in ['cancelled', 'completed']:
            return jsonify({'error': f'Cannot cancel class with status: {class_doc.get("status")}'}), 400
        
        # Use cancellation service if available
        try:
            from app.services.cancellation_service import CancellationService
            success, message, class_data = CancellationService.cancel_class(
                class_id=class_id,
                reason=reason,
                cancelled_by=str(current_user_id),
                cancellation_type=cancellation_type,
                refund_required=refund_required,
                send_notifications=send_notifications,
                replacement_class_id=data.get('replacement_class_id')
            )
            
            if success:
                return jsonify({
                    'message': message,
                }), 200
            else:
                return jsonify({'error': message}), 400
        except ImportError:
            # Fallback if cancellation service not available
            # Update class status directly
            mongo.db.classes.update_one(
                {'_id': ObjectId(class_id)},
                {
                    '$set': {
                        'status': 'cancelled',
                        'cancellation_reason': reason,
                        'cancelled_by': ObjectId(current_user_id),
                        'cancelled_at': datetime.utcnow(),
                        'cancellation_type': cancellation_type,
                        'refund_required': refund_required,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Get updated class
            updated_class = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            updated_class['_id'] = str(updated_class['_id'])
            
            return jsonify({
                'message': 'Class cancelled successfully',
            }), 200
    
    except Exception as e:
        current_app.logger.error(f"Cancel class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/student/review-class', methods=['POST'])
@jwt_required()
@require_role(['student'])
def student_review_class():
    """Student review a completed class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        class_id = data.get('class_id')
        rating = data.get('rating')
        comment = data.get('comment', '')
        
        if not class_id or rating is None:
            return jsonify({'error': 'Class ID and rating are required'}), 400
        
        # Validate rating
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400
        
        # Validate class exists and is past
        class_doc = mongo.db.classes.find_one({
            '_id': ObjectId(class_id),
            'organization_id': ObjectId(current_org_id) if current_org_id else None
        })
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check if class is in the past and completed
        if class_doc['scheduled_at'] > datetime.now():
            return jsonify({'error': 'Cannot review future classes'}), 400
        
        # Check if student attended this class
        attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'status': {'$in': ['present', 'late']}
        })
        
        if not attendance:
            return jsonify({'error': 'You can only review classes you attended'}), 403
        
        # Check if review already exists
        existing_review = mongo.db.reviews.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id)
        })
        
        if existing_review:
            return jsonify({'error': 'You have already reviewed this class'}), 400
        
        # Create review record
        review_data = {
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'organization_id': ObjectId(current_org_id) if current_org_id else None,
            'rating': rating,
            'comment': comment.strip() if comment else '',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        result = mongo.db.reviews.insert_one(review_data)
        
        # Get student info for the response
        student = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        
        review_data['_id'] = result.inserted_id
        review_data['student_name'] = student.get('name', 'Unknown') if student else 'Unknown'
        
        return jsonify({
            'message': 'Review submitted successfully',
            'review': make_json_serializable(review_data)
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Student review class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/student/classes-pending-review', methods=['GET'])
@jwt_required()
@require_role(['student'])
def get_classes_pending_review():
    """Get classes attended by student that haven't been reviewed yet"""
    try:
        # Get effective user ID (supports child profiles)
        current_user_id = get_effective_user_id()
        
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        # Get attended classes that are past and not reviewed
        # First get all attendance records for the student
        attendance_records = list(mongo.db.attendance.find({
            'student_id': ObjectId(current_user_id),
            'status': {'$in': ['present', 'late']}  # Only classes actually attended
        }))
        
        if not attendance_records:
            return jsonify({
                'classes_pending_review': [],
                'count': 0
            }), 200
        
        attended_class_ids = [record['class_id'] for record in attendance_records]
        
        # Get classes that are past
        past_classes = list(mongo.db.classes.find({
            '_id': {'$in': attended_class_ids},
            'scheduled_at': {'$lt': datetime.now()},
            'organization_id': ObjectId(current_org_id) if current_org_id else None
        }))
        
        if not past_classes:
            return jsonify({
                'classes_pending_review': [],
                'count': 0
            }), 200
        
        # Check which classes haven't been reviewed
        past_class_ids = [cls['_id'] for cls in past_classes]
        
        # Get existing reviews for these classes by this student
        existing_reviews = list(mongo.db.reviews.find({
            'class_id': {'$in': past_class_ids},
            'student_id': ObjectId(current_user_id)
        }))
        
        reviewed_class_ids = [review['class_id'] for review in existing_reviews]
        
        # Filter out classes that have been reviewed
        classes_pending_review = [
            cls for cls in past_classes 
            if cls['_id'] not in reviewed_class_ids
        ]
        
        # Sort by scheduled date (oldest first)
        classes_pending_review.sort(key=lambda x: x['scheduled_at'])
        
        # Enhance classes with additional info
        for class_doc in classes_pending_review:
            # Add coach info
            if class_doc.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': class_doc['coach_id']})
                if coach:
                    class_doc['coach_name'] = coach.get('name')
                    class_doc['coach_phone'] = coach.get('phone_number')
            
            # Add location info
            if class_doc.get('location_id'):
                location = mongo.db.centers.find_one({'_id': class_doc['location_id']})
                if location:
                    class_doc['location'] = location
            
            # Mark that this class needs review
            class_doc['user_has_reviewed'] = False
            
            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(class_doc)
        
        return jsonify({
            'classes_pending_review': make_json_serializable(classes_pending_review),
            'count': len(classes_pending_review)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get classes pending review error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/student/cancel-class', methods=['POST'])
@jwt_required()
@require_role(['student'])
def student_cancel_class():
    """Student cancel a single class with reason"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        class_id = data.get('class_id')
        reason = data.get('reason')
        
        if not class_id:
            return jsonify({'error': 'Class ID is required'}), 400
            
        if not reason:
            return jsonify({'error': 'Cancellation reason is required'}), 400
        
        # Validate class exists
        class_doc = mongo.db.classes.find_one({
            '_id': ObjectId(class_id),
            'organization_id': ObjectId(current_org_id) if current_org_id else None
        })
        
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Check if class is in the future
        if class_doc['scheduled_at'] <= datetime.now():
            return jsonify({'error': 'Cannot cancel past classes'}), 400
        
        # Check if class is already cancelled
        if class_doc.get('status') == 'cancelled':
            return jsonify({'error': 'Class is already cancelled'}), 400
        
        # Check if student is enrolled
        if ObjectId(current_user_id) not in class_doc.get('student_ids', []):
            return jsonify({'error': 'You are not enrolled in this class'}), 403
        
        # Remove student from class
        result = mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {
                '$pull': {'student_ids': ObjectId(current_user_id)},
                '$set': {'updated_at': datetime.now()}
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to cancel class'}), 500
        
        # Create cancellation record
        cancellation_data = {
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'cancelled_by': ObjectId(current_user_id),
            'cancelled_by_role': 'student',
            'organization_id': ObjectId(current_org_id) if current_org_id else None,
            'cancelled_at': datetime.now(),
            'reason': reason,
            'type': 'student_withdrawal'  # To distinguish from full class cancellations
        }
        
        mongo.db.cancellations.insert_one(cancellation_data)
        
        # Get updated class
        updated_class = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        
        # Format the response
        response_class = make_json_serializable(updated_class)
        
        # Add coach info
        if updated_class.get('coach_id'):
            coach = mongo.db.users.find_one({'_id': updated_class['coach_id']})
            if coach:
                response_class['coach_name'] = coach.get('name', 'Unknown')
        
        # Add RSVP info
        rsvp_info = mongo.db.rsvps.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id)
        })
        
        if rsvp_info:
            response_class['user_rsvp_status'] = rsvp_info['rsvp_status']
        
        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(response_class)
        
        return jsonify({
            'message': 'Successfully cancelled class registration',
            'class': response_class,
            'cancellation': {
                'reason': reason,
                'cancelled_at': datetime.now().isoformat(),
                'cancelled_by': {
                    'id': current_user_id,
                    'role': 'student'
                }
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Student cancel class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/explore/organizations', methods=['GET'])
@jwt_required()
def get_explore_organizations():
    """Get list of all organizations for explore feature"""
    try:
        # Get all active organizations
        organizations = list(mongo.db.organizations.find({
            'status': 'active',
        }))

        print(organizations)
        
        # Format organizations
        formatted_orgs = []
        for org in organizations:
            # Get sports from activities
            sports = []
            print("org", org, type(org))
            if org.get('activities'):
                sports = [activity for activity in org.get('activities', []) if activity]
            
            print("sports", sports)
            
            formatted_org = {
                'id': str(org['_id']),
                'name': org.get('name', 'Unknown'),
                'sports': sports,
                'contact_info': {
                    'phone': org.get('whatsapp_number') or org.get('contact_info', {}),
                    'email': org.get('contact_info', {}).get('email'),
                    'address': org.get('address', {})
                },
                'is_active': org.get('status', 'active') == 'active',
                # Additional fields for explore view
                'description': org.get('description', ''),
                'banner_url': org.get('banner_url', ''),
                'logo_url': org.get('logo_url', '')
            }
            formatted_orgs.append(formatted_org)
        
        print("formatted_orgs", formatted_orgs)
        
        return jsonify({
            'organizations': formatted_orgs,
            'count': len(formatted_orgs)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get explore organizations error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/explore/organizations/<org_id>/coaches', methods=['GET'])
@jwt_required()
def get_organization_coaches(org_id):
    """Get coaches for an organization with their details"""
    try:
        # Validate organization exists
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Get all coaches for this organization
        coaches = list(mongo.db.users.find({
            'organization_id': ObjectId(org_id),
            'role': 'coach',
        }))
        
        formatted_coaches = []
        for coach in coaches:
            # Get profile data
            profile_data = coach.get('profile_data', {})
            
            # Get count of classes taught (lifetime)
            classes_taught = mongo.db.classes.count_documents({
                'coach_id': coach['_id'],
                'status': {'$in': ['completed', 'scheduled', 'ongoing']}
            })
            
            formatted_coach = {
                'id': str(coach['_id']),
                'name': coach.get('name', 'Unknown'),
                'profile_picture_url': coach.get('profile_picture_url', ''),
                'specialization': profile_data.get('specialization', 'General Coaching'),
                'years_of_experience': profile_data.get('years_of_experience', 0),
                'achievements': coach.get('achievements', []),
                'bio': profile_data.get('bio', ''),
                'classes_taught': classes_taught,
                'phone_number': coach.get('phone_number', ''),
                'email': coach.get('email', ''),
            }
            formatted_coaches.append(formatted_coach)
        
        return jsonify({
            'coaches': formatted_coaches,
            'count': len(formatted_coaches)
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get organization coaches error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/explore/organizations/<org_id>/classes', methods=['GET'])
@jwt_required()
def get_organization_classes(org_id):
    """Get upcoming classes for an organization grouped by center"""
    try:
        # Validate organization exists
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Get all centers for this organization
        centers = list(mongo.db.centers.find({'organization_id': ObjectId(org_id)}))
        
        # Get classes for next 5 days for each center
        now = datetime.utcnow()
        end_date = now + timedelta(days=5)

        start_date = now
        end_date = end_date
        if 'date' in request.args:
            date = request.args.get('date')
            if 'T' in date:
                date = date.split('T')[0]
            date = datetime.strptime(date, '%Y-%m-%d')
            start_date = date
            end_date = date + timedelta(days=1)
        
        centers_with_classes = []
        for center in centers:
            # Get classes for this center (only bookable classes)
            classes = list(mongo.db.classes.find({
                'organization_id': ObjectId(org_id),
                'location.center_id': center['_id'],
                'scheduled_at': {'$gte': start_date, '$lt': end_date},
                'status': {'$in': ['scheduled', 'ongoing']},
                'is_bookable': {'$ne': False}  # Include only bookable classes (True or undefined/null)
            }).sort('scheduled_at', 1))
            
            # Format classes
            formatted_classes = []
            for class_doc in classes:
                # Get coach info
                coach_name = 'Unknown'
                if class_doc.get('coach_id'):
                    coach = mongo.db.users.find_one({'_id': class_doc['coach_id']})
                    if coach:
                        coach_name = coach.get('name', 'Unknown')
                
                # Check if current user is enrolled
                current_user_id = get_jwt_identity()
                is_user_enrolled = ObjectId(current_user_id) in class_doc.get('student_ids', [])

                formatted_class = {
                    'id': str(class_doc['_id']),
                    'title': class_doc.get('title', 'Unknown'),
                    'scheduled_at': (class_doc['scheduled_at'] + timedelta(hours=5, minutes=30)).isoformat(),
                    'duration_minutes': class_doc.get('duration_minutes', 60),
                    'sport': class_doc.get('sport', ''),
                    'level': class_doc.get('level', ''),
                    'coach_name': coach_name,
                    'student_count': len(class_doc.get('student_ids', [])),
                    'is_user_enrolled': is_user_enrolled,
                    'price': class_doc.get('price', 0)
                }
                
                # Add instructions if they exist
                if class_doc.get('instructions'):
                    formatted_class['instructions'] = class_doc['instructions']
                
                # Convert instruction keys to strings if instructions is a dict
                convert_instruction_keys_to_str(formatted_class)
                
                print(class_doc)
                formatted_classes.append(formatted_class)
            
            if formatted_classes:  # Only include centers that have classes
                centers_with_classes.append({
                    'center_id': str(center['_id']),
                    'center_name': center.get('name', 'Unknown'),
                    'address': center.get('address', {}),
                    'classes': formatted_classes
                })
        
        return jsonify({
            'organization': {
                'id': str(org['_id']),
                'name': org.get('name', 'Unknown'),
                'description': org.get('description', ''),
                'banner_url': org.get('banner_url', ''),
                'logo_url': org.get('logo_url', '')
            },
            'centers': centers_with_classes
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get organization classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/book', methods=['POST'])
@jwt_required()
def book_class(class_id):
    """Book a class for the current user"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        booked_by = ObjectId(current_user_id)
        data = request.get_json()
        if 'friend_id' in data:
            current_user_id = data['friend_id']

        print("current_user_id", current_user_id, current_org_id, class_id, data)

        # Validate class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404

        # Check if class is in the future
        if class_doc['scheduled_at'] <= datetime.now():
            return jsonify({'error': 'Cannot book past classes'}), 400

        # Check if class is already full
        student_count = len(class_doc.get('student_ids', []))
        if student_count >= class_doc.get('capacity', 20):
            return jsonify({'error': 'Class is full'}), 400

        # Check if user is already enrolled
        if ObjectId(current_user_id) in class_doc.get('student_ids', []):
            return jsonify({'error': 'You are already enrolled in this class'}), 400

        # Add student to class
        result = mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {
                '$addToSet': {'student_ids': ObjectId(current_user_id)},
                '$set': {'updated_at': datetime.now()}
            }
        )

        if result.modified_count == 0:
            return jsonify({'error': 'Failed to book class'}), 500

        # Create booking record
        booking_data = {
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'organization_id': ObjectId(current_org_id) if current_org_id else None,
            'booked_at': datetime.now(),
            'status': 'confirmed',
            'booked_by': booked_by
        }
        booking_result = mongo.db.bookings.insert_one(booking_data)

        # Award Botle Coins for booking
        booking_for_friend = 'friend_id' in data
        if booking_for_friend:
            # Booking for someone else: +15 coins
            CoinService.award_coins(
                user_id=booked_by,
                amount=15,
                reason=CoinTransaction.REASON_OTHER_BOOKING,
                description=f"Booked a class for a friend",
                reference_id=class_id,
                reference_type='class'
            )
            current_app.logger.info(f"Awarded 15 coins to user {booked_by} for booking class for friend")
        else:
            # Booking for self: +5 coins
            CoinService.award_coins(
                user_id=booked_by,
                amount=5,
                reason=CoinTransaction.REASON_SELF_BOOKING,
                description=f"Booked a class",
                reference_id=class_id,
                reference_type='class'
            )
            current_app.logger.info(f"Awarded 5 coins to user {booked_by} for booking class")

        # Get updated class
        updated_class = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        updated_class['_id'] = str(updated_class['_id'])
        if updated_class.get('coach_id'):
            updated_class['coach_id'] = str(updated_class['coach_id'])
        if updated_class.get('organization_id'):
            updated_class['organization_id'] = str(updated_class['organization_id'])
        if updated_class.get('student_ids'):
            updated_class['student_ids'] = [str(s) for s in updated_class['student_ids']]
        if updated_class.get('scheduled_at'):
            updated_class['scheduled_at'] = updated_class['scheduled_at'].isoformat()
        if updated_class.get('schedule_item_id'):   
            updated_class['schedule_item_id'] = str(updated_class['schedule_item_id'])
        if updated_class.get('location'):   
            if updated_class['location'].get('center_id'):
                updated_class['location']['center_id'] = str(updated_class['location']['center_id'])
        
        # Convert instruction keys to strings if instructions is a dict
        convert_instruction_keys_to_str(updated_class)
        
        print("updated_class", updated_class)
        return jsonify({
            'message': 'Successfully booked class',
            'class': updated_class,
            'is_user_enrolled': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Book class error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@mobile_api_bp.route('/student/cancel-classes', methods=['POST'])
@jwt_required()
@require_role(['student'])
def student_cancel_classes():
    """Student cancel multiple classes (bulk operation)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        data = request.get_json()
        class_ids = data.get('class_ids', [])
        
        if not class_ids or not isinstance(class_ids, list):
            return jsonify({'error': 'class_ids must be a non-empty list'}), 400
        
        if len(class_ids) > 50:  # Limit bulk operations
            return jsonify({'error': 'Cannot cancel more than 50 classes at once'}), 400
        
        results = []
        
        for class_id in class_ids:
            try:
                # Validate class exists
                class_doc = mongo.db.classes.find_one({
                    '_id': ObjectId(class_id),
                    'organization_id': ObjectId(current_org_id) if current_org_id else None
                })
                
                if not class_doc:
                    results.append({
                        'class_id': class_id,
                        'success': False,
                        'error': 'Class not found'
                    })
                    continue
                
                # Check if class is in the future
                if class_doc['scheduled_at'] <= datetime.now():
                    results.append({
                        'class_id': class_id,
                        'success': False,
                        'error': 'Cannot cancel past classes'
                    })
                    continue
                
                # Check if class is already cancelled
                if class_doc.get('status') == 'cancelled':
                    results.append({
                        'class_id': class_id,
                        'success': False,
                        'error': 'Class is already cancelled'
                    })
                    continue
                
                # Check if student is enrolled
                if ObjectId(current_user_id) not in class_doc.get('student_ids', []):
                    results.append({
                        'class_id': class_id,
                        'success': False,
                        'error': 'You are not enrolled in this class'
                    })
                    continue
                
                # Remove student from class
                mongo.db.classes.update_one(
                    {'_id': ObjectId(class_id)},
                    {
                        '$pull': {'students': ObjectId(current_user_id)},
                        '$set': {'updated_at': datetime.now()}
                    }
                )
                
                # Create cancellation record
                cancellation_data = {
                    'class_id': ObjectId(class_id),
                    'student_id': ObjectId(current_user_id),
                    'organization_id': ObjectId(current_org_id) if current_org_id else None,
                    'cancelled_at': datetime.now(),
                    'reason': 'student_bulk_cancellation'
                }
                
                mongo.db.cancellations.insert_one(cancellation_data)
                
                results.append({
                    'class_id': class_id,
                    'success': True,
                    'message': 'Successfully cancelled'
                })
                
            except Exception as e:
                results.append({
                    'class_id': class_id,
                    'success': False,
                    'error': f'Error processing: {str(e)}'
                })
        
        # Count successful vs failed operations
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        return jsonify({
            'message': f'Bulk cancellation completed: {successful} successful, {failed} failed',
            'results': results,
            'summary': {
                'total': len(results),
                'successful': successful,
                'failed': failed
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Student bulk cancel classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Picture upload endpoints
@mobile_api_bp.route('/classes/<class_id>/upload-pictures', methods=['POST'])
@jwt_required()
@require_role(['coach', 'org_admin', 'coach_admin', 'super_admin'])
def upload_class_pictures(class_id):
    """Upload pictures for a class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        # Validate class exists and user has access
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Check if user is the coach or has admin privileges
        current_role = claims.get('role', 'student')
        if current_role not in ['org_admin', 'coach_admin', 'super_admin']:
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Only the class coach can upload pictures'}), 403
        
        print("request.files", request.files)
        # Get uploaded files
        if 'pictures' not in request.files:
            return jsonify({'error': 'No pictures uploaded'}), 400
        
        files = request.files.getlist('pictures')
        if not files or all(file.filename == '' for file in files):
            return jsonify({'error': 'No valid pictures uploaded'}), 400
        
        # Get description
        description = request.form.get('description', '').strip()
        
        # Initialize file upload service
        upload_service = FileUploadService()
        
        uploaded_files = []
        failed_uploads = []
        
        for file in files:
            if file and file.filename:
                # Upload to S3 using the file upload service
                success, message, file_url = upload_service.upload_file(
                    file=file,
                    upload_type='class_picture',
                    organization_id=current_org_id,
                    user_id=current_user_id
                )
                
                if success and file_url:
                    # Get file size from the file object
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    uploaded_files.append({
                        'filename': file_url,  # Store full S3 URL as filename
                        'original_filename': secure_filename(file.filename),
                        'file_url': file_url,
                        'file_size': file_size,
                        'uploaded_at': datetime.utcnow()
                    })
                else:
                    failed_uploads.append({
                        'filename': file.filename,
                        'error': message
                    })
        
        if not uploaded_files:
            error_msg = 'No files were successfully uploaded'
            if failed_uploads:
                error_msg += f'. Errors: {[f["error"] for f in failed_uploads]}'
            return jsonify({'error': error_msg}), 400
        
        # Create picture record in database
        picture_data = {
            'class_id': ObjectId(class_id),
            'uploaded_by': ObjectId(current_user_id),
            'organization_id': ObjectId(current_org_id) if current_org_id else None,
            'description': description if description else None,
            'pictures': uploaded_files,
            'uploaded_at': datetime.utcnow(),
            'status': 'active'
        }
        
        result = mongo.db.class_pictures.insert_one(picture_data)
        
        # Update class with picture count
        mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {
                '$inc': {'picture_count': len(uploaded_files)},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        # Get uploaded by user info
        uploader = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        uploader_name = uploader.get('name', 'Unknown') if uploader else 'Unknown'
        
        response_data = {
            'message': f'Successfully uploaded {len(uploaded_files)} picture(s)',
            'upload_id': str(result.inserted_id),
            'pictures_uploaded': len(uploaded_files),
            'uploaded_by': uploader_name,
            'uploaded_at': datetime.utcnow().isoformat(),
            'description': description if description else None
        }
        
        # Include failed uploads info if any
        if failed_uploads:
            response_data['failed_uploads'] = failed_uploads
            response_data['message'] += f' ({len(failed_uploads)} failed)'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        current_app.logger.error(f"Upload class pictures error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/pictures', methods=['GET'])
@jwt_required()
def get_class_pictures(class_id):
    """Get pictures for a class"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        # Validate class exists and user has access
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Check if user has access to this class
        current_role = claims.get('role', 'student')
        if current_role == 'student':
            if ObjectId(current_user_id) not in class_doc.get('student_ids', []):
                return jsonify({'error': 'Unauthorized access'}), 403
        elif current_role == 'coach':
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get pictures for this class
        pictures_cursor = mongo.db.class_pictures.find({
            'class_id': ObjectId(class_id),
            'status': 'active'
        }).sort('uploaded_at', -1)
        
        pictures = []
        for picture_doc in pictures_cursor:
            # Get uploader info
            uploader = mongo.db.users.find_one({'_id': picture_doc['uploaded_by']})
            uploader_name = uploader.get('name', 'Unknown') if uploader else 'Unknown'
            
            picture_info = {
                'id': str(picture_doc['_id']),
                'description': picture_doc.get('description'),
                'uploaded_by': uploader_name,
                'uploaded_at': picture_doc['uploaded_at'].isoformat(),
                'picture_count': len(picture_doc.get('pictures', [])),
                'pictures': []
            }
            
            # Add picture details
            for pic in picture_doc.get('pictures', []):
                picture_info['pictures'].append({
                    'filename': pic['filename'],  # This now contains the full S3 URL
                    'original_filename': pic['original_filename'],
                    'file_url': pic.get('file_url', pic['filename']),  # Fallback for backward compatibility
                    'file_size': pic['file_size'],
                    'uploaded_at': pic['uploaded_at'].isoformat()
                })
            
            pictures.append(picture_info)
        
        return jsonify({
            'pictures': pictures,
            'total_count': len(pictures)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get class pictures error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/classes/<class_id>/pictures/<picture_id>', methods=['DELETE'])
@jwt_required()
@require_role(['coach', 'org_admin', 'coach_admin', 'super_admin'])
def delete_class_picture(class_id, picture_id):
    """Delete a class picture"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')
        
        # Validate class exists and user has access
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        if current_org_id and str(class_doc.get('organization_id')) != current_org_id:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Check if user is the coach or has admin privileges
        current_role = claims.get('role', 'student')
        if current_role not in ['org_admin', 'coach_admin', 'super_admin']:
            if str(class_doc.get('coach_id')) != current_user_id:
                return jsonify({'error': 'Only the class coach can delete pictures'}), 403
        
        # Find the picture record
        picture_doc = mongo.db.class_pictures.find_one({
            '_id': ObjectId(picture_id),
            'class_id': ObjectId(class_id)
        })
        
        if not picture_doc:
            return jsonify({'error': 'Picture not found'}), 404
        
        # Delete physical files
        upload_dir = os.path.join(current_app.root_path, '..', 'uploads', 'class_pictures')
        for pic in picture_doc.get('pictures', []):
            file_path = os.path.join(upload_dir, pic['filename'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    current_app.logger.warning(f"Could not delete file: {file_path}")
        
        # Mark as deleted in database
        mongo.db.class_pictures.update_one(
            {'_id': ObjectId(picture_id)},
            {
                '$set': {
                    'status': 'deleted',
                    'deleted_at': datetime.utcnow(),
                    'deleted_by': ObjectId(current_user_id)
                }
            }
        )
        
        # Update class picture count
        picture_count = len(picture_doc.get('pictures', []))
        mongo.db.classes.update_one(
            {'_id': ObjectId(class_id)},
            {
                '$inc': {'picture_count': -picture_count},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        return jsonify({
            'message': 'Picture deleted successfully',
            'deleted_pictures': picture_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Delete class picture error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mobile_api_bp.route('/announcements/latest', methods=['GET'])
@jwt_required()
def mobile_get_latest_announcement():
    """Get the latest announcement for the organization"""
    try:
        # Get current user and organization
        current_user = get_jwt_identity()
        user = mongo.db.users.find_one({'_id': ObjectId(current_user)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Build query
        query = {
            'post_type': 'announcement',
            'organization_id': ObjectId(user['organization_id']),
            'status': 'published'
        }

        # Get latest announcement
        announcement = mongo.db.posts.find_one(query, sort=[('created_at', -1)])

        if not announcement:
            return jsonify({'success': True, 'announcement': None})

        # Format the announcement

        author_id = announcement['author_id']
        if isinstance(author_id, str):
            author_id = ObjectId(author_id)
        print({'_id': author_id})
        created_by = mongo.db.users.find_one({'_id': author_id})
        if not created_by:
                created_by = {'name': "Unknown"}


        associated_class = {}

        if announcement.get('associated_class') != None:
            for key, value in announcement.get('associated_class').items():
                if '_id' in key:
                    if isinstance(value, ObjectId):
                        associated_class[key] = str(value)
                        print("Converted _id to string", key)
                    else:
                        associated_class[key] = value

                else:
                    associated_class[key] = value

                if isinstance(associated_class[key], datetime):
                    print("Converted datetime to string", associated_class[key])
                    associated_class[key] = associated_class[key].isoformat()
                

                print(key, type(associated_class[key]))
                if isinstance(associated_class[key], dict):
                    for key2, value2 in associated_class[key].items():
                        if '_id' in key2:
                            if isinstance(value2, ObjectId):
                                associated_class[key][key2] = str(value2)
                            else:
                                associated_class[key][key2] = value2
                        else:
                            associated_class[key][key2] = value2

            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(associated_class)

            # Get likes and comments info
            likes = announcement.get('likes', [])
            comments = announcement.get('comments', [])
            user_oid = ObjectId(current_user)
            
            # Check if current user has liked this announcement
            is_liked = any(str(like) == current_user or (isinstance(like, ObjectId) and like == user_oid) for like in likes)
            
        formatted_announcement = {
            'id': str(announcement['_id']),
            'title': announcement['title'],
            'content': announcement['content'],
            'created_at': announcement['created_at'].isoformat(),
            'created_by': str(created_by['name']),
            'organization_id': str(announcement['organization_id']),
            'associated_class': associated_class if len(associated_class.keys()) > 0 else None,
            'media_urls': announcement.get('media_urls', []),
            'like_count': len(likes),
            'comment_count': len(comments),
            'is_liked': is_liked
        }
        
        

        return jsonify({
            'success': True,
            'announcement': formatted_announcement
        })

    except Exception as e:
        print(f"Error in get_latest_announcement: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch latest announcement'}), 500

@mobile_api_bp.route('/announcements', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'coach_admin', 'super_admin'])
def create_announcement():
    """Create an announcement with optional images (uses FileUploadService like picture upload)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        current_org_id = claims.get('organization_id')

        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        status = request.form.get('status', 'published').strip()

        if not title:
            return jsonify({'success': False, 'message': 'title is required'}), 400
        if not content:
            return jsonify({'success': False, 'message': 'content is required'}), 400

        media_urls = []
        failed_uploads = []

        if 'pictures' in request.files:
            files = request.files.getlist('pictures')
            upload_service = FileUploadService()
            for file in files:
                if file and file.filename:
                    success, message, file_url = upload_service.upload_file(
                        file=file,
                        upload_type='post_image',
                        organization_id=current_org_id,
                        user_id=current_user_id
                    )
                    if success and file_url:
                        media_urls.append(file_url)
                    else:
                        failed_uploads.append({'filename': secure_filename(file.filename), 'error': message})

        post_doc = {
            'title': title,
            'content': content,
            'post_type': 'announcement',
            'status': status,
            'organization_id': ObjectId(current_org_id) if current_org_id else None,
            'author_id': ObjectId(current_user_id),
            'media_urls': media_urls,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        result = mongo.db.posts.insert_one(post_doc)

        response = {
            'success': True,
            'message': 'Announcement created successfully',
            'id': str(result.inserted_id),
            'failed_uploads': failed_uploads
        }
        return jsonify(response), 201
    except Exception as e:
        current_app.logger.error(f"Create announcement error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@mobile_api_bp.route('/announcements/<announcement_id>/like', methods=['POST'])
@jwt_required()
def toggle_like(announcement_id):
    """Toggle like on an announcement (any role can like)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Verify announcement exists
        announcement = mongo.db.posts.find_one({'_id': ObjectId(announcement_id)})
        if not announcement:
            return jsonify({'success': False, 'message': 'Announcement not found'}), 404
        
        # Initialize likes array if it doesn't exist
        if 'likes' not in announcement:
            announcement['likes'] = []
        
        likes = announcement.get('likes', [])
        user_oid = ObjectId(current_user_id)
        
        # Check if user already liked
        is_liked = any(str(like) == current_user_id or (isinstance(like, ObjectId) and like == user_oid) for like in likes)
        
        if is_liked:
            # Unlike - remove user from likes
            likes = [like for like in likes if str(like) != current_user_id and (not isinstance(like, ObjectId) or like != user_oid)]
        else:
            # Like - add user to likes
            if user_oid not in likes:
                likes.append(user_oid)
        
        # Update announcement
        mongo.db.posts.update_one(
            {'_id': ObjectId(announcement_id)},
            {'$set': {'likes': likes, 'updated_at': datetime.utcnow()}}
        )
        
        return jsonify({
            'success': True,
            'liked': not is_liked,
            'like_count': len(likes)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Toggle like error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@mobile_api_bp.route('/announcements/<announcement_id>/comments', methods=['POST'])
@jwt_required()
def add_comment(announcement_id):
    """Add a comment to an announcement (any role can comment)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.json
        
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'message': 'Comment content is required'}), 400
        
        # Verify announcement exists
        announcement = mongo.db.posts.find_one({'_id': ObjectId(announcement_id)})
        if not announcement:
            return jsonify({'success': False, 'message': 'Announcement not found'}), 404
        
        # Get user info
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Create comment
        comment = {
            '_id': ObjectId(),
            'user_id': ObjectId(current_user_id),
            'user_name': user.get('name', 'Unknown'),
            'content': content,
            'created_at': datetime.utcnow()
        }
        
        # Add comment to announcement
        mongo.db.posts.update_one(
            {'_id': ObjectId(announcement_id)},
            {
                '$push': {'comments': comment},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        # Format comment for response
        formatted_comment = {
            'id': str(comment['_id']),
            'user_id': str(comment['user_id']),
            'user_name': comment['user_name'],
            'content': comment['content'],
            'created_at': comment['created_at'].isoformat()
        }
        
        return jsonify({
            'success': True,
            'comment': formatted_comment,
            'message': 'Comment added successfully'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Add comment error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@mobile_api_bp.route('/announcements/<announcement_id>/comments', methods=['GET'])
@jwt_required()
def get_comments(announcement_id):
    """Get comments for an announcement"""
    try:
        # Verify announcement exists
        announcement = mongo.db.posts.find_one({'_id': ObjectId(announcement_id)})
        if not announcement:
            return jsonify({'success': False, 'message': 'Announcement not found'}), 404
        
        comments = announcement.get('comments', [])
        
        # Format comments
        formatted_comments = []
        for comment in comments:
            formatted_comments.append({
                'id': str(comment['_id']),
                'user_id': str(comment['user_id']),
                'user_name': comment.get('user_name', 'Unknown'),
                'content': comment['content'],
                'created_at': comment['created_at'].isoformat() if isinstance(comment['created_at'], datetime) else comment['created_at']
            })
        
        # Sort by created_at descending (newest first)
        formatted_comments.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'comments': formatted_comments
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get comments error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@mobile_api_bp.route('/posts', methods=['GET'])
@jwt_required()
def get_posts():
    # """Get posts for the organization"""
    # try:
        current_user_id = get_jwt_identity()
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Build query
        query = {
            'post_type': 'announcement',
            'organization_id': ObjectId(user['organization_id']),
            'status': 'published'
        }

        # Get latest announcement
        announcements = mongo.db.posts.find(query, sort=[('created_at', -1)])
        formatted_announcements = []
        for announcement in announcements:
            author_id = announcement['author_id']
            if isinstance(author_id, str):
                author_id = ObjectId(author_id)
            print({'_id': author_id})
            created_by = mongo.db.users.find_one({'_id': author_id})
            if not created_by:
                created_by = {'name': "Unknown"}
            
            associated_class = {}

            if announcement.get('associated_class') != None:
                for key, value in announcement.get('associated_class').items():
                    if '_id' in key:
                        if isinstance(value, ObjectId):
                            associated_class[key] = str(value)
                            print("Converted _id to string", key)
                        else:
                            associated_class[key] = value

                    else:
                        associated_class[key] = value

                    if isinstance(associated_class[key], datetime):
                        print("Converted datetime to string", associated_class[key])
                        associated_class[key] = associated_class[key].isoformat()
                    

                    print(key, type(associated_class[key]))
                    if isinstance(associated_class[key], dict):
                        for key2, value2 in associated_class[key].items():
                            if '_id' in key2:
                                if isinstance(value2, ObjectId):
                                    associated_class[key][key2] = str(value2)

            # Convert instruction keys to strings if instructions is a dict
            convert_instruction_keys_to_str(associated_class)

            print("associated_class", associated_class)
                    
            # Get likes and comments info
            likes = announcement.get('likes', [])
            comments = announcement.get('comments', [])
            user_oid = ObjectId(current_user_id)
            
            # Check if current user has liked this announcement
            is_liked = any(str(like) == current_user_id or (isinstance(like, ObjectId) and like == user_oid) for like in likes)
            
            formatted_announcements.append({
                'id': str(announcement['_id']),
                'title': announcement['title'],
                'content': announcement['content'],
                'created_at': announcement['created_at'].isoformat(),
                'created_by': str(created_by['name']),
                'organization_id': str(announcement['organization_id']),
                'associated_class': associated_class if len(associated_class.keys()) > 0 else None,
                'media_urls': announcement.get('media_urls', []),
                'like_count': len(likes),
                'comment_count': len(comments),
                'is_liked': is_liked
            })


            print("formatted_announcements", associated_class)
        if not announcements:
            return jsonify({'success': True, 'announcements': []})

        return jsonify({'success': True, 'announcements': formatted_announcements})


    # except Exception as e:
    #     print(f"Error in get_announcement: {str(e)}")
    #     return jsonify({'success': False, 'message': 'Failed to fetch latest announcement'}), 500


@mobile_api_bp.route('/users/create_or_get', methods=['POST'])
@jwt_required()
def create_or_get_user():
    """Create or get user"""
    try:
        import random, string
        data = request.json

        current_user_id = get_jwt_identity()
        org_id = get_jwt().get('organization_id')

        print("data", data,org_id,current_user_id)

        user = mongo.db.users.find_one({'phone_number': data['phone']})
        print("user", user)
        if not user or user is None:
            generated_email = data['name'].strip() + '.' + data['phone'].strip() + '@botle.club'
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            role = 'student'
            print("generated_email", generated_email, random_password, role)
            result, status_code = AuthService.register_user(
                phone_number=data['phone'],
                name=data['name'],
                password=random_password,
                role=role,
                organization_id=ObjectId(org_id),
                created_by=ObjectId(current_user_id),
                email=generated_email,
                billing_start_date=None
            )
            print("result", result, status_code)
            if status_code == 201:
                # Add role-specific profile data
                user_id = result['user_id']
                user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            
                for key, value in user.items():
                    if '_id' in key:
                        user[key] = str(value)
                
                
            return jsonify({'id': str(user['_id'])}), 200
        else:
            return jsonify({'id': str(user['_id'])}), 200
    except Exception as e:
        current_app.logger.error(f"Create or get user error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# Feedback Endpoints
@mobile_api_bp.route('/classes/<class_id>/activity', methods=['GET'])
@jwt_required()
def get_class_activity(class_id):
    """Get activity information for a class via its schedule_item_id"""
    try:
        current_user_id = get_jwt_identity()
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Get the class
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
        
        # Get schedule_item_id from class
        schedule_item_id = class_doc.get('schedule_item_id')
        if not schedule_item_id:
            return jsonify({'success': False, 'message': 'Class has no associated schedule item'}), 404
        
        # Get schedule item
        schedule_item = mongo.db.schedules.find_one({'_id': ObjectId(schedule_item_id)})
        if not schedule_item:
            return jsonify({'success': False, 'message': 'Schedule item not found'}), 404
        
        # Get activity from schedule item
        activity_id = schedule_item.get('activity_id')
        if not activity_id:
            return jsonify({'success': False, 'message': 'Schedule item has no associated activity'}), 404
        
        activity = mongo.db.activities.find_one({'_id': ObjectId(activity_id)})
        if not activity:
            return jsonify({'success': False, 'message': 'Activity not found'}), 404
        
        # Format activity data
        activity_data = {
            'id': str(activity['_id']),
            'action': activity.get('action', ''),
            'organization_id': str(activity.get('organization_id', '')),
            'feedback_metrics': activity.get('feedback_metrics', []),
            'price': activity.get('price'),
        }
        
        return jsonify({'success': True, 'activity': activity_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get class activity error: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@mobile_api_bp.route('/classes/<class_id>/feedback', methods=['POST'])
@jwt_required()
def submit_class_feedback(class_id):
    """Submit feedback for a student in a class (coaches only)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.json
        
        # Get the current user (must be coach)
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Only coaches can submit feedback
        if user.get('role') not in ['coach', 'org_admin', 'center_admin']:
            return jsonify({'success': False, 'message': 'Only coaches can submit feedback'}), 403
        
        # Get student_id from request
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({'success': False, 'message': 'student_id is required'}), 400
        
        # Get the class
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
        
        # Verify student attended the class
        attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(student_id),
            'status': 'present'
        })
        
        if not attendance:
            return jsonify({'success': False, 'message': 'Student did not attend this class'}), 403
        
        # Get activity via schedule_item_id
        schedule_item_id = class_doc.get('schedule_item_id')
        activity_id = None
        
        if schedule_item_id:
            schedule_item = mongo.db.schedules.find_one({'_id': ObjectId(schedule_item_id)})
            if schedule_item:
                activity_id = schedule_item.get('activity_id')
        
        if not activity_id:
            return jsonify({'success': False, 'message': 'Cannot find activity for this class'}), 404
        
        # Validate metrics
        metrics = data.get('metrics', {})
        if not metrics:
            return jsonify({'success': False, 'message': 'Metrics are required'}), 400
        
        # Check if feedback already exists
        existing_feedback = mongo.db.feedback.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(student_id)
        })
        
        if existing_feedback:
            # Update existing feedback
            update_data = {
                'metrics': metrics,
                'notes': data.get('notes', ''),
                'updated_at': datetime.utcnow(),
                'coach_id': ObjectId(current_user_id)  # Update coach who modified
            }
            
            mongo.db.feedback.update_one(
                {'_id': existing_feedback['_id']},
                {'$set': update_data}
            )
            
            return jsonify({
                'success': True,
                'message': 'Feedback updated successfully',
                'feedback_id': str(existing_feedback['_id'])
            }), 200
        else:
            # Create new feedback
            feedback = {
                'class_id': ObjectId(class_id),
                'student_id': ObjectId(student_id),
                'coach_id': ObjectId(current_user_id),
                'activity_id': ObjectId(activity_id),
                'organization_id': ObjectId(class_doc.get('organization_id')),
                'metrics': metrics,
                'notes': data.get('notes', ''),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = mongo.db.feedback.insert_one(feedback)
            
            return jsonify({
                'success': True,
                'message': 'Feedback submitted successfully',
                'feedback_id': str(result.inserted_id)
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"Submit feedback error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@mobile_api_bp.route('/classes/<class_id>/feedback/<student_id>', methods=['GET'])
@jwt_required()
def get_class_feedback(class_id, student_id):
    """Get feedback for a student in a class"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get the current user
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Get the class
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
        
        # Get feedback for this student and class
        feedback = mongo.db.feedback.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(student_id)
        })
        
        if not feedback:
            return jsonify({'success': True, 'feedback': None}), 200
        
        # Format feedback data
        feedback_data = {
            'id': str(feedback['_id']),
            'class_id': str(feedback['class_id']),
            'student_id': str(feedback['student_id']),
            'coach_id': str(feedback['coach_id']) if feedback.get('coach_id') else None,
            'activity_id': str(feedback['activity_id']),
            'organization_id': str(feedback['organization_id']),
            'metrics': feedback.get('metrics', {}),
            'notes': feedback.get('notes', ''),
            'created_at': feedback['created_at'].isoformat() if feedback.get('created_at') else None,
            'updated_at': feedback['updated_at'].isoformat() if feedback.get('updated_at') else None,
        }
        
        return jsonify({'success': True, 'feedback': feedback_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get feedback error: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@mobile_api_bp.route('/classes/<class_id>/student-feedback', methods=['POST'])
@jwt_required()
def submit_student_feedback(class_id):
    """Submit student feedback for a class (students only)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.json
        
        # Get the current user (must be student)
        user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Only students can submit student feedback
        if user.get('role') not in ['student']:
            return jsonify({'success': False, 'message': 'Only students can submit feedback'}), 403
        
        # Get rating from request
        rating = data.get('rating')
        if not rating:
            return jsonify({'success': False, 'message': 'rating is required'}), 400
        
        # Validate rating is between 1-5
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'rating must be between 1 and 5'}), 400
        
        # Get the class
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'success': False, 'message': 'Class not found'}), 404
        
        # Verify student attended the class
        attendance = mongo.db.attendance.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id),
            'status': {'$in': ['present', 'late']}
        })
        
        if not attendance:
            return jsonify({'success': False, 'message': 'You must attend the class before submitting feedback'}), 403
        
        # Check if feedback already exists
        existing_feedback = mongo.db.student_feedback.find_one({
            'class_id': ObjectId(class_id),
            'student_id': ObjectId(current_user_id)
        })
        
        if existing_feedback:
            # Update existing feedback
            update_data = {
                'rating': rating,
                'notes': data.get('notes', ''),
                'updated_at': datetime.utcnow()
            }
            
            mongo.db.student_feedback.update_one(
                {'_id': existing_feedback['_id']},
                {'$set': update_data}
            )
            
            return jsonify({
                'success': True,
                'message': 'Feedback updated successfully',
                'feedback_id': str(existing_feedback['_id'])
            }), 200
        else:
            # Create new feedback
            feedback = {
                'class_id': ObjectId(class_id),
                'student_id': ObjectId(current_user_id),
                'organization_id': ObjectId(class_doc.get('organization_id')) if class_doc.get('organization_id') else None,
                'rating': rating,
                'notes': data.get('notes', ''),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            result = mongo.db.student_feedback.insert_one(feedback)
            
            return jsonify({
                'success': True,
                'message': 'Feedback submitted successfully',
                'feedback_id': str(result.inserted_id)
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"Submit student feedback error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


# Botle Coins Endpoints
@mobile_api_bp.route('/coins/transactions', methods=['GET'])
@jwt_required()
def get_coin_transactions():
    """Get coin transaction history for the current user"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Calculate skip
        skip = (page - 1) * limit
        
        # Get transactions
        transactions = CoinService.get_user_transactions(
            user_id=current_user_id,
            limit=limit,
            skip=skip
        )
        
        # Get current balance
        current_balance = CoinService.get_user_balance(current_user_id)
        
        # Get total count for pagination
        total_count = mongo.db.coin_transactions.count_documents({
            'user_id': ObjectId(current_user_id)
        })
        
        return jsonify({
            'success': True,
            'transactions': transactions,
            'currentBalance': current_balance,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'hasMore': (skip + len(transactions)) < total_count
            }
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get coin transactions error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@mobile_api_bp.route('/coins/balance', methods=['GET'])
@jwt_required()
def get_coin_balance():
    """Get current coin balance for the user"""
    try:
        current_user_id = get_jwt_identity()
        balance = CoinService.get_user_balance(current_user_id)
        
        return jsonify({
            'success': True,
            'balance': balance
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Get coin balance error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# Profile Picture Upload
@mobile_api_bp.route('/auth/profile-picture', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    """Upload or update user profile picture"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Upload file using FileUploadService
        file_service = FileUploadService()
        result = file_service.upload_profile_picture(file, current_user_id)
        
        if result['success']:
            # Update user's profile_picture_url in database
            mongo.db.users.update_one(
                {'_id': ObjectId(current_user_id)},
                {
                    '$set': {
                        'profile_picture_url': result['url'],
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Get updated user
            updated_user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
            updated_user['_id'] = str(updated_user['_id'])
            if 'password' in updated_user:
                del updated_user['password']
            if updated_user.get('organization_id'):
                updated_user['organization_id'] = str(updated_user['organization_id'])
            if updated_user.get('organization_ids'):
                updated_user['organization_ids'] = [str(oid) for oid in updated_user['organization_ids']]
            if updated_user.get('subscription_ids'):
                updated_user['subscription_ids'] = [str(sid) for sid in updated_user['subscription_ids']]
            
            # Ensure botle_coins field exists
            if 'botle_coins' not in updated_user:
                updated_user['botle_coins'] = 0
            
            return jsonify({
                'success': True,
                'message': 'Profile picture uploaded successfully',
                'url': result['url'],
                'user': updated_user
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Upload failed')
            }), 400
    
    except Exception as e:
        current_app.logger.error(f"Upload profile picture error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500