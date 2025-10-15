from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields, ValidationError
from app.services.feed_service import FeedService
from app.models.post import Post
from app.models.user import User
from app.extensions import mongo
from app.routes.auth import require_role
from app.utils.auth import jwt_or_session_required, require_role_hybrid, get_current_user_info
from bson import ObjectId
from datetime import datetime, timedelta
from app.services.file_upload_service import FileUploadService

feed_bp = Blueprint('feed', __name__)

# Request schemas
class CreatePostSchema(Schema):
    title = fields.Str(required=True, validate=lambda x: 5 <= len(x.strip()) <= 200)
    content = fields.Str(required=True, validate=lambda x: 10 <= len(x.strip()) <= 5000)
    post_type = fields.Str(required=False, missing='announcement', 
                          validate=lambda x: x in ['announcement', 'tip', 'event', 'achievement', 'general'])
    category = fields.Str(required=False, allow_none=True)
    media_urls = fields.List(fields.Url(), required=False, missing=[])
    tags = fields.List(fields.Str(), required=False, missing=[])
    visibility = fields.Str(required=False, missing='public',
                           validate=lambda x: x in ['public', 'students_only', 'coaches_only'])
    scheduled_for = fields.DateTime(required=False, allow_none=True)
    associated_class_id = fields.Str(required=False, allow_none=True)

class CommentSchema(Schema):
    content = fields.Str(required=True, validate=lambda x: 1 <= len(x.strip()) <= 1000)
    parent_comment_id = fields.Str(required=False, allow_none=True)

# API Routes
@feed_bp.route('/api/organizations/feed', methods=['GET'])
@jwt_or_session_required()
def api_get_feed():
    """Get organization feed for user's organization"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user_id = ObjectId(user_info.get('user_id'))
        organization_id = ObjectId(user_info.get('organization_id'))
        
        if not organization_id:
            return jsonify({'error': 'User not associated with any organization'}), 400
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)  # Max 50 per page
        post_type = request.args.get('type')
        category = request.args.get('category')
        
        success, message, feed_data = FeedService.get_organization_feed(
            organization_id=organization_id,
            user_id=current_user_id,
            page=page,
            per_page=per_page,
            post_type=post_type,
            category=category
        )
        print(feed_data)
        
        if success:
            return jsonify(feed_data), 200
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error getting feed: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/organizations/<organization_id>/posts', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin', 'coach'])
def api_create_post(organization_id):
    """Create a new post"""
    try:
        schema = CreatePostSchema()
        data = schema.load(request.json)
        
        current_user_id = get_jwt_identity()
        
        success, message, post_data = FeedService.create_post(
            title=data['title'],
            content=data['content'],
            author_id=current_user_id,
            organization_id=organization_id,
            post_type=data['post_type'],
            category=data.get('category'),
            media_urls=data['media_urls'],
            tags=data['tags'],
            visibility=data['visibility'],
            scheduled_for=data.get('scheduled_for')
        )
        
        if success:
            return jsonify({
                'message': message,
                'post': post_data
            }), 201
        else:
            return jsonify({'error': message}), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating post: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/posts/<post_id>/like', methods=['POST'])
@jwt_or_session_required()
def api_like_post(post_id):
    """Like or unlike a post"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user_id = user_info.get('user_id')
        
        success, message, like_data = FeedService.like_post(post_id, current_user_id)
        
        if success:
            return jsonify({
                'message': message,
                'data': like_data
            }), 200
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error liking post: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/posts/<post_id>/comments', methods=['GET'])
@jwt_or_session_required()
def api_get_comments(post_id):
    """Get comments for a post"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        
        success, message, comments_data = FeedService.get_post_comments(
            post_id=post_id,
            page=page,
            per_page=per_page
        )
        
        if success:
            return jsonify(comments_data), 200
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error getting comments: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/posts/<post_id>/associate-class', methods=['POST'])
@jwt_or_session_required()
@require_role(['org_admin', 'center_admin'])
def api_associate_class(post_id):
    """Associate a class with an announcement post"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401

        # Validate request data
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        if 'class_id' not in data:
            return jsonify({'error': 'class_id is required'}), 400

        class_id = data['class_id']

        # Get post and verify ownership
        post_data = mongo.db.posts.find_one({'_id': ObjectId(post_id)})
        if not post_data:
            return jsonify({'error': 'Post not found'}), 404

        post = Post.from_dict(post_data)
        if not post.can_be_edited_by(user_info['user_id'], user_info['role'], user_info['organization_id']):
            return jsonify({'error': 'Access denied'}), 403

        # Get class data
        class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_data:
            return jsonify({'error': 'Class not found'}), 404

        # Get additional class info
        coach_data = mongo.db.users.find_one({'_id': class_data['coach_id']})
        center_data = mongo.db.centers.find_one({'_id': class_data['center_id']})

        # Create class info
        associated_class = {
            '_id': str(class_data['_id']),
            'name': class_data['name'],
            'scheduled_at': class_data['scheduled_at'],
            'coach_name': coach_data['name'] if coach_data else None,
            'center_name': center_data['name'] if center_data else None
        }

        # Update post
        mongo.db.posts.update_one(
            {'_id': ObjectId(post_id)},
            {'$set': {
                'associated_class': associated_class,
                'updated_at': datetime.utcnow()
            }}
        )

        return jsonify({
            'message': 'Class associated successfully',
            'associated_class': associated_class
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error associating class: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/posts/<post_id>/comments', methods=['POST'])
@jwt_or_session_required()
def api_add_comment(post_id):
    """Add a comment to a post"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        schema = CommentSchema()
        data = schema.load(request.json)
        
        current_user_id = user_info.get('user_id')
        
        success, message, comment_data = FeedService.add_comment(
            post_id=post_id,
            content=data['content'],
            author_id=current_user_id,
            parent_comment_id=data.get('parent_comment_id')
        )
        
        if success:
            return jsonify({
                'message': message,
                'comment': comment_data
            }), 201
        else:
            return jsonify({'error': message}), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding comment: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@feed_bp.route('/api/organizations/<organization_id>/search', methods=['GET'])
@jwt_or_session_required()
def api_search_posts(organization_id):
    """Search posts in organization"""
    try:
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user_id = ObjectId(user_info.get('user_id'))
        user_org_id = ObjectId(user_info.get('organization_id'))
        
        # Verify user belongs to the organization
        if user_org_id != ObjectId(organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query must be at least 2 characters'}), 400
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)
        
        success, message, search_data = FeedService.search_posts(
            organization_id=organization_id,
            query=query,
            user_id=current_user_id,
            page=page,
            per_page=per_page
        )
        
        if success:
            return jsonify(search_data), 200
        else:
            return jsonify({'error': message}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error searching posts: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Web Routes for UI
@feed_bp.route('/feed')
def feed_page():
    """Organization feed page"""
    from app.routes.web import login_required, role_required
    
    @login_required
    def _feed_page():
        # try:
            org_id = ObjectId(session.get('organization_id'))
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            user_role = session.get('role')
            user_id = ObjectId(session.get('user_id'))
            
            # Get organization info
            org_data = mongo.db.organizations.find_one({'_id': org_id})
            if not org_data:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get recent posts for initial load
            success, message, feed_data = FeedService.get_organization_feed(
                organization_id=org_id,
                user_id=user_id,
                page=1,
                per_page=5
            )
            
            posts = feed_data.get('posts', []) if success else []
            
            # Get available categories from existing posts
            categories_cursor = mongo.db.posts.distinct('category', {
                'organization_id': ObjectId(org_id),
                'status': 'published',
                'category': {'$ne': None, '$ne': ''}
            })
            categories = list(categories_cursor)

            


            
            return render_template('feed.html', 
                                 organization=org_data,
                                 posts=posts,
                                 categories=categories,
                                 can_create_posts=user_role in ['org_admin', 'center_admin', 'coach'])
        
        # except Exception as e:
        #     current_app.logger.error(f"Error loading feed page: {str(e)}")
        #     flash('Error loading feed page.', 'error')
        #     return redirect(url_for('web.dashboard'))
    
    return _feed_page()

@feed_bp.route('/create-post')
def create_post_page():
    """Create post page"""
    from app.routes.web import login_required, role_required
    
    @login_required
    @role_required(['org_admin', 'center_admin', 'coach'])
    def _create_post_page():
        try:
            org_id = ObjectId(session.get('organization_id'))
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get organization info
            org_data = mongo.db.organizations.find_one({'_id': org_id})
            if not org_data:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            today = datetime.now()
            next_week = today + timedelta(days=7)

            classes_cursor = mongo.db.classes.find({
                'organization_id': org_id,
                'scheduled_at': {'$gte': today, '$lte': next_week},
            }).sort('scheduled_at', 1)
            
            
            
            classes = []
            for class_data in classes_cursor:
                classes.append(class_data)
            
            
            return render_template('create_post.html', organization=org_data, classes=classes)
        
        except Exception as e:
            current_app.logger.error(f"Error loading create post page: {str(e)}")
            flash('Error loading page.', 'error')
            return redirect(url_for('feed.feed_page'))
    
    return _create_post_page()

@feed_bp.route('/create-post', methods=['POST'])
def submit_post():
    """Handle post creation form submission"""
    from app.routes.web import login_required, role_required
    
    @login_required
    @role_required(['org_admin', 'center_admin', 'coach'])
    def _submit_post():
        try:
            org_id = ObjectId(session.get('organization_id'))
            user_id = ObjectId(session.get('user_id'))
            
            if not org_id or not user_id:
                flash('Invalid session.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get form data
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            post_type = request.form.get('post_type', 'announcement')
            category = request.form.get('category', '').strip() or None
            visibility = request.form.get('visibility', 'public')
            tags_str = request.form.get('tags', '').strip()
            associated_class_id = request.form.get('associated_class', '').strip() or None
            featured_image_urls = []
            # Process tags
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
            
            if 'featured_images' in request.files:
                featured_images = request.files.getlist('featured_images')
                for image in featured_images:
                    if image.filename == '':
                        continue
                    upload_service = FileUploadService()
                    success, message, image_url = upload_service.upload_file(image, 'post_image', str(org_id), str(user_id))
                    if not success:
                        flash(f'Error uploading featured image: {message}', 'error')
                        return redirect(url_for('feed.create_post_page'))
                    featured_image_urls.append(image_url)

            # Basic validation
            if not title or len(title) < 5:
                flash('Title must be at least 5 characters long.', 'error')
                return redirect(url_for('feed.create_post_page'))
            
            if not content or len(content) < 10:
                flash('Content must be at least 10 characters long.', 'error')
                return redirect(url_for('feed.create_post_page'))
            
            # Create post
            success, message, post_data = FeedService.create_post(
                title=title,
                content=content,
                author_id=user_id,
                organization_id=org_id,
                post_type=post_type,
                category=category,
                tags=tags,
                visibility=visibility,
                associated_class_id=associated_class_id,
                media_urls=featured_image_urls
            )
            
            if success:
                flash('Post created successfully!', 'success')
                return redirect(url_for('feed.feed_page'))
            else:
                flash(f'Error creating post: {message}', 'error')
                return redirect(url_for('feed.create_post_page'))
        
        except Exception as e:
            current_app.logger.error(f"Error submitting post: {str(e)}")
            flash('Error creating post. Please try again.', 'error')
            return redirect(url_for('feed.create_post_page'))
    
    return _submit_post()
