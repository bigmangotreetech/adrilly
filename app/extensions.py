from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from celery import Celery
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

# Initialize extensions
mongo = PyMongo()
jwt = JWTManager()
cors = CORS()

def verify_database_connection():
    """Verify MongoDB connection and return status"""
    try:
        # Check if mongo.db is available
        if mongo.db is None:
            return False, "MongoDB not initialized - check MONGODB_URI configuration"
        
        mongo.db.command('ping')
        return True, "Database connection successful"
    except ServerSelectionTimeoutError:
        return False, "Could not connect to MongoDB server"
    except OperationFailure as e:
        return False, f"Database operation failed: {e}"
    except NotImplementedError:
        # This happens when trying to use mongo.db in boolean context
        # If we get here, mongo.db exists, so try ping directly
        try:
            mongo.db.command('ping')
            return True, "Database connection successful"
        except Exception as inner_e:
            return False, f"Database ping failed: {inner_e}"
    except Exception as e:
        return False, f"Unexpected database error: {e}"

def ensure_collection_exists(collection_name, create_if_missing=True):
    """Ensure a collection exists, optionally create if missing"""
    try:
        # Check if mongo.db is available
        if mongo.db is None:
            return False, f"MongoDB not initialized - cannot check collection {collection_name}"
        
        existing_collections = mongo.db.list_collection_names()
        
        if collection_name not in existing_collections:
            if create_if_missing:
                mongo.db.create_collection(collection_name)
                return True, f"Created collection: {collection_name}"
            else:
                return False, f"Collection {collection_name} does not exist"
        else:
            return True, f"Collection {collection_name} exists"
    except Exception as e:
        return False, f"Error checking collection {collection_name}: {e}"

def make_celery(app):
    """Create and configure Celery instance"""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery 