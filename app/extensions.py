from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from celery import Celery
import os

# Initialize extensions
mongo = PyMongo()
jwt = JWTManager()
cors = CORS()

def make_celery(app):
    """Create a new Celery object and tie together the Celery config to the app's config."""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
        include=[
            'tasks.reminder_tasks',
            'tasks.enhanced_reminder_tasks',
            'tasks.class_creation_tasks'
            'tasks.holiday_tasks'
            'tasks.billing_cycle_tasks',
        ]
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

def init_extensions(app):
    """Initialize Flask extensions."""
    # Configure MongoDB
    app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/adrilly")
    
    # Initialize extensions
    mongo.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)

celery = make_celery(app)