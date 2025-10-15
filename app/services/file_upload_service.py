import os
import uuid
import mimetypes
from datetime import datetime
from typing import Optional, Tuple, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image
import io
import os

class FileUploadService:
    """Service for handling file uploads to AWS S3"""
    
    # Allowed file types for different upload types
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}
    
    # Maximum file sizes (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DOCUMENT_SIZE = 25 * 1024 * 1024  # 25MB
    
    # Image dimensions for different types
    IMAGE_CONFIGS = {
        'profile': {'max_width': 400, 'max_height': 400, 'quality': 85},
        'banner': {'max_width': 1200, 'max_height': 400, 'quality': 90},
        'logo': {'max_width': 300, 'max_height': 300, 'quality': 90},
        'center_image': {'max_width': 800, 'max_height': 600, 'quality': 85},
        'class_picture': {'max_width': 1200, 'max_height': 1200, 'quality': 90},
        'post_image': {'max_width': 1200, 'max_height': 1200, 'quality': 90}
    }
    
    def __init__(self):
        self.bucket_name = os.environ.get('AWS_BUCKET_NAME')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.aws_access_key = os.environ.get('AWS_ACCESS_KEY')
        self.aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

        # Initialize S3 client
        self._init_s3_client()
    
    def _init_s3_client(self):
        """Initialize AWS S3 client"""
        try:
            if self.aws_access_key and self.aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
                current_app.logger.info("AWS S3 client initialized successfully")
            else:
                # Try using default AWS credentials (IAM role, etc.)
                self.s3_client = boto3.client('s3', region_name=self.region)
                current_app.logger.info("AWS S3 client initialized with default credentials")
                
        except NoCredentialsError:
            current_app.logger.error("AWS credentials not found")
            self.s3_client = None
        except Exception as e:
            current_app.logger.error(f"Failed to initialize AWS S3 client: {str(e)}")
            self.s3_client = None
    
    def _validate_file(self, file, upload_type: str) -> Tuple[bool, str]:
        """Validate file type and size"""
        if not file or not file.filename:
            return False, "No file provided"
        
        # Get file extension
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Check file type
        if upload_type in ['profile', 'banner', 'logo', 'center_image', 'class_picture', 'post_image']:
            if file_ext not in self.ALLOWED_IMAGE_EXTENSIONS:
                return False, f"Invalid file type. Allowed: {', '.join(self.ALLOWED_IMAGE_EXTENSIONS)}"
            max_size = self.MAX_IMAGE_SIZE
        else:
            if file_ext not in self.ALLOWED_DOCUMENT_EXTENSIONS:
                return False, f"Invalid file type. Allowed: {', '.join(self.ALLOWED_DOCUMENT_EXTENSIONS)}"
            max_size = self.MAX_DOCUMENT_SIZE
        
        # Check file size (approximate check)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > max_size:
            size_mb = max_size // (1024 * 1024)
            return False, f"File too large. Maximum size: {size_mb}MB"
        
        return True, "Valid"
    
    def _process_image(self, file, upload_type: str) -> io.BytesIO:
        """Process and optimize image based on upload type"""
        if upload_type not in self.IMAGE_CONFIGS:
            return file
        
        config = self.IMAGE_CONFIGS[upload_type]
        
        try:
            # Open image with Pillow
            image = Image.open(file)
            
            # Convert to RGB if necessary (for PNG with transparency)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize image if needed
            max_width = config['max_width']
            max_height = config['max_height']
            
            # Calculate new dimensions maintaining aspect ratio
            width, height = image.size
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized image to bytes
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=config['quality'], optimize=True)
            output.seek(0)
            
            return output
            
        except Exception as e:
            current_app.logger.error(f"Error processing image: {str(e)}")
            file.seek(0)
            return file
    
    def _generate_s3_key(self, upload_type: str, organization_id: str, filename: str) -> str:
        """Generate S3 key for file"""
        # Create unique filename with timestamp and UUID
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(secure_filename(filename))
        
        # Construct S3 key based on upload type
        if upload_type == 'profile':
            return f"profiles/{organization_id}/{timestamp}_{unique_id}{ext}"
        elif upload_type in ['banner', 'logo']:
            return f"organizations/{organization_id}/{upload_type}/{timestamp}_{unique_id}{ext}"
        elif upload_type == 'center_image':
            return f"centers/{organization_id}/{timestamp}_{unique_id}{ext}"
        elif upload_type == 'class_picture':
            return f"class_pictures/{organization_id}/{timestamp}_{unique_id}{ext}"
        elif upload_type == 'post_image':
            return f"posts/{organization_id}/{timestamp}_{unique_id}{ext}"
        else:
            return f"uploads/{organization_id}/{upload_type}/{timestamp}_{unique_id}{ext}"
    
    def upload_file(self, file, upload_type: str, organization_id: str, 
                   user_id: str = None, center_id: str = None) -> Tuple[bool, str, Optional[str]]:
        """
        Upload file to S3
        
        Args:
            file: File object from request
            upload_type: Type of upload ('profile', 'banner', 'logo', 'center_image', 'class_picture', 'post_image')
            organization_id: Organization ID for file organization
            user_id: User ID (for profile pictures)
            center_id: Center ID (for center images)
            
        Returns:
            Tuple of (success, message, file_url)
        """
        
        if not self.s3_client:
            return False, "S3 service not available", None
        
        if not self.bucket_name:
            return False, "S3 bucket not configured", None
        
        # Validate file
        is_valid, message = self._validate_file(file, upload_type)
        if not is_valid:
            return False, message, None
        
        try:
            # Generate S3 key
            s3_key = self._generate_s3_key(upload_type, organization_id, file.filename)
            
            # Process image if it's an image upload
            if upload_type in self.IMAGE_CONFIGS:
                processed_file = self._process_image(file, upload_type)
                file_data = processed_file.getvalue() if hasattr(processed_file, 'getvalue') else processed_file.read()
                content_type = 'image/jpeg'  # All processed images are JPEG
            else:
                file.seek(0)
                file_data = file.read()
                content_type = mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type,
                CacheControl='max-age=31536000',  # 1 year cache
                Metadata={
                    'upload_type': upload_type,
                    'organization_id': organization_id,
                    'user_id': user_id or '',
                    'center_id': center_id or '',
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )
            
            # Generate public URL
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            current_app.logger.info(f"File uploaded successfully: {s3_key}")
            print(f"File uploaded successfully: {s3_key}")
            return True, "File uploaded successfully", file_url
            
        except ClientError as e:
            error_msg = f"AWS S3 error: {str(e)}"
            current_app.logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            current_app.logger.error(error_msg)
            return False, error_msg, None
    
    def delete_file(self, file_url: str) -> bool:
        """Delete file from S3 by URL"""
        if not self.s3_client or not file_url:
            return False
        
        try:
            # Extract S3 key from URL
            if f"s3.{self.region}.amazonaws.com" in file_url:
                s3_key = file_url.split(f"s3.{self.region}.amazonaws.com/")[1]
            else:
                current_app.logger.error(f"Invalid S3 URL format: {file_url}")
                return False
            
            # Delete from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            current_app.logger.info(f"File deleted successfully: {s3_key}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def list_files(self, prefix: str, max_keys: int = 100) -> List[dict]:
        """List files with given prefix"""
        if not self.s3_client:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for obj in response.get('Contents', []):
                file_info = {
                    'key': obj['Key'],
                    'url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{obj['Key']}",
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                }
                files.append(file_info)
            
            return files
            
        except Exception as e:
            current_app.logger.error(f"Error listing files: {str(e)}")
            return []
