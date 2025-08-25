from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from app.services.organization_signup_service import OrganizationSignupService
from app.models.user import User
from app.models.organization import Organization
from app.extensions import mongo
from bson import ObjectId
from datetime import datetime
import re

org_signup_bp = Blueprint('org_signup', __name__)

# Request schemas
class OrganizationSignupSchema(Schema):
    phone_number = fields.Str(required=True)
    name = fields.Str(required=True)
    center_code = fields.Str(required=True)
    email = fields.Email(required=False, allow_none=True)
    password = fields.Str(required=False, allow_none=True)

class SignupLinkValidationSchema(Schema):
    slug = fields.Str(required=True)
    token = fields.Str(required=True)

# Web routes for signup pages
@org_signup_bp.route('/signup/<slug>')
def signup_page(slug):
    """Display organization signup page"""
    try:
        token = request.args.get('token')
        if not token:
            flash('Invalid signup link - missing token', 'error')
            return redirect(url_for('web.login'))
        
        # Validate the link
        is_valid, message, org_data = OrganizationSignupService.validate_signup_link(slug, token)
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('web.login'))
        
        # Get organization public details
        org_details = OrganizationSignupService.get_organization_by_slug(slug)
        if not org_details:
            flash('Organization not found', 'error')
            return redirect(url_for('web.login'))
        
        return render_template('organization_signup.html', 
                             organization=org_details,
                             slug=slug,
                             token=token)
        
    except Exception as e:
        current_app.logger.error(f"Error in signup page: {str(e)}")
        flash('An error occurred loading the signup page', 'error')
        return redirect(url_for('web.login'))

@org_signup_bp.route('/signup/<slug>/submit', methods=['POST'])
def submit_signup(slug):
    """Handle signup form submission"""
    try:
        token = request.form.get('token')
        phone_number = request.form.get('phone_number', '').strip()
        name = request.form.get('name', '').strip()
        center_code = request.form.get('center_code', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '').strip() or None
        
        # Basic validation
        if not all([token, phone_number, name, center_code]):
            flash('All required fields must be filled', 'error')
            return redirect(url_for('org_signup.signup_page', slug=slug, token=token))
        
        # Process signup
        success, message, user_data = OrganizationSignupService.signup_with_center_code(
            slug=slug,
            token=token,
            phone_number=phone_number,
            name=name,
            center_code=center_code,
            email=email,
            password=password
        )
        
        if success:
            # Auto-login the user
            session['user_id'] = str(user_data['_id'])
            session['phone_number'] = user_data['phone_number']
            session['name'] = user_data['name']
            session['role'] = user_data['role']
            session['organization_id'] = user_data['organization_id']
            session['is_authenticated'] = True
            
            flash('Welcome! Your account has been created successfully.', 'success')
            return redirect(url_for('web.dashboard'))
        else:
            flash(message, 'error')
            return redirect(url_for('org_signup.signup_page', slug=slug, token=token))
        
    except Exception as e:
        current_app.logger.error(f"Error in signup submission: {str(e)}")
        flash('An error occurred during signup. Please try again.', 'error')
        return redirect(url_for('org_signup.signup_page', slug=slug, token=request.form.get('token')))

# API routes for mobile/programmatic access
@org_signup_bp.route('/api/signup/validate', methods=['POST'])
def api_validate_signup_link():
    """API endpoint to validate a signup link"""
    try:
        schema = SignupLinkValidationSchema()
        data = schema.load(request.json)
        
        is_valid, message, org_data = OrganizationSignupService.validate_signup_link(
            data['slug'], data['token']
        )
        
        if is_valid:
            org_details = OrganizationSignupService.get_organization_by_slug(data['slug'])
            return jsonify({
                'valid': True,
                'message': message,
                'organization': org_details
            }), 200
        else:
            return jsonify({
                'valid': False,
                'message': message
            }), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error validating signup link: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_signup_bp.route('/api/signup/<slug>', methods=['POST'])
def api_organization_signup(slug):
    """API endpoint for organization signup"""
    try:
        schema = OrganizationSignupSchema()
        data = schema.load(request.json)
        
        token = request.headers.get('X-Signup-Token') or request.json.get('token')
        if not token:
            return jsonify({'error': 'Signup token required'}), 400
        
        success, message, user_data = OrganizationSignupService.signup_with_center_code(
            slug=slug,
            token=token,
            phone_number=data['phone_number'],
            name=data['name'],
            center_code=data['center_code'],
            email=data.get('email'),
            password=data.get('password')
        )
        
        if success:
            # Create JWT token for API users
            access_token = create_access_token(
                identity=str(user_data['_id']),
                additional_claims={
                    'role': user_data['role'],
                    'organization_id': user_data['organization_id'],
                    'phone_number': user_data['phone_number']
                }
            )
            
            return jsonify({
                'message': message,
                'user': {
                    'id': str(user_data['_id']),
                    'phone_number': user_data['phone_number'],
                    'name': user_data['name'],
                    'email': user_data.get('email'),
                    'role': user_data['role'],
                    'organization_id': user_data['organization_id']
                },
                'access_token': access_token
            }), 201
        else:
            return jsonify({'error': message}), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error in API signup: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_signup_bp.route('/api/organization/<organization_id>/signup-credentials', methods=['POST'])
@jwt_required()
def api_regenerate_signup_credentials(organization_id):
    """API endpoint to regenerate signup credentials (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        success, message, credentials = OrganizationSignupService.generate_new_signup_credentials(
            organization_id, current_user_id
        )
        
        if success:
            return jsonify({
                'message': message,
                'credentials': credentials
            }), 200
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error regenerating credentials: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_signup_bp.route('/api/organization/<organization_id>/signup-info', methods=['GET'])
@jwt_required()
def api_get_signup_info(organization_id):
    """Get organization signup information (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Verify admin permissions
        admin_user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not admin_user or admin_user.get('role') not in ['super_admin', 'org_admin']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        # Check organization access
        if admin_user.get('role') != 'super_admin':
            if str(admin_user.get('organization_id')) != organization_id:
                return jsonify({'error': 'Cannot access this organization'}), 403
        
        # Get organization
        org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
        if not org_data:
            return jsonify({'error': 'Organization not found'}), 404
        
        org = Organization.from_dict(org_data)
        
        return jsonify({
            'signup_enabled': org.signup_enabled,
            'signup_url': org.get_signup_url(),
            'center_code': org.center_code,
            'max_signups_per_day': org.max_signups_per_day,
            'signup_requires_approval': org.signup_requires_approval
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting signup info: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@org_signup_bp.route('/api/organization/<organization_id>/signup-settings', methods=['PUT'])
@jwt_required()
def api_update_signup_settings(organization_id):
    """Update organization signup settings (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Verify admin permissions
        admin_user = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not admin_user or admin_user.get('role') not in ['super_admin', 'org_admin']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        # Check organization access
        if admin_user.get('role') != 'super_admin':
            if str(admin_user.get('organization_id')) != organization_id:
                return jsonify({'error': 'Cannot access this organization'}), 403
        
        # Get update data
        update_data = {}
        if 'signup_enabled' in request.json:
            update_data['signup_enabled'] = bool(request.json['signup_enabled'])
        if 'max_signups_per_day' in request.json:
            max_signups = int(request.json['max_signups_per_day'])
            if max_signups < 1 or max_signups > 1000:
                return jsonify({'error': 'Invalid max_signups_per_day value (1-1000)'}), 400
            update_data['max_signups_per_day'] = max_signups
        if 'signup_requires_approval' in request.json:
            update_data['signup_requires_approval'] = bool(request.json['signup_requires_approval'])
        
        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        update_data['updated_at'] = datetime.utcnow()
        
        # Update organization
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(organization_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'message': 'Signup settings updated successfully'}), 200
        else:
            return jsonify({'error': 'Organization not found or no changes made'}), 404
        
    except ValueError as e:
        return jsonify({'error': f'Invalid data type: {str(e)}'}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating signup settings: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
