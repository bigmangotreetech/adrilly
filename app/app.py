from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import config
from app.extensions import mongo, jwt, cors
from app.extensions import celery
import os
import logging

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Get the absolute path to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(project_root, 'templates')
    static_folder = os.path.join(project_root, 'static')
    
    
    # Create Flask app with correct template and static folders
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    mongo.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)
    
    # Create Celery instance
    # celery = make_celery(app)
    
    # Add context processor to make session available in templates
    @app.context_processor
    def inject_session():
        from flask import session
        return {
            'session': session
        }
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Initialize startup scripts
    initialize_startup_scripts(app, celery)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'Sports Coaching Management API',
            'version': '1.0.0'
        })
    
    return app, celery

def make_celery(app):
    """Create a new Celery object and tie together the Celery config to the app's config."""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

def register_blueprints(app):
    """Register all blueprints"""
    from app.routes.auth import auth_bp
    from app.routes.classes import classes_bp
    from app.routes.webhooks import webhooks_bp
    from app.routes.attendance import attendance_bp
    from app.routes.progress import progress_bp
    from app.routes.payments import payments_bp
    from app.routes.users import users_bp
    from app.routes.equipment import equipment_bp
    from app.routes.uploads import uploads_bp
    from app.routes.web import web_bp
    from app.routes.organization_signup import org_signup_bp
    from app.routes.class_cancellation import class_cancellation_bp
    from app.routes.feed import feed_bp
    from app.routes.enhanced_webhooks import enhanced_webhooks_bp
    from app.routes.enhanced_payments import register_payment_blueprints
    from app.routes.performance_monitoring import register_performance_blueprints
    from app.routes.security_monitoring import register_security_blueprints
    from app.routes.mobile_api import mobile_api_bp
    from app.routes.payment_api import payment_api_bp
    from app.routes.leads import leads_bp
    
    # Register API blueprints (they already have /api prefix in their definitions)
    app.register_blueprint(auth_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(leads_bp)
    
    # Register web blueprint without prefix (for the UI)
    app.register_blueprint(web_bp)
    
    # Register organization signup blueprint
    app.register_blueprint(org_signup_bp)
    
    # Register class cancellation blueprint
    app.register_blueprint(class_cancellation_bp)
    
    # Register feed blueprint
    app.register_blueprint(feed_bp)
    
    # Register enhanced webhooks blueprint
    app.register_blueprint(enhanced_webhooks_bp)
    
    # Register enhanced payment blueprints
    register_payment_blueprints(app)
    
    # Register performance monitoring blueprints
    register_performance_blueprints(app)
    
    # Register security monitoring blueprints
    register_security_blueprints(app)

    # Register mobile API blueprint
    app.register_blueprint(mobile_api_bp)
    
    # Register payment API blueprint
    app.register_blueprint(payment_api_bp)

def register_error_handlers(app):
    """Register error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request'}), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized'}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden'}), 403

def initialize_startup_scripts(app, celery):
    """Initialize all startup scripts and tasks"""
    logger = logging.getLogger(__name__)
    
    try:
        # Only run initialization in production or when explicitly requested
        skip_init = os.environ.get('SKIP_STARTUP_INIT', 'false').lower() == 'true'
        
        if skip_init:
            logger.info("[SKIP] Skipping startup initialization (SKIP_STARTUP_INIT=true)")
            return
        
        logger.info("[STARTUP] Running startup initialization...")
        
        # Import and run the initialization
        from app.startup.initialization import initialize_app
        
        # Run initialization in a separate thread to avoid blocking app startup
        import threading
        
        def run_init():
            try:
                with app.app_context():
                    from app.tasks.class_creation_tasks import (
                        create_daily_classes_function,
                    )
                    create_daily_classes = create_daily_classes_function()
            
                    result = initialize_app(app, celery)
                    if result:
                        logger.info("[SUCCESS] Startup initialization completed successfully")
                    else:
                        logger.warning(f"[WARNING] Startup initialization completed with issues: {result.get('summary', 'Unknown')}")
            except Exception as e:
                logger.error(f"[ERROR] Startup initialization failed: {str(e)}")
        
        # Start initialization in background thread
        init_thread = threading.Thread(target=run_init, daemon=True)
        init_thread.start()
        
        logger.info("[INFO] Startup initialization started in background")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to start initialization: {str(e)}")
        # Don't fail app startup if initialization fails

# JWT error handlers
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({'error': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'error': 'Invalid token'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'error': 'Authorization token is required'}), 401

