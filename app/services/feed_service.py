from datetime import datetime, timedelta
from flask import current_app
from bson import ObjectId
from app.extensions import mongo
from app.models.post import Post, Comment
from app.models.user import User
from typing import Tuple, List, Dict, Any, Optional
import re
from pymongo import DESCENDING, ASCENDING

class FeedService:
    """Service for managing organization feed and social features"""
    
    @staticmethod
    def create_post(
        title: str,
        content: str,
        author_id: str,
        organization_id: str,
        post_type: str = 'announcement',
        category: str = None,
        media_urls: List[str] = None,
        tags: List[str] = None,
        visibility: str = 'public',
        scheduled_for: datetime = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Create a new post
        
        Args:
            title: Post title
            content: Post content
            author_id: User ID of the author
            organization_id: Organization ID
            post_type: Type of post
            category: Optional category
            media_urls: List of media URLs
            tags: List of hashtags
            visibility: Visibility setting
            scheduled_for: Optional scheduled publish time
            
        Returns:
            Tuple of (success, message, post_data)
        """
        try:
            # Validate author
            author_data = mongo.db.users.find_one({'_id': ObjectId(author_id)})
            if not author_data:
                return False, "Author not found", None
            
            author = User.from_dict(author_data)
            
            # Check if author can create posts
            if not FeedService._can_user_create_posts(author, organization_id):
                return False, "Insufficient permissions to create posts", None
            
            # Clean and validate content
            content = FeedService._clean_content(content)
            if len(content.strip()) < 10:
                return False, "Post content must be at least 10 characters", None
            
            # Process tags
            tags = FeedService._process_tags(tags or [])
            
            # Create post
            post = Post(
                title=title.strip(),
                content=content,
                author_id=author_id,
                organization_id=organization_id,
                post_type=post_type,
                category=category,
                media_urls=media_urls or [],
                tags=tags,
                visibility=visibility,
                scheduled_for=scheduled_for
            )
            
            # Generate excerpt
            post.generate_excerpt()
            
            # Generate keywords for search
            post.keywords = FeedService._extract_keywords(title + " " + content)
            
            # Insert into database
            result = mongo.db.posts.insert_one(post.to_dict())
            post._id = result.inserted_id
            
            current_app.logger.info(f"Post created by {author.name} ({author_id}) in org {organization_id}")
            
            return True, "Post created successfully", post.to_dict()
            
        except Exception as e:
            current_app.logger.error(f"Error creating post: {str(e)}")
            return False, "Error creating post", None
    
    @staticmethod
    def get_organization_feed(
        organization_id: str,
        user_id: str,
        page: int = 1,
        per_page: int = 10,
        post_type: str = None,
        category: str = None
    ) -> Tuple[bool, str, Dict]:
        """
        Get organization feed with pagination
        
        Args:
            organization_id: Organization ID
            user_id: User requesting the feed
            page: Page number (1-based)
            per_page: Posts per page
            post_type: Optional filter by post type
            category: Optional filter by category
            
        Returns:
            Tuple of (success, message, feed_data)
        """
        try:
            # Get user for permission check
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if not user_data:
                return False, "User not found", {}
            
            user = User.from_dict(user_data)
            
            # Build query
            query = {
                'organization_id': ObjectId(organization_id),
                'status': 'published'
            }
            
            # Add visibility filter based on user role
            if user.role == 'student':
                query['visibility'] = {'$in': ['public', 'students_only']}
            elif user.role in ['coach', 'center_admin']:
                query['visibility'] = {'$in': ['public', 'coaches_only']}
            # Org admins can see all posts
            
            # Add filters
            if post_type:
                query['post_type'] = post_type
            if category:
                query['category'] = category
            
            # Calculate pagination
            skip = (page - 1) * per_page
            
            # Get posts with sorting (pinned first, then by published date)
            posts_cursor = mongo.db.posts.find(query).sort([
                ('is_pinned', DESCENDING),
                ('published_at', DESCENDING)
            ]).skip(skip).limit(per_page)
            
            posts = []
            for post_data in posts_cursor:
                post = Post.from_dict(post_data)
                
                # Increment view count
                mongo.db.posts.update_one(
                    {'_id': post._id},
                    {'$inc': {'views_count': 1}}
                )
                
                # Get author info
                author_data = mongo.db.users.find_one({'_id': post.author_id})
                author_info = {
                    'name': author_data.get('name', 'Unknown'),
                    'role': author_data.get('role', 'user'),
                    'profile_picture_url': author_data.get('profile_picture_url')
                } if author_data else {}
                
                # Get recent comments (last 3)
                recent_comments = FeedService._get_recent_comments(post._id, 3)
                
                post_dict = post.to_dict()
                post_dict['author'] = author_info
                post_dict['recent_comments'] = recent_comments
                post_dict['user_has_liked'] = ObjectId(user_id) in post.liked_by
                
                posts.append(post_dict)
            
            # Get total count for pagination
            total_posts = mongo.db.posts.count_documents(query)
            total_pages = (total_posts + per_page - 1) // per_page
            
            feed_data = {
                'posts': posts,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_posts': total_posts,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
            return True, "Feed retrieved successfully", feed_data
            
        except Exception as e:
            current_app.logger.error(f"Error getting organization feed: {str(e)}")
            return False, "Error retrieving feed", {}
    
    @staticmethod
    def like_post(post_id: str, user_id: str) -> Tuple[bool, str, Dict]:
        """Like or unlike a post"""
        try:
            # Get post
            post_data = mongo.db.posts.find_one({'_id': ObjectId(post_id)})
            if not post_data:
                return False, "Post not found", {}
            
            post = Post.from_dict(post_data)
            
            # Check if user already liked
            user_obj_id = ObjectId(user_id)
            if user_obj_id in post.liked_by:
                # Unlike
                post.remove_like(user_id)
                action = 'unliked'
            else:
                # Like
                post.add_like(user_id)
                action = 'liked'
            
            # Update in database
            mongo.db.posts.update_one(
                {'_id': ObjectId(post_id)},
                {
                    '$set': {
                        'liked_by': [str(uid) for uid in post.liked_by],
                        'likes_count': post.likes_count,
                        'updated_at': post.updated_at
                    }
                }
            )
            
            return True, f"Post {action}", {
                'likes_count': post.likes_count,
                'user_has_liked': user_obj_id in post.liked_by
            }
            
        except Exception as e:
            current_app.logger.error(f"Error liking post: {str(e)}")
            return False, "Error updating like status", {}
    
    @staticmethod
    def add_comment(
        post_id: str,
        content: str,
        author_id: str,
        parent_comment_id: str = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Add a comment to a post"""
        try:
            # Validate post exists
            post_data = mongo.db.posts.find_one({'_id': ObjectId(post_id)})
            if not post_data:
                return False, "Post not found", None
            
            # Validate content
            content = content.strip()
            if len(content) < 1:
                return False, "Comment cannot be empty", None
            
            if len(content) > 1000:
                return False, "Comment too long (max 1000 characters)", None
            
            # Create comment
            comment = Comment(
                content=content,
                author_id=author_id,
                post_id=post_id,
                parent_comment_id=parent_comment_id
            )
            
            # Insert comment
            result = mongo.db.comments.insert_one(comment.to_dict())
            comment._id = result.inserted_id
            
            # Update post comment count
            mongo.db.posts.update_one(
                {'_id': ObjectId(post_id)},
                {'$inc': {'comments_count': 1}}
            )
            
            # Get author info for response
            author_data = mongo.db.users.find_one({'_id': ObjectId(author_id)})
            author_info = {
                'name': author_data.get('name', 'Unknown'),
                'role': author_data.get('role', 'user'),
                'profile_picture_url': author_data.get('profile_picture_url')
            } if author_data else {}
            
            comment_dict = comment.to_dict()
            comment_dict['author'] = author_info
            
            return True, "Comment added successfully", comment_dict
            
        except Exception as e:
            current_app.logger.error(f"Error adding comment: {str(e)}")
            return False, "Error adding comment", None
    
    @staticmethod
    def get_post_comments(
        post_id: str,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[bool, str, Dict]:
        """Get comments for a post with pagination"""
        try:
            skip = (page - 1) * per_page
            
            # Get comments
            comments_cursor = mongo.db.comments.find({
                'post_id': ObjectId(post_id),
                'is_deleted': False
            }).sort('created_at', ASCENDING).skip(skip).limit(per_page)
            
            comments = []
            for comment_data in comments_cursor:
                comment = Comment.from_dict(comment_data)
                
                # Get author info
                author_data = mongo.db.users.find_one({'_id': comment.author_id})
                author_info = {
                    'name': author_data.get('name', 'Unknown'),
                    'role': author_data.get('role', 'user'),
                    'profile_picture_url': author_data.get('profile_picture_url')
                } if author_data else {}
                
                comment_dict = comment.to_dict()
                comment_dict['author'] = author_info
                
                comments.append(comment_dict)
            
            # Get total count
            total_comments = mongo.db.comments.count_documents({
                'post_id': ObjectId(post_id),
                'is_deleted': False
            })
            
            total_pages = (total_comments + per_page - 1) // per_page
            
            return True, "Comments retrieved successfully", {
                'comments': comments,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_comments': total_comments,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting comments: {str(e)}")
            return False, "Error retrieving comments", {}
    
    @staticmethod
    def search_posts(
        organization_id: str,
        query: str,
        user_id: str,
        page: int = 1,
        per_page: int = 10
    ) -> Tuple[bool, str, Dict]:
        """Search posts in organization"""
        try:
            # Get user for permission check
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if not user_data:
                return False, "User not found", {}
            
            user = User.from_dict(user_data)
            
            # Build search query
            search_query = {
                'organization_id': ObjectId(organization_id),
                'status': 'published',
                '$or': [
                    {'title': {'$regex': query, '$options': 'i'}},
                    {'content': {'$regex': query, '$options': 'i'}},
                    {'tags': {'$regex': query, '$options': 'i'}},
                    {'keywords': {'$regex': query, '$options': 'i'}}
                ]
            }
            
            # Add visibility filter
            if user.role == 'student':
                search_query['visibility'] = {'$in': ['public', 'students_only']}
            elif user.role in ['coach', 'center_admin']:
                search_query['visibility'] = {'$in': ['public', 'coaches_only']}
            
            # Calculate pagination
            skip = (page - 1) * per_page
            
            # Execute search
            posts_cursor = mongo.db.posts.find(search_query).sort(
                'published_at', DESCENDING
            ).skip(skip).limit(per_page)
            
            posts = []
            for post_data in posts_cursor:
                post = Post.from_dict(post_data)
                
                # Get author info
                author_data = mongo.db.users.find_one({'_id': post.author_id})
                author_info = {
                    'name': author_data.get('name', 'Unknown'),
                    'role': author_data.get('role', 'user')
                } if author_data else {}
                
                post_dict = post.to_dict()
                post_dict['author'] = author_info
                post_dict['user_has_liked'] = ObjectId(user_id) in post.liked_by
                
                posts.append(post_dict)
            
            # Get total count
            total_posts = mongo.db.posts.count_documents(search_query)
            total_pages = (total_posts + per_page - 1) // per_page
            
            return True, "Search completed", {
                'posts': posts,
                'query': query,
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_posts': total_posts,
                    'total_pages': total_pages
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error searching posts: {str(e)}")
            return False, "Error searching posts", {}
    
    @staticmethod
    def _can_user_create_posts(user: User, organization_id: str) -> bool:
        """Check if user can create posts"""
        # Must be in the same organization
        if str(user.organization_id) != str(organization_id):
            return False
        
        # Only coaches and admins can create posts
        return user.role in ['org_admin', 'center_admin', 'coach']
    
    @staticmethod
    def _clean_content(content: str) -> str:
        """Clean and sanitize post content"""
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Basic HTML sanitization (remove script tags, etc.)
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', content, flags=re.IGNORECASE | re.DOTALL)
        
        return content
    
    @staticmethod
    def _process_tags(tags: List[str]) -> List[str]:
        """Process and clean hashtags"""
        processed_tags = []
        for tag in tags:
            tag = tag.strip().lower()
            if tag.startswith('#'):
                tag = tag[1:]
            if tag and len(tag) <= 50:  # Max tag length
                processed_tags.append(tag)
        
        return list(set(processed_tags))  # Remove duplicates
    
    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract keywords for search indexing"""
        # Simple keyword extraction
        words = re.findall(r'\b\w{3,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were',
            'will', 'would', 'could', 'should', 'have', 'has', 'had'
        }
        
        keywords = [word for word in words if word not in stop_words]
        
        # Return unique keywords (max 20)
        return list(set(keywords))[:20]
    
    @staticmethod
    def _get_recent_comments(post_id: ObjectId, limit: int = 3) -> List[Dict]:
        """Get recent comments for a post"""
        try:
            comments_cursor = mongo.db.comments.find({
                'post_id': post_id,
                'is_deleted': False
            }).sort('created_at', DESCENDING).limit(limit)
            
            comments = []
            for comment_data in comments_cursor:
                comment = Comment.from_dict(comment_data)
                
                # Get author info
                author_data = mongo.db.users.find_one({'_id': comment.author_id})
                author_info = {
                    'name': author_data.get('name', 'Unknown'),
                    'role': author_data.get('role', 'user')
                } if author_data else {}
                
                comment_dict = comment.to_dict()
                comment_dict['author'] = author_info
                
                comments.append(comment_dict)
            
            return comments
            
        except Exception as e:
            current_app.logger.error(f"Error getting recent comments: {str(e)}")
            return []
