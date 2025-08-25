from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields, ValidationError
from app.services.feed_service import FeedService
from app.models.post import Post
from app.models.user import User
from app.extensions import mongo
from app.routes.auth import require_role
from bson import ObjectId
from datetime import datetime

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

class CommentSchema(Schema):
    content = fields.Str(required=True, validate=lambda x: 1 <= len(x.strip()) <= 1000)
    parent_comment_id = fields.Str(required=False, allow_none=True)

# API Routes
@feed_bp.route('/api/organizations/<organization_id>/feed', methods=['GET'])
@jwt_required()
def api_get_feed(organization_id):
    """Get organization feed"""
    try:
        current_user_id = get_jwt_identity()
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
@jwt_required()
def api_like_post(post_id):
    """Like or unlike a post"""
    try:
        current_user_id = get_jwt_identity()
        
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
@jwt_required()
def api_get_comments(post_id):
    """Get comments for a post"""
    try:
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

@feed_bp.route('/api/posts/<post_id>/comments', methods=['POST'])
@jwt_required()
def api_add_comment(post_id):
    """Add a comment to a post"""
    try:
        schema = CommentSchema()
        data = schema.load(request.json)
        
        current_user_id = get_jwt_identity()
        
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
@jwt_required()
def api_search_posts(organization_id):
    """Search posts in organization"""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query must be at least 2 characters'}), 400
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 50)
        current_user_id = get_jwt_identity()
        
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
        try:
            org_id = session.get('organization_id')
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            user_role = session.get('role')
            user_id = session.get('user_id')
            
            # Get organization info
            org_data = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
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
        
        except Exception as e:
            current_app.logger.error(f"Error loading feed page: {str(e)}")
            flash('Error loading feed page.', 'error')
            return redirect(url_for('web.dashboard'))
    
    return _feed_page()

@feed_bp.route('/create-post')
def create_post_page():
    """Create post page"""
    from app.routes.web import login_required, role_required
    
    @login_required
    @role_required(['org_admin', 'center_admin', 'coach'])
    def _create_post_page():
        try:
            org_id = session.get('organization_id')
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get organization info
            org_data = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
            if not org_data:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            return render_template('create_post.html', organization=org_data)
        
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
            org_id = session.get('organization_id')
            user_id = session.get('user_id')
            
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
            
            # Process tags
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
            
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
                visibility=visibility
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
