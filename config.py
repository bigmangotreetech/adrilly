import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/sports_coaching'
    
    # Flask-PyMongo expects MONGO_URI with database name
    @staticmethod
    def get_mongo_uri():
        """Get MongoDB URI with database name for Flask-PyMongo"""
        uri = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/sports_coaching'
        
        # If it's a MongoDB Atlas URI without database name, add 'adrilly'
        if 'mongodb.net/' in uri and '?' in uri:
            base_uri, params = uri.split('?', 1)
            if not base_uri.endswith('/'):
                base_uri += '/'
            # Add database name if not present
            if base_uri.endswith('mongodb.net/'):
                uri = f"{base_uri}adrilly?{params}"
        
        return uri
    
    MONGO_URI = get_mongo_uri.__func__()
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # WhatsApp Configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM')
    
    # Interakt Configuration (Alternative)
    INTERAKT_API_KEY = os.environ.get('INTERAKT_API_KEY')
    INTERAKT_BASE_URL = os.environ.get('INTERAKT_BASE_URL')
    
    # Webhook Configuration
    WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL') or 'http://localhost:5000'
    
    # App Configuration
    APP_HOST = os.environ.get('APP_HOST') or '0.0.0.0'
    APP_PORT = int(os.environ.get('APP_PORT') or 5000)
    
    # Email Verification Configuration
    VERIFICATION_METHOD = os.environ.get('VERIFICATION_METHOD') or 'tmp'  # 'email' or 'tmp'
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION') or 'us-east-1'
    
    # AWS SES Configuration
    SES_FROM_EMAIL = os.environ.get('SES_FROM_EMAIL') or 'noreply@adrilly.com'
    
    # AWS S3 Configuration
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET') or 'adrilly-uploads'
    
    # Verification Code Settings
    VERIFICATION_CODE_EXPIRY = int(os.environ.get('VERIFICATION_CODE_EXPIRY') or 600)  # 10 minutes
    VERIFICATION_CODE_LENGTH = int(os.environ.get('VERIFICATION_CODE_LENGTH') or 6)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    MONGODB_URI = 'mongodb://localhost:27017/sports_coaching_test'
    MONGO_URI = 'mongodb://localhost:27017/sports_coaching_test'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 