from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from app.extensions import mongo
from app.services.file_upload_service import FileUploadService
from app.models.user import User
from app.models.center import Center
from app.models.organization import Organization
import logging

uploads_bp = Blueprint('uploads', __name__, url_prefix='/api/uploads')
logger = logging.getLogger(__name__)

@uploads_bp.route('/profile-picture', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    """Upload user profile picture"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user from database
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Upload file
        success, message, file_url = upload_service.upload_file(
            file=file,
            upload_type='profile',
            organization_id=str(user.organization_id) if user.organization_id else 'default',
            user_id=current_user_id
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Delete old profile picture if exists
        if user.profile_picture_url:
            upload_service.delete_file(user.profile_picture_url)
        
        # Update user with new profile picture URL
        result = mongo.db.users.update_one(
            {'_id': ObjectId(current_user_id)},
            {
                '$set': {
                    'profile_picture_url': file_url,
                    'updated_at': user_data.get('updated_at')
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update user profile picture'}), 500
        
        logger.info(f"Profile picture uploaded for user {current_user_id}: {file_url}")
        
        return jsonify({
            'message': 'Profile picture uploaded successfully',
            'profile_picture_url': file_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading profile picture: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/organization/<organization_id>/banner', methods=['POST'])
@jwt_required()
def upload_organization_banner(organization_id):
    """Upload organization banner"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Check if user can manage organization
        if not user.can_manage_organization and str(user.organization_id) != organization_id:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get organization
        org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
        if not org_data:
            return jsonify({'error': 'Organization not found'}), 404
        
        organization = Organization.from_dict(org_data)
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Upload file
        success, message, file_url = upload_service.upload_file(
            file=file,
            upload_type='banner',
            organization_id=organization_id
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Delete old banner if exists
        if organization.banner_url:
            upload_service.delete_file(organization.banner_url)
        
        # Update organization with new banner URL
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(organization_id)},
            {
                '$set': {
                    'banner_url': file_url,
                    'updated_at': org_data.get('updated_at')
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update organization banner'}), 500
        
        logger.info(f"Organization banner uploaded for {organization_id}: {file_url}")
        
        return jsonify({
            'message': 'Organization banner uploaded successfully',
            'banner_url': file_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading organization banner: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/organization/<organization_id>/logo', methods=['POST'])
@jwt_required()
def upload_organization_logo(organization_id):
    """Upload organization logo"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Check if user can manage organization
        if not user.can_manage_organization and str(user.organization_id) != organization_id:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get organization
        org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
        if not org_data:
            return jsonify({'error': 'Organization not found'}), 404
        
        organization = Organization.from_dict(org_data)
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Upload file
        success, message, file_url = upload_service.upload_file(
            file=file,
            upload_type='logo',
            organization_id=organization_id
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Delete old logo if exists
        if organization.logo_url:
            upload_service.delete_file(organization.logo_url)
        
        # Update organization with new logo URL
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(organization_id)},
            {
                '$set': {
                    'logo_url': file_url,
                    'updated_at': org_data.get('updated_at')
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update organization logo'}), 500
        
        logger.info(f"Organization logo uploaded for {organization_id}: {file_url}")
        
        return jsonify({
            'message': 'Organization logo uploaded successfully',
            'logo_url': file_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading organization logo: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/center/<center_id>/banner', methods=['POST'])
@jwt_required()
def upload_center_banner(center_id):
    """Upload center banner"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Get center
        center_data = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center_data:
            return jsonify({'error': 'Center not found'}), 404
        
        center = Center.from_dict(center_data)
        
        # Check permissions (user must be able to manage organization or be a coach at this center)
        if not user.can_manage_organization and str(user.organization_id) != str(center.organization_id):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Upload file
        success, message, file_url = upload_service.upload_file(
            file=file,
            upload_type='banner',
            organization_id=str(center.organization_id),
            center_id=center_id
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Delete old banner if exists
        if center.banner_url:
            upload_service.delete_file(center.banner_url)
        
        # Update center with new banner URL
        result = mongo.db.centers.update_one(
            {'_id': ObjectId(center_id)},
            {
                '$set': {
                    'banner_url': file_url,
                    'updated_at': center_data.get('updated_at')
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update center banner'}), 500
        
        logger.info(f"Center banner uploaded for {center_id}: {file_url}")
        
        return jsonify({
            'message': 'Center banner uploaded successfully',
            'banner_url': file_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading center banner: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/center/<center_id>/logo', methods=['POST'])
@jwt_required()
def upload_center_logo(center_id):
    """Upload center logo"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Get center
        center_data = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center_data:
            return jsonify({'error': 'Center not found'}), 404
        
        center = Center.from_dict(center_data)
        
        # Check permissions
        if not user.can_manage_organization and str(user.organization_id) != str(center.organization_id):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Upload file
        success, message, file_url = upload_service.upload_file(
            file=file,
            upload_type='logo',
            organization_id=str(center.organization_id),
            center_id=center_id
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        # Delete old logo if exists
        if center.logo_url:
            upload_service.delete_file(center.logo_url)
        
        # Update center with new logo URL
        result = mongo.db.centers.update_one(
            {'_id': ObjectId(center_id)},
            {
                '$set': {
                    'logo_url': file_url,
                    'updated_at': center_data.get('updated_at')
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Failed to update center logo'}), 500
        
        logger.info(f"Center logo uploaded for {center_id}: {file_url}")
        
        return jsonify({
            'message': 'Center logo uploaded successfully',
            'logo_url': file_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading center logo: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/center/<center_id>/images', methods=['POST'])
@jwt_required()
def upload_center_images(center_id):
    """Upload center images (multiple files)"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Get center
        center_data = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center_data:
            return jsonify({'error': 'Center not found'}), 404
        
        center = Center.from_dict(center_data)
        
        # Check permissions
        if not user.can_manage_organization and str(user.organization_id) != str(center.organization_id):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Check if files are in request
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        uploaded_urls = []
        failed_uploads = []
        
        # Upload each file
        for file in files:
            if file.filename != '':
                success, message, file_url = upload_service.upload_file(
                    file=file,
                    upload_type='center_image',
                    organization_id=str(center.organization_id),
                    center_id=center_id
                )
                
                if success:
                    uploaded_urls.append(file_url)
                else:
                    failed_uploads.append({'filename': file.filename, 'error': message})
        
        # Update center with new image URLs
        if uploaded_urls:
            # Add new URLs to existing images list
            current_images = center.images or []
            updated_images = current_images + uploaded_urls
            
            result = mongo.db.centers.update_one(
                {'_id': ObjectId(center_id)},
                {
                    '$set': {
                        'images': updated_images,
                        'updated_at': center_data.get('updated_at')
                    }
                }
            )
            
            if result.modified_count == 0:
                return jsonify({'error': 'Failed to update center images'}), 500
        
        logger.info(f"Center images uploaded for {center_id}: {len(uploaded_urls)} successful, {len(failed_uploads)} failed")
        
        response_data = {
            'message': f'Uploaded {len(uploaded_urls)} images successfully',
            'uploaded_urls': uploaded_urls
        }
        
        if failed_uploads:
            response_data['failed_uploads'] = failed_uploads
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error uploading center images: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@uploads_bp.route('/center/<center_id>/images/<path:image_url>', methods=['DELETE'])
@jwt_required()
def delete_center_image(center_id, image_url):
    """Delete a specific center image"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user and check permissions
        user_data = mongo.db.users.find_one({'_id': ObjectId(current_user_id)})
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        user = User.from_dict(user_data)
        
        # Get center
        center_data = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center_data:
            return jsonify({'error': 'Center not found'}), 404
        
        center = Center.from_dict(center_data)
        
        # Check permissions
        if not user.can_manage_organization and str(user.organization_id) != str(center.organization_id):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Decode the image URL (it may be URL encoded)
        from urllib.parse import unquote
        decoded_url = unquote(image_url)
        
        # Check if the image exists in the center's images list
        if decoded_url not in (center.images or []):
            return jsonify({'error': 'Image not found in center'}), 404
        
        # Initialize upload service
        upload_service = FileUploadService()
        
        # Delete file from S3
        if upload_service.delete_file(decoded_url):
            # Remove URL from center's images list
            updated_images = [img for img in center.images if img != decoded_url]
            
            result = mongo.db.centers.update_one(
                {'_id': ObjectId(center_id)},
                {
                    '$set': {
                        'images': updated_images,
                        'updated_at': center_data.get('updated_at')
                    }
                }
            )
            
            if result.modified_count == 0:
                return jsonify({'error': 'Failed to update center images'}), 500
            
            logger.info(f"Center image deleted for {center_id}: {decoded_url}")
            
            return jsonify({
                'message': 'Image deleted successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to delete image from storage'}), 500
        
    except Exception as e:
        logger.error(f"Error deleting center image: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
