from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Any, Optional

class Post:
    """Post model for organization social feed"""
    
    def __init__(self, title, content, author_id, organization_id, 
                 post_type='announcement', category=None, media_urls=None,
                 tags=None, visibility='public', scheduled_for=None,
                 associated_class=None):
        self.title = title
        self.content = content
        self.author_id = ObjectId(author_id) if author_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.post_type = post_type  # 'announcement', 'tip', 'event', 'achievement', 'general'
        self.category = category  # Optional category like 'nutrition', 'training', 'safety'
        self.media_urls = media_urls or []  # List of image/video URLs
        self.tags = tags or []  # List of hashtags
        self.visibility = visibility  # 'public', 'students_only', 'coaches_only'
        self.scheduled_for = scheduled_for  # For scheduled posts
        self.associated_class = associated_class  # Associated class details
        # Status and engagement
        self.status = 'draft' if scheduled_for else 'published'  # 'draft', 'published', 'archived'
        self.is_pinned = False
        self.likes_count = 0
        self.comments_count = 0
        self.views_count = 0
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.published_at = None if scheduled_for else datetime.utcnow()
        
        # Rich content support
        self.content_format = 'text'  # 'text', 'markdown', 'html'
        self.excerpt = None  # Auto-generated summary
        
        # Engagement tracking
        self.liked_by = []  # List of user IDs who liked
        self.shared_count = 0
        
        # SEO and discovery
        self.keywords = []  # For internal search
        self.featured = False  # Featured posts get priority display
        self.associated_class = associated_class  # Associated class details
    
    def to_dict(self, include_engagement=True):
        """Convert post to dictionary"""
        data = {
            'title': self.title,
            'content': self.content,
            'author_id': str(self.author_id) if self.author_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'post_type': self.post_type,
            'category': self.category,
            'media_urls': self.media_urls,
            'tags': self.tags,
            'visibility': self.visibility,
            'scheduled_for': self.scheduled_for,
            'status': self.status,
            'is_pinned': self.is_pinned,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'published_at': self.published_at,
            'content_format': self.content_format,
            'excerpt': self.excerpt,
            'shared_count': self.shared_count,
            'keywords': self.keywords,
            'featured': self.featured,
            'associated_class': self.associated_class,
        }
        
        if include_engagement:
            data.update({
                'likes_count': self.likes_count,
                'comments_count': self.comments_count,
                'views_count': self.views_count,
                'liked_by': [str(uid) for uid in self.liked_by]
            })
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create post from dictionary"""
        post = cls(
            title=data['title'],
            content=data['content'],
            author_id=data.get('author_id'),
            organization_id=data.get('organization_id'),
            post_type=data.get('post_type', 'announcement'),
            category=data.get('category'),
            media_urls=data.get('media_urls', []),
            tags=data.get('tags', []),
            visibility=data.get('visibility', 'public'),
            scheduled_for=data.get('scheduled_for'),
            associated_class=data.get('associated_class'),
        )
        
        # Set additional attributes
        if '_id' in data:
            post._id = data['_id']
        if 'status' in data:
            post.status = data['status']
        if 'is_pinned' in data:
            post.is_pinned = data['is_pinned']
        if 'likes_count' in data:
            post.likes_count = data['likes_count']
        if 'comments_count' in data:
            post.comments_count = data['comments_count']
        if 'views_count' in data:
            post.views_count = data['views_count']
        if 'created_at' in data:
            post.created_at = data['created_at']
        if 'updated_at' in data:
            post.updated_at = data['updated_at']
        if 'published_at' in data:
            post.published_at = data['published_at']
        if 'content_format' in data:
            post.content_format = data['content_format']
        if 'excerpt' in data:
            post.excerpt = data['excerpt']
        if 'liked_by' in data:
            post.liked_by = [ObjectId(uid) for uid in data['liked_by']]
        if 'shared_count' in data:
            post.shared_count = data['shared_count']
        if 'keywords' in data:
            post.keywords = data['keywords']
        if 'featured' in data:
            post.featured = data['featured']
        if 'associated_class' in data:
            post.associated_class = data['associated_class']
        return post
    
    def generate_excerpt(self, max_length=150):
        """Generate excerpt from content"""
        if len(self.content) <= max_length:
            self.excerpt = self.content
        else:
            # Find last complete word within limit
            truncated = self.content[:max_length]
            last_space = truncated.rfind(' ')
            if last_space > 0:
                self.excerpt = truncated[:last_space] + '...'
            else:
                self.excerpt = truncated + '...'
        
        self.updated_at = datetime.utcnow()
        return self.excerpt
    
    def add_like(self, user_id):
        """Add a like from user"""
        user_id = ObjectId(user_id) if user_id else None
        if user_id and user_id not in self.liked_by:
            self.liked_by.append(user_id)
            self.likes_count = len(self.liked_by)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_like(self, user_id):
        """Remove a like from user"""
        user_id = ObjectId(user_id) if user_id else None
        if user_id and user_id in self.liked_by:
            self.liked_by.remove(user_id)
            self.likes_count = len(self.liked_by)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        # Don't update updated_at for view increments to avoid spam
    
    def can_be_viewed_by(self, user_role, user_org_id):
        """Check if post can be viewed by user"""
        # Check organization access
        if str(self.organization_id) != str(user_org_id):
            return False
        
        # Check visibility permissions
        if self.visibility == 'public':
            return True
        elif self.visibility == 'students_only':
            return user_role == 'student'
        elif self.visibility == 'coaches_only':
            return user_role in ['coach', 'center_admin', 'org_admin']
        
        return False
    
    def can_be_edited_by(self, user_id, user_role, user_org_id):
        """Check if post can be edited by user"""
        # Check organization access
        if str(self.organization_id) != str(user_org_id):
            return False
        
        # Author can edit their own posts
        if str(self.author_id) == str(user_id):
            return True
        
        # Org admins can edit any post in their org
        if user_role == 'org_admin':
            return True
        
        return False
    
    def publish_now(self):
        """Publish a draft or scheduled post immediately"""
        self.status = 'published'
        self.published_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if self.scheduled_for:
            self.scheduled_for = None
    
    def archive(self):
        """Archive the post"""
        self.status = 'archived'
        self.updated_at = datetime.utcnow()
    
    def pin(self):
        """Pin the post"""
        self.is_pinned = True
        self.updated_at = datetime.utcnow()
    
    def unpin(self):
        """Unpin the post"""
        self.is_pinned = False
        self.updated_at = datetime.utcnow()

class Comment:
    """Comment model for post comments"""
    
    def __init__(self, content, author_id, post_id, parent_comment_id=None):
        self.content = content
        self.author_id = ObjectId(author_id) if author_id else None
        self.post_id = ObjectId(post_id) if post_id else None
        self.parent_comment_id = ObjectId(parent_comment_id) if parent_comment_id else None
        
        # Status and engagement
        self.likes_count = 0
        self.liked_by = []
        self.is_edited = False
        self.is_deleted = False
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # Content moderation
        self.is_flagged = False
        self.flagged_reason = None
    
    def to_dict(self):
        """Convert comment to dictionary"""
        data = {
            'content': self.content,
            'author_id': str(self.author_id) if self.author_id else None,
            'post_id': str(self.post_id) if self.post_id else None,
            'parent_comment_id': str(self.parent_comment_id) if self.parent_comment_id else None,
            'likes_count': self.likes_count,
            'liked_by': [str(uid) for uid in self.liked_by],
            'is_edited': self.is_edited,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_flagged': self.is_flagged,
            'flagged_reason': self.flagged_reason,
            'organization_id': str(self.organization_id) if self.organization_id else None,
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create comment from dictionary"""
        comment = cls(
            content=data['content'],
            author_id=data.get('author_id'),
            post_id=data.get('post_id'),
            parent_comment_id=data.get('parent_comment_id')
        )
        
        # Set additional attributes
        if '_id' in data:
            comment._id = data['_id']
        if 'likes_count' in data:
            comment.likes_count = data['likes_count']
        if 'liked_by' in data:
            comment.liked_by = [ObjectId(uid) for uid in data['liked_by']]
        if 'is_edited' in data:
            comment.is_edited = data['is_edited']
        if 'is_deleted' in data:
            comment.is_deleted = data['is_deleted']
        if 'created_at' in data:
            comment.created_at = data['created_at']
        if 'updated_at' in data:
            comment.updated_at = data['updated_at']
        if 'is_flagged' in data:
            comment.is_flagged = data['is_flagged']
        if 'flagged_reason' in data:
            comment.flagged_reason = data['flagged_reason']
        
        return comment
    
    def add_like(self, user_id):
        """Add a like from user"""
        user_id = ObjectId(user_id) if user_id else None
        if user_id and user_id not in self.liked_by:
            self.liked_by.append(user_id)
            self.likes_count = len(self.liked_by)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_like(self, user_id):
        """Remove a like from user"""
        user_id = ObjectId(user_id) if user_id else None
        if user_id and user_id in self.liked_by:
            self.liked_by.remove(user_id)
            self.likes_count = len(self.liked_by)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def edit_content(self, new_content):
        """Edit comment content"""
        self.content = new_content
        self.is_edited = True
        self.updated_at = datetime.utcnow()
    
    def soft_delete(self):
        """Soft delete the comment"""
        self.is_deleted = True
        self.content = "[Comment deleted]"
        self.updated_at = datetime.utcnow()
    
    def flag(self, reason):
        """Flag comment for moderation"""
        self.is_flagged = True
        self.flagged_reason = reason
        self.updated_at = datetime.utcnow()
