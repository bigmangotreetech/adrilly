from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt
from app.services.performance_optimization_service import performance_service
from app.routes.auth import require_role
from app.routes.web import login_required, role_required
from marshmallow import Schema, fields, ValidationError
from datetime import datetime

performance_bp = Blueprint('performance', __name__, url_prefix='/api/performance')

# Web interface blueprint
performance_web_bp = Blueprint('performance_web', __name__)

@performance_bp.route('/create-indexes', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def create_database_indexes():
    """Create optimized database indexes"""
    try:
        result = performance_service.create_database_indexes()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/metrics', methods=['GET'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def get_performance_metrics():
    """Get comprehensive performance metrics"""
    try:
        metrics = performance_service.monitor_performance_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/optimize-query', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def optimize_query():
    """Analyze and optimize specific query performance"""
    try:
        data = request.json
        collection_name = data.get('collection')
        query = data.get('query', {})
        explain = data.get('explain', False)
        
        if not collection_name:
            return jsonify({'error': 'Collection name is required'}), 400
        
        result = performance_service.optimize_query_performance(
            collection_name, query, explain
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/optimize-aggregation', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def optimize_aggregation():
    """Optimize aggregation pipeline performance"""
    try:
        data = request.json
        collection_name = data.get('collection')
        pipeline = data.get('pipeline', [])
        
        if not collection_name or not pipeline:
            return jsonify({'error': 'Collection name and pipeline are required'}), 400
        
        result = performance_service.optimize_aggregation_pipeline(
            collection_name, pipeline
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/batch-operations', methods=['POST'])
@jwt_required()
@require_role(['super_admin', 'org_admin'])
def perform_batch_operations():
    """Perform batch database operations"""
    try:
        data = request.json
        collection_name = data.get('collection')
        operations = data.get('operations', [])
        operation_type = data.get('operation_type', 'insert')
        
        if not collection_name or not operations:
            return jsonify({'error': 'Collection name and operations are required'}), 400
        
        result = performance_service.batch_operations(
            collection_name, operations, operation_type
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/paginate/<collection_name>', methods=['GET'])
@jwt_required()
def get_paginated_data(collection_name):
    """Get paginated data from collection"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_field = request.args.get('sort_field', '_id')
        sort_direction = request.args.get('sort_direction', -1, type=int)
        
        # Parse query parameters
        query = {}
        for key, value in request.args.items():
            if key not in ['page', 'per_page', 'sort_field', 'sort_direction']:
                query[key] = value
        
        result = performance_service.implement_pagination(
            collection_name, query, page, per_page, sort_field, sort_direction
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/cleanup-data', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def cleanup_old_data():
    """Clean up old data to maintain performance"""
    try:
        data = request.json
        days_to_keep = data.get('days_to_keep', 90)
        
        result = performance_service.cleanup_old_data(days_to_keep)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/optimize-collections', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def optimize_large_collections():
    """Optimize large collections for better performance"""
    try:
        result = performance_service.optimize_large_collections()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/cache/get/<key>', methods=['GET'])
@jwt_required()
@require_role(['super_admin'])
def get_cache_value(key):
    """Get value from cache"""
    try:
        value = performance_service.cache_get(key)
        return jsonify({'key': key, 'value': value}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/cache/set', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def set_cache_value():
    """Set value in cache"""
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        ttl = data.get('ttl', 300)
        
        if not key:
            return jsonify({'error': 'Key is required'}), 400
        
        success = performance_service.cache_set(key, value, ttl)
        return jsonify({'success': success}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/cache/delete/<key>', methods=['DELETE'])
@jwt_required()
@require_role(['super_admin'])
def delete_cache_value(key):
    """Delete value from cache"""
    try:
        success = performance_service.cache_delete(key)
        return jsonify({'success': success}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/cache/clear-pattern', methods=['POST'])
@jwt_required()
@require_role(['super_admin'])
def clear_cache_pattern():
    """Clear cache keys matching pattern"""
    try:
        data = request.json
        pattern = data.get('pattern')
        
        if not pattern:
            return jsonify({'error': 'Pattern is required'}), 400
        
        deleted_count = performance_service.cache_delete_pattern(pattern)
        return jsonify({'deleted_count': deleted_count}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Web interface routes
@performance_web_bp.route('/performance-dashboard')
@login_required
@role_required(['super_admin', 'org_admin'])
def performance_dashboard():
    """Performance monitoring dashboard"""
    try:
        # Get current performance metrics
        metrics = performance_service.monitor_performance_metrics()
        
        return render_template('performance_dashboard.html', metrics=metrics)
    except Exception as e:
        return f"Error loading performance dashboard: {str(e)}", 500

@performance_web_bp.route('/query-analyzer')
@login_required
@role_required(['super_admin'])
def query_analyzer():
    """Query performance analyzer page"""
    return render_template('query_analyzer.html')

@performance_web_bp.route('/cache-manager')
@login_required
@role_required(['super_admin'])
def cache_manager():
    """Cache management interface"""
    return render_template('cache_manager.html')

# Cached decorator examples for common operations
@performance_service.cached_function('user_profile', ttl=300)
def get_cached_user_profile(user_id: str):
    """Get user profile with caching"""
    from app.extensions import mongo
    from bson import ObjectId
    
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return user_data

@performance_service.cached_function('organization_stats', ttl=600)
def get_cached_organization_stats(org_id: str):
    """Get organization statistics with caching"""
    from app.extensions import mongo
    from bson import ObjectId
    
    pipeline = [
        {'$match': {'organization_id': ObjectId(org_id)}},
        {
            '$group': {
                '_id': None,
                'total_students': {'$sum': 1},
                'active_students': {
                    '$sum': {'$cond': [{'$eq': ['$is_active', True]}, 1, 0]}
                }
            }
        }
    ]
    
    stats = list(mongo.db.users.aggregate(pipeline))
    return stats[0] if stats else {}

@performance_service.cached_function('class_schedule', ttl=180)
def get_cached_class_schedule(org_id: str, date_start: str, date_end: str):
    """Get class schedule with caching"""
    from app.extensions import mongo
    from bson import ObjectId
    from datetime import datetime
    
    start_date = datetime.fromisoformat(date_start)
    end_date = datetime.fromisoformat(date_end)
    
    classes = list(mongo.db.classes.find({
        'organization_id': ObjectId(org_id),
        'scheduled_at': {'$gte': start_date, '$lte': end_date},
        'status': {'$ne': 'cancelled'}
    }).sort('scheduled_at', 1))
    
    return classes

@performance_service.cached_function('payment_summary', ttl=240)
def get_cached_payment_summary(org_id: str):
    """Get payment summary with caching"""
    from app.extensions import mongo
    from bson import ObjectId
    
    pipeline = [
        {'$match': {'organization_id': ObjectId(org_id)}},
        {
            '$group': {
                '_id': '$status',
                'count': {'$sum': 1},
                'total_amount': {'$sum': '$amount'}
            }
        }
    ]
    
    summary = list(mongo.db.payments.aggregate(pipeline))
    return summary

# Utility functions for performance optimization
def invalidate_user_cache(user_id: str):
    """Invalidate user-related cache entries"""
    performance_service.cache_delete_pattern(f'user_profile:{user_id}*')

def invalidate_organization_cache(org_id: str):
    """Invalidate organization-related cache entries"""
    performance_service.cache_delete_pattern(f'organization_stats:{org_id}*')
    performance_service.cache_delete_pattern(f'class_schedule:{org_id}*')
    performance_service.cache_delete_pattern(f'payment_summary:{org_id}*')

def register_performance_blueprints(app):
    """Register performance monitoring blueprints"""
    app.register_blueprint(performance_bp)
    app.register_blueprint(performance_web_bp)
