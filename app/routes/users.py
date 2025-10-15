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
                # Check if organization_id is in user's organization_ids array
                query = {'organization_ids': ObjectId(org_filter)}
            else:
                query = {}
        else:
            # Other roles can only see users in their organization
            if not organization_id:
                return jsonify({'error': 'User must be associated with an organization'}), 400
            # Check if organization_id is in user's organization_ids array
            query = {'organization_ids': ObjectId(organization_id)}
        
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
                'organization_ids': ObjectId(target_org_id)
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
        
        # Filter for users (multi-org support)
        user_org_filter = {'organization_ids': ObjectId(target_org_id)}
        # Filter for other entities (single org)
        entity_org_filter = {'organization_id': ObjectId(target_org_id)}
        
        # Get user counts by role
        user_stats = {}
        for role in ['org_admin', 'center_admin', 'coach', 'student']:
            count = mongo.db.users.count_documents({
                **user_org_filter,
                'role': role,
                'is_active': True
            })
            user_stats[role] = count
        
        # Get group stats
        group_count = mongo.db.groups.count_documents({
            **entity_org_filter,
            'is_active': True
        })
        
        # Get class stats (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        class_stats = {
            'total_classes': mongo.db.classes.count_documents(entity_org_filter),
            'recent_classes': mongo.db.classes.count_documents({
                **entity_org_filter,
                'scheduled_at': {'$gte': thirty_days_ago}
            }),
            'upcoming_classes': mongo.db.classes.count_documents({
                **entity_org_filter,
                'scheduled_at': {'$gte': datetime.utcnow()},
                'status': 'scheduled'
            })
        }
        
        # Get payment stats
        payment_stats = {
            'pending_payments': mongo.db.payments.count_documents({
                **entity_org_filter,
                'status': 'pending'
            }),
            'overdue_payments': mongo.db.payments.count_documents({
                **entity_org_filter,
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

# Child profile management endpoints
@users_bp.route('/<user_id>/children', methods=['GET'])
@jwt_or_session_required()
def get_children(user_id):
    """Get all children of a parent user"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can access this data
        if str(current_user_id) != str(user_id) and user_info['role'] not in ['super_admin', 'org_admin', 'center_admin', 'coach']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get children
        children_cursor = mongo.db.users.find({
            'parent_id': ObjectId(user_id),
            'is_active': True
        }).sort('created_at', -1)
        
        children = []
        for child_data in children_cursor:
            for key, value in child_data.items()    :
                if '_id' in key:
                    child_data[key] = str(value)
                    
            children.append(child_data)
        print(children)
        
        return jsonify({
            'children': children,
            'total': len(children)
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@users_bp.route('/<user_id>/children', methods=['POST'])
@jwt_or_session_required()
def add_child(user_id):
    """Add a child profile to a parent user"""
    from pymongo.errors import DuplicateKeyError
    
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can add child
        # if str(current_user_id) != str(user_id):
        #     return jsonify({'error': 'Access denied'}), 403
        
        # Get parent user
        parent_user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not parent_user:
            return jsonify({'error': 'Parent user not found'}), 404
        
        # Get request data
        data = request.get_json() if request.is_json else request.form
        name = data.get('name') + ' (' +parent_user.get('name')+"'s child)"
        age = data.get('age')
        gender = data.get('gender')
        
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        
        # Count existing children to generate starting serial number
        existing_children_count = mongo.db.users.count_documents({
            'parent_id': ObjectId(user_id),
            'is_active': True
        })
        child_serial = existing_children_count + 1
        
        # Get parent email and phone for generating child credentials
        parent_phone = parent_user.get('phone_number', '')
        parent_email = parent_user.get('email', '')
        
        # Try to create child with auto-incrementing serial number on duplicate
        max_attempts = 100  # Prevent infinite loop
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Generate unique phone number by appending serial to parent's phone
                if parent_phone:
                    child_phone = f"{parent_phone}{child_serial}"
                else:
                    child_phone = f"child{user_id}{child_serial}"
                
                # Generate unique email by appending serial to parent's email
                if parent_email and '@' in parent_email:
                    email_parts = parent_email.split('@')
                    child_email = f"{email_parts[0]}_child{child_serial}@{email_parts[1]}"
                else:
                    child_email = f"child{child_serial}_{user_id}@parent.child"
                
                # Create child user - inherit parent's organizations
                parent_org_ids = parent_user.get('organization_ids', [])
                if not parent_org_ids and parent_user.get('organization_id'):
                    parent_org_ids = [parent_user['organization_id']]
                
                child = User(
                    phone_number=child_phone,
                    name=name,
                    role='student',
                    organization_ids=parent_org_ids,  # Inherit all parent's organizations
                    parent_id=user_id,
                    age=int(age) if age else None,
                    gender=gender
                )
                
                # Set the unique email
                child.email = child_email
                
                # Save to database
                child_dict = child.to_dict()
                child_dict['parent_id'] = ObjectId(user_id)
                result = mongo.db.users.insert_one(child_dict)
                child._id = result.inserted_id
                
                print(child_dict)

                for key, value in child_dict.items():
                    if '_id' in key:
                        child_dict[key] = str(value)
                    

                return jsonify({
                    'message': 'Child profile added successfully',
                    'child': child_dict
                }), 201
                
            except DuplicateKeyError as e:
                # If duplicate email or phone, increment serial and try again
                child_serial += 1
                attempt += 1
                continue
        
        # If we exhausted all attempts
        return jsonify({'error': 'Unable to generate unique credentials after multiple attempts'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@users_bp.route('/<user_id>/children/<child_id>', methods=['PUT'])
@jwt_or_session_required()
def update_child(user_id, child_id):
    """Update a child profile"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can update child
        # if str(current_user_id) != str(user_id):
        #     return jsonify({'error': 'Access denied'}), 403
        
        # Verify child belongs to parent
        child = mongo.db.users.find_one({
            '_id': ObjectId(child_id),
            'parent_id': ObjectId(user_id)
        })
        
        if not child:
            return jsonify({'error': 'Child not found'}), 404
        
        # Get update data
        data = request.get_json() if request.is_json else request.form
        update_fields = {}
        
        if 'name' in data:
            update_fields['name'] = data['name']
        if 'age' in data:
            update_fields['age'] = int(data['age'])
        if 'gender' in data:
            update_fields['gender'] = data['gender']
        
        update_fields['updated_at'] = datetime.utcnow()
        
        # Update child
        mongo.db.users.update_one(
            {'_id': ObjectId(child_id)},
            {'$set': update_fields}
        )
        
        # Get updated child
        updated_child = mongo.db.users.find_one({'_id': ObjectId(child_id)})
        child_obj = User.from_dict(updated_child)
        
        return jsonify({
            'message': 'Child profile updated successfully',
            'child': child_obj.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@users_bp.route('/<user_id>/children/<child_id>', methods=['DELETE'])
@jwt_or_session_required()
def delete_child(user_id, child_id):
    """Delete/deactivate a child profile"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can delete child
        # if str(current_user_id) != str(user_id):
        #     return jsonify({'error': 'Access denied'}), 403
        
        # Verify child belongs to parent
        child = mongo.db.users.find_one({
            '_id': ObjectId(child_id),
            'parent_id': ObjectId(user_id)
        })
        
        if not child:
            return jsonify({'error': 'Child not found'}), 404
        
        # Deactivate child (soft delete)
        mongo.db.users.update_one(
            {'_id': ObjectId(child_id)},
            {
                '$set': {
                    'is_active': False,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return jsonify({'message': 'Child profile deleted successfully'}), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# User dashboard data endpoints
@users_bp.route('/<user_id>/upcoming-classes', methods=['GET'])
@jwt_or_session_required()
def get_user_upcoming_classes(user_id):
    """Get upcoming classes for a user"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can access this data
        if str(current_user_id) != str(user_id) and user_info['role'] not in ['super_admin', 'org_admin', 'center_admin', 'coach']:
            return jsonify({'error': 'Access denied'}), 403
        
        now = datetime.utcnow()
        
        # Get classes where user is enrolled
        classes_cursor = mongo.db.classes.find({
            'student_ids': ObjectId(user_id),
            'scheduled_at': {'$gte': now},
            'status': {'$in': ['scheduled', 'confirmed']}
        }).sort('scheduled_at', 1).limit(50)
        
        classes = []
        for class_doc in classes_cursor:
            class_dict = {
                '_id': str(class_doc['_id']),
                'title': class_doc.get('title', ''),
                'sport': class_doc.get('sport', ''),
                'level': class_doc.get('level', ''),
                'scheduled_at': class_doc['scheduled_at'].isoformat() if class_doc.get('scheduled_at') else None,
                'duration_minutes': class_doc.get('duration_minutes', 60),
                'location': class_doc.get('location', {}),
                'status': class_doc.get('status', 'scheduled')
            }
            
            # Get coach info
            if class_doc.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': class_doc['coach_id']})
                if coach:
                    class_dict['coach_name'] = coach.get('name', '')
                    class_dict['coach_phone'] = coach.get('phone_number', '')
            
            classes.append(class_dict)
        
        return jsonify({
            'classes': classes,
            'total': len(classes)
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@users_bp.route('/<user_id>/attended-classes', methods=['GET'])
@jwt_or_session_required()
def get_user_attended_classes(user_id):
    """Get attended classes for a user with attendance status"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can access this data
        if str(current_user_id) != str(user_id) and user_info['role'] not in ['super_admin', 'org_admin', 'center_admin', 'coach']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get attendance records for this user
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        attendance_cursor = mongo.db.attendance.find({
            'student_id': ObjectId(user_id),
            'status': {'$in': ['present', 'late', 'absent', 'excused']}
        }).sort('created_at', -1).skip(skip).limit(per_page)
        
        attended_classes = []
        for attendance_doc in attendance_cursor:
            class_doc = mongo.db.classes.find_one({'_id': attendance_doc['class_id']})
            if not class_doc:
                continue
            
            class_dict = {
                '_id': str(class_doc['_id']),
                'title': class_doc.get('title', ''),
                'sport': class_doc.get('sport', ''),
                'level': class_doc.get('level', ''),
                'scheduled_at': class_doc['scheduled_at'].isoformat() if class_doc.get('scheduled_at') else None,
                'duration_minutes': class_doc.get('duration_minutes', 60),
                'location': class_doc.get('location', {}),
                'attendance_status': attendance_doc.get('status', 'unknown'),
                'attendance_date': attendance_doc.get('created_at').isoformat() if attendance_doc.get('created_at') else None,
                'notes': attendance_doc.get('notes', '')
            }
            
            # Get coach info
            if class_doc.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': class_doc['coach_id']})
                if coach:
                    class_dict['coach_name'] = coach.get('name', '')
            
            attended_classes.append(class_dict)
        
        total = mongo.db.attendance.count_documents({
            'student_id': ObjectId(user_id),
            'status': {'$in': ['present', 'late', 'absent', 'excused']}
        })
        
        return jsonify({
            'classes': attended_classes,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@users_bp.route('/<user_id>/payments', methods=['GET'])
@jwt_or_session_required()
def get_user_payments(user_id):
    """Get payment history for a user"""
    try:
        user_info = get_current_user_info()
        current_user_id = user_info['user_id']
        
        # Check if user can access this data
        if str(current_user_id) != str(user_id) and user_info['role'] not in ['super_admin', 'org_admin', 'center_admin', 'coach']:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get payment records for this user
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)
        skip = (page - 1) * per_page
        
        payments_cursor = mongo.db.payments.find({
            'student_id': ObjectId(user_id)
        }).sort('due_date', -1).skip(skip).limit(per_page)
        
        payments = []
        for payment_doc in payments_cursor:
            payment_dict = {
                '_id': str(payment_doc['_id']),
                'amount': payment_doc.get('amount', 0),
                'status': payment_doc.get('status', 'pending'),
                'due_date': payment_doc['due_date'].isoformat() if payment_doc.get('due_date') else None,
                'paid_date': payment_doc['paid_date'].isoformat() if payment_doc.get('paid_date') else None,
                'description': payment_doc.get('description', ''),
                'payment_method': payment_doc.get('payment_method', ''),
                'transaction_id': payment_doc.get('transaction_id', ''),
                'created_at': payment_doc['created_at'].isoformat() if payment_doc.get('created_at') else None
            }
            
            payments.append(payment_dict)
        
        total = mongo.db.payments.count_documents({
            'student_id': ObjectId(user_id)
        })
        
        return jsonify({
            'payments': payments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500 