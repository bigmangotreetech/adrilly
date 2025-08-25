from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from app.extensions import mongo
from app.models.user import User
from app.models.organization import Organization, Group
from app.routes.auth import require_role, require_permission
from app.services.auth_service import AuthService
from marshmallow import Schema, fields, ValidationError
from datetime import datetime
from bson import ObjectId
from functools import wraps
from flask import session
from app.utils.auth import jwt_or_session_required, get_current_user_info, require_role_hybrid

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

# Request schemas
class CreateGroupSchema(Schema):
    name = fields.Str(required=True)
    coach_id = fields.Str(required=False)
    sport = fields.Str(required=False)
    level = fields.Str(required=False)
    description = fields.Str(required=False)
    max_students = fields.Int(required=False)

class UpdateUserRoleSchema(Schema):
    role = fields.Str(required=True, validate=lambda x: x in ['org_admin', 'center_admin', 'coach', 'student'])

class AssignUserToGroupSchema(Schema):
    user_id = fields.Str(required=True)
    group_id = fields.Str(required=True)

@users_bp.route('', methods=['GET'])
@jwt_or_session_required()
@require_role_hybrid(['super_admin', 'org_admin', 'center_admin', 'coach'])
def get_users():
    """Get users in the organization with role-based filtering"""
    try:
        user_info = get_current_user_info()
        user_role = user_info['role']
        user_id = user_info['user_id']
        organization_id = user_info['organization_id']
        
        # Build query based on user role and organization
        if user_role == 'super_admin':
            # Super admin can see users from any organization
            org_filter = request.args.get('organization_id')
            if org_filter:
                query = {'organization_id': ObjectId(org_filter)}
            else:
                query = {}
        else:
            # Other roles can only see users in their organization
            if not organization_id:
                return jsonify({'error': 'User must be associated with an organization'}), 400
            query = {'organization_id': ObjectId(organization_id)}
        
        # Additional filters
        role_filter = request.args.get('role')
        is_active = request.args.get('is_active')
        
        if role_filter:
            query['role'] = role_filter
        
        if is_active is not None:
            query['is_active'] = is_active.lower() == 'true'
        
        # Role-based visibility restrictions
        current_user = AuthService.get_user_by_id(user_id)
        if user_role == 'coach':
            # Coaches can only see students and themselves
            if role_filter and role_filter != 'student':
                query['_id'] = ObjectId(user_id)  # Only themselves
            else:
                query['$or'] = [
                    {'role': 'student'},
                    {'_id': ObjectId(user_id)}
                ]
        elif user_role == 'center_admin':
            # Center admins can see coaches and students
            if role_filter and role_filter not in ['coach', 'student']:
                query['role'] = {'$in': ['coach', 'student']}
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        # Execute query
        users_cursor = mongo.db.users.find(query).sort('created_at', -1).skip(skip).limit(per_page)
        users = []
        
        for user_data in users_cursor:
            user = User.from_dict(user_data)
            user_dict = user.to_dict()
            
            # Add organization info
            if user.organization_id:
                org_data = mongo.db.organizations.find_one({'_id': user.organization_id})
                if org_data:
                    user_dict['organization_name'] = org_data['name']
            
            # Add group info for students
            if user.role == 'student' and user.groups:
                group_names = []
                for group_id in user.groups:
                    group_data = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
                    if group_data:
                        group_names.append(group_data['name'])
                user_dict['group_names'] = group_names
            
            users.append(user_dict)
        
        # Get total count
        total = mongo.db.users.count_documents(query)
        
        return jsonify({
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/<user_id>/role', methods=['PUT'])
@jwt_required()
@require_role(['super_admin', 'org_admin', 'center_admin'])
def update_user_role(user_id):
    """Update user role (admin function)"""
    try:
        schema = UpdateUserRoleSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        current_user_id = get_jwt_identity()
        current_user_role = claims.get('role')
        
        # Get users
        current_user = AuthService.get_user_by_id(current_user_id)
        target_user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        
        if not target_user_data:
            return jsonify({'error': 'User not found'}), 404
        
        target_user = User.from_dict(target_user_data)
        
        # Check permissions
        if not current_user.can_manage_user(target_user):
            return jsonify({'error': 'Cannot manage this user'}), 403
        
        # Role hierarchy validation
        new_role = data['role']
        current_level = User.ROLES.get(current_user_role, 999)
        new_role_level = User.ROLES.get(new_role, 999)
        
        if current_level >= new_role_level:
            return jsonify({'error': 'Cannot assign role equal or higher than your own'}), 403
        
        result, status_code = AuthService.update_user_role(user_id, new_role, current_user_id)
        
        if result:
            return jsonify({
                'message': 'User role updated successfully',
                'user': result.to_dict()
            }), status_code
        else:
            return jsonify({'error': 'Failed to update user role'}), status_code
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/<user_id>/deactivate', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin', 'center_admin'])
def deactivate_user(user_id):
    """Deactivate a user account"""
    try:
        claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Check if user can manage target user
        current_user = AuthService.get_user_by_id(current_user_id)
        target_user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        
        if not target_user_data:
            return jsonify({'error': 'User not found'}), 404
        
        target_user = User.from_dict(target_user_data)
        
        if not current_user.can_manage_user(target_user):
            return jsonify({'error': 'Cannot manage this user'}), 403
        
        result, status_code = AuthService.deactivate_user(user_id, current_user_id)
        return jsonify(result), status_code
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/groups', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin', 'center_admin'])
def create_group():
    """Create a new group"""
    try:
        schema = CreateGroupSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        current_user_role = claims.get('role')
        
        if not organization_id and current_user_role != 'super_admin':
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # If super_admin, they can specify organization via parameter
        if current_user_role == 'super_admin':
            target_org_id = request.args.get('organization_id', organization_id)
        else:
            target_org_id = organization_id
        
        if not target_org_id:
            return jsonify({'error': 'Organization ID required'}), 400
        
        # Validate coach if specified
        if data.get('coach_id'):
            coach_data = mongo.db.users.find_one({
                '_id': ObjectId(data['coach_id']),
                'role': {'$in': ['coach', 'center_admin']},
                'organization_id': ObjectId(target_org_id)
            })
            if not coach_data:
                return jsonify({'error': 'Invalid coach or coach not in organization'}), 400
        
        # Create new group
        new_group = Group(
            name=data['name'],
            organization_id=target_org_id,
            coach_id=data.get('coach_id'),
            sport=data.get('sport'),
            level=data.get('level'),
            description=data.get('description')
        )
        
        if 'max_students' in data:
            new_group.max_students = data['max_students']
        
        result = mongo.db.groups.insert_one(new_group.to_dict())
        new_group._id = result.inserted_id
        
        return jsonify({
            'message': 'Group created successfully',
            'group': new_group.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/groups', methods=['GET'])
@jwt_required()
def get_groups():
    """Get groups in the organization"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_role = claims.get('role')
        
        # Build query
        if user_role == 'super_admin':
            org_filter = request.args.get('organization_id')
            if org_filter:
                query = {'organization_id': ObjectId(org_filter)}
            else:
                query = {}
        else:
            if not organization_id:
                return jsonify({'error': 'User must be associated with an organization'}), 400
            query = {'organization_id': ObjectId(organization_id)}
        
        # Additional filters
        sport = request.args.get('sport')
        coach_id = request.args.get('coach_id')
        is_active = request.args.get('is_active')
        
        if sport:
            query['sport'] = sport
        if coach_id:
            query['coach_id'] = ObjectId(coach_id)
        if is_active is not None:
            query['is_active'] = is_active.lower() == 'true'
        
        groups_cursor = mongo.db.groups.find(query).sort('name', 1)
        groups = []
        
        for group_data in groups_cursor:
            group = Group.from_dict(group_data)
            group_dict = group.to_dict()
            
            # Add coach info
            if group.coach_id:
                coach_data = mongo.db.users.find_one({'_id': group.coach_id})
                if coach_data:
                    group_dict['coach_name'] = coach_data['name']
            
            # Add student count
            student_count = mongo.db.users.count_documents({
                'groups': str(group._id),
                'role': 'student',
                'is_active': True
            })
            group_dict['student_count'] = student_count
            
            groups.append(group_dict)
        
        return jsonify({
            'groups': groups,
            'total': len(groups)
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/groups/<group_id>/assign-user', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin', 'center_admin', 'coach'])
def assign_user_to_group(group_id):
    """Assign a user to a group"""
    try:
        schema = AssignUserToGroupSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Validate group exists
        group_data = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        if not group_data:
            return jsonify({'error': 'Group not found'}), 404
        
        # Validate user exists and is a student
        user_data = mongo.db.users.find_one({
            '_id': ObjectId(data['user_id']),
            'role': 'student'
        })
        if not user_data:
            return jsonify({'error': 'Student not found'}), 404
        
        user = User.from_dict(user_data)
        group = Group.from_dict(group_data)
        current_user = AuthService.get_user_by_id(current_user_id)
        
        # Check permissions
        if not current_user.can_manage_user(user):
            return jsonify({'error': 'Cannot manage this user'}), 403
        
        # Check if user is in same organization as group
        if str(user.organization_id) != str(group.organization_id):
            return jsonify({'error': 'User and group must be in same organization'}), 400
        
        # Check if user is already in group
        if group_id in user.groups:
            return jsonify({'error': 'User already in group'}), 400
        
        # Check group capacity
        if group.max_students:
            current_count = mongo.db.users.count_documents({
                'groups': group_id,
                'role': 'student',
                'is_active': True
            })
            if current_count >= group.max_students:
                return jsonify({'error': 'Group is at maximum capacity'}), 400
        
        # Add user to group
        mongo.db.users.update_one(
            {'_id': ObjectId(data['user_id'])},
            {
                '$addToSet': {'groups': group_id},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        # Update group student count
        new_count = mongo.db.users.count_documents({
            'groups': group_id,
            'role': 'student',
            'is_active': True
        })
        
        mongo.db.groups.update_one(
            {'_id': ObjectId(group_id)},
            {
                '$set': {
                    'current_students': new_count,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return jsonify({'message': 'User assigned to group successfully'}), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/groups/<group_id>/remove-user/<user_id>', methods=['DELETE'])
@jwt_required()
@require_role(['super_admin', 'org_admin', 'center_admin', 'coach'])
def remove_user_from_group(group_id, user_id):
    """Remove a user from a group"""
    try:
        claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Validate user and group
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        group_data = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        
        if not user_data or not group_data:
            return jsonify({'error': 'User or group not found'}), 404
        
        user = User.from_dict(user_data)
        current_user = AuthService.get_user_by_id(current_user_id)
        
        # Check permissions
        if not current_user.can_manage_user(user):
            return jsonify({'error': 'Cannot manage this user'}), 403
        
        # Remove user from group
        mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$pull': {'groups': group_id},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        
        # Update group student count
        new_count = mongo.db.users.count_documents({
            'groups': group_id,
            'role': 'student',
            'is_active': True
        })
        
        mongo.db.groups.update_one(
            {'_id': ObjectId(group_id)},
            {
                '$set': {
                    'current_students': new_count,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return jsonify({'message': 'User removed from group successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@users_bp.route('/organizations/stats', methods=['GET'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def get_organization_stats():
    """Get organization statistics"""
    try:
        claims = get_jwt()
        user_role = claims.get('role')
        organization_id = claims.get('organization_id')
        
        if user_role == 'super_admin':
            # Super admin can view stats for any organization
            target_org_id = request.args.get('organization_id', organization_id)
        else:
            target_org_id = organization_id
        
        if not target_org_id:
            return jsonify({'error': 'Organization ID required'}), 400
        
        org_filter = {'organization_id': ObjectId(target_org_id)}
        
        # Get user counts by role
        user_stats = {}
        for role in ['org_admin', 'center_admin', 'coach', 'student']:
            count = mongo.db.users.count_documents({
                **org_filter,
                'role': role,
                'is_active': True
            })
            user_stats[role] = count
        
        # Get group stats
        group_count = mongo.db.groups.count_documents({
            **org_filter,
            'is_active': True
        })
        
        # Get class stats (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        class_stats = {
            'total_classes': mongo.db.classes.count_documents(org_filter),
            'recent_classes': mongo.db.classes.count_documents({
                **org_filter,
                'scheduled_at': {'$gte': thirty_days_ago}
            }),
            'upcoming_classes': mongo.db.classes.count_documents({
                **org_filter,
                'scheduled_at': {'$gte': datetime.utcnow()},
                'status': 'scheduled'
            })
        }
        
        # Get payment stats
        payment_stats = {
            'pending_payments': mongo.db.payments.count_documents({
                **org_filter,
                'status': 'pending'
            }),
            'overdue_payments': mongo.db.payments.count_documents({
                **org_filter,
                'status': 'overdue'
            })
        }
        
        return jsonify({
            'organization_id': target_org_id,
            'user_stats': user_stats,
            'group_count': group_count,
            'class_stats': class_stats,
            'payment_stats': payment_stats
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 