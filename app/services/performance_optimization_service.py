from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from app.extensions import mongo
from flask import current_app
from bson import ObjectId
import json
import hashlib
import time
from functools import wraps
import redis
import os

class PerformanceOptimizationService:
    """Service for implementing comprehensive performance optimizations"""
    
    def __init__(self):
        # Initialize Redis for caching if available
        self.redis_client = None
        if os.getenv('REDIS_URL'):
            try:
                import redis
                self.redis_client = redis.from_url(os.getenv('REDIS_URL'))
                self.redis_client.ping()  # Test connection
            except Exception as e:
                current_app.logger.warning(f"Redis not available: {str(e)}")
        
        # Cache configuration
        self.cache_ttl = {
            'user_profile': 300,      # 5 minutes
            'organization_data': 600,  # 10 minutes
            'class_schedule': 180,     # 3 minutes
            'payment_summary': 240,    # 4 minutes
            'attendance_stats': 300,   # 5 minutes
            'feed_posts': 120,         # 2 minutes
            'analytics_data': 900      # 15 minutes
        }
    
    def create_database_indexes(self) -> Dict:
        """Create optimized database indexes for better query performance"""
        try:
            indexes_created = {
                'users': [],
                'organizations': [],
                'classes': [],
                'payments': [],
                'attendance': [],
                'posts': [],
                'whatsapp_logs': []
            }
            
            # Users collection indexes
            # Drop old non-sparse indexes first
            try:
                mongo.db.users.drop_index("phone_number_1")
            except Exception:
                pass
            try:
                mongo.db.users.drop_index("email_1")
            except Exception:
                pass
            
            # Create sparse unique indexes for email and phone_number
            mongo.db.users.create_index("phone_number", unique=True, sparse=True)
            mongo.db.users.create_index("email", unique=True, sparse=True)
            indexes_created['users'].extend(['phone_number_1', 'email_1'])
            
            # Other users indexes
            users_indexes = [
                ('organization_id', 1),
                ('role', 1),
                ('is_active', 1),
                ([('organization_id', 1), ('role', 1), ('is_active', 1)], None),  # Compound index
                ([('phone_number', 1), ('is_active', 1)], None),
                ('created_at', -1)
            ]
            
            for index in users_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.users.create_index(index[0])
                else:
                    result = mongo.db.users.create_index([(index[0], index[1])])
                indexes_created['users'].append(str(result))
            
            # Organizations collection indexes
            org_indexes = [
                ('owner_id', 1),
                ('signup_slug', 1),
                ('signup_token', 1),
                ('is_active', 1),
                ('created_at', -1)
            ]
            
            for index in org_indexes:
                result = mongo.db.organizations.create_index([(index[0], index[1])])
                indexes_created['organizations'].append(str(result))
            
            # Classes collection indexes
            class_indexes = [
                ('organization_id', 1),
                ('coach_id', 1),
                ('scheduled_at', 1),
                ('status', 1),
                ([('organization_id', 1), ('scheduled_at', 1)], None),
                ([('organization_id', 1), ('status', 1)], None),
                ([('coach_id', 1), ('scheduled_at', 1)], None),
                ('student_ids', 1),
                ('group_ids', 1),
                ('created_at', -1)
            ]
            
            for index in class_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.classes.create_index(index[0])
                else:
                    result = mongo.db.classes.create_index([(index[0], index[1])])
                indexes_created['classes'].append(str(result))
            
            # Payments collection indexes
            payment_indexes = [
                ('student_id', 1),
                ('organization_id', 1),
                ('status', 1),
                ('due_date', 1),
                ('payment_id', 1),
                ('gateway_payment_id', 1),
                ([('organization_id', 1), ('status', 1)], None),
                ([('student_id', 1), ('status', 1)], None),
                ([('organization_id', 1), ('due_date', 1)], None),
                ('created_at', -1)
            ]
            
            for index in payment_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.payments.create_index(index[0])
                else:
                    result = mongo.db.payments.create_index([(index[0], index[1])])
                indexes_created['payments'].append(str(result))
            
            # Attendance collection indexes
            attendance_indexes = [
                ('class_id', 1),
                ('student_id', 1),
                ('status', 1),
                ('attendance_id', 1),
                ([('class_id', 1), ('student_id', 1)], None),
                ([('student_id', 1), ('status', 1)], None),
                ([('class_id', 1), ('status', 1)], None),
                ('created_at', -1),
                ('rsvp_response', 1)
            ]
            
            for index in attendance_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.attendance.create_index(index[0])
                else:
                    result = mongo.db.attendance.create_index([(index[0], index[1])])
                indexes_created['attendance'].append(str(result))
            
            # Posts collection indexes (for feed)
            post_indexes = [
                ('organization_id', 1),
                ('author_id', 1),
                ('post_type', 1),
                ('is_published', 1),
                ([('organization_id', 1), ('is_published', 1), ('created_at', -1)], None),
                ('created_at', -1)
            ]
            
            for index in post_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.posts.create_index(index[0])
                else:
                    result = mongo.db.posts.create_index([(index[0], index[1])])
                indexes_created['posts'].append(str(result))
            
            # WhatsApp logs indexes
            whatsapp_indexes = [
                ('to_number', 1),
                ('from_number', 1),
                ('message_type', 1),
                ('status', 1),
                ('timestamp', -1),
                ([('message_type', 1), ('timestamp', -1)], None)
            ]
            
            for index in whatsapp_indexes:
                if isinstance(index[0], list):
                    result = mongo.db.whatsapp_logs.create_index(index[0])
                else:
                    result = mongo.db.whatsapp_logs.create_index([(index[0], index[1])])
                indexes_created['whatsapp_logs'].append(str(result))
            
            return {
                'status': 'success',
                'indexes_created': indexes_created,
                'total_indexes': sum(len(indexes) for indexes in indexes_created.values())
            }
            
        except Exception as e:
            current_app.logger.error(f"Error creating database indexes: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            current_app.logger.warning(f"Cache get error: {str(e)}")
            return None
    
    def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            current_app.logger.warning(f"Cache set error: {str(e)}")
            return False
    
    def cache_delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            current_app.logger.warning(f"Cache delete error: {str(e)}")
            return False
    
    def cache_delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            current_app.logger.warning(f"Cache pattern delete error: {str(e)}")
            return 0
    
    def generate_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key from prefix and arguments"""
        key_parts = [prefix] + [str(arg) for arg in args]
        key_string = ':'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def cached_function(self, cache_key_prefix: str, ttl: int = 300):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.generate_cache_key(cache_key_prefix, *args, **sorted(kwargs.items()))
                
                # Try to get from cache first
                cached_result = self.cache_get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                self.cache_set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator
    
    def optimize_query_performance(self, collection_name: str, query: Dict, 
                                 explain: bool = False) -> Dict:
        """Analyze and optimize query performance"""
        try:
            collection = getattr(mongo.db, collection_name)
            
            # Measure execution time
            start_time = time.time()
            
            if explain:
                # Get query execution plan
                explain_result = collection.find(query).explain()
                execution_time = time.time() - start_time
                
                return {
                    'collection': collection_name,
                    'query': query,
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'explain_result': explain_result,
                    'optimization_suggestions': self._analyze_query_performance(explain_result)
                }
            else:
                # Just execute and measure time
                result = list(collection.find(query))
                execution_time = time.time() - start_time
                
                return {
                    'collection': collection_name,
                    'query': query,
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'documents_returned': len(result),
                    'result': result
                }
                
        except Exception as e:
            current_app.logger.error(f"Error optimizing query performance: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_query_performance(self, explain_result: Dict) -> List[str]:
        """Analyze query execution plan and suggest optimizations"""
        suggestions = []
        
        execution_stats = explain_result.get('executionStats', {})
        winning_plan = explain_result.get('queryPlanner', {}).get('winningPlan', {})
        
        # Check if query uses index
        if winning_plan.get('stage') == 'COLLSCAN':
            suggestions.append("Query is performing a collection scan. Consider adding an index.")
        
        # Check execution time
        execution_time_ms = execution_stats.get('executionTimeMillis', 0)
        if execution_time_ms > 100:
            suggestions.append(f"Query took {execution_time_ms}ms. Consider optimization.")
        
        # Check documents examined vs returned
        docs_examined = execution_stats.get('totalDocsExamined', 0)
        docs_returned = execution_stats.get('totalDocsReturned', 0)
        
        if docs_examined > 0 and docs_returned > 0:
            efficiency = docs_returned / docs_examined
            if efficiency < 0.1:
                suggestions.append("Query is examining many more documents than returned. Consider more selective indexes.")
        
        if not suggestions:
            suggestions.append("Query performance looks good!")
        
        return suggestions
    
    def batch_operations(self, collection_name: str, operations: List[Dict], 
                        operation_type: str = 'insert') -> Dict:
        """Perform batch operations for better performance"""
        try:
            collection = getattr(mongo.db, collection_name)
            
            start_time = time.time()
            
            if operation_type == 'insert':
                result = collection.insert_many(operations)
                success_count = len(result.inserted_ids)
            
            elif operation_type == 'update':
                bulk_operations = []
                for op in operations:
                    bulk_operations.append(
                        collection.UpdateOne(op['filter'], op['update'], upsert=op.get('upsert', False))
                    )
                result = collection.bulk_write(bulk_operations)
                success_count = result.modified_count
            
            elif operation_type == 'delete':
                bulk_operations = []
                for op in operations:
                    bulk_operations.append(collection.DeleteOne(op['filter']))
                result = collection.bulk_write(bulk_operations)
                success_count = result.deleted_count
            
            else:
                return {'error': f'Unsupported operation type: {operation_type}'}
            
            execution_time = time.time() - start_time
            
            return {
                'operation_type': operation_type,
                'total_operations': len(operations),
                'successful_operations': success_count,
                'execution_time_ms': round(execution_time * 1000, 2),
                'operations_per_second': round(len(operations) / execution_time, 2)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in batch operations: {str(e)}")
            return {'error': str(e)}
    
    def optimize_aggregation_pipeline(self, collection_name: str, pipeline: List[Dict]) -> Dict:
        """Optimize aggregation pipeline performance"""
        try:
            collection = getattr(mongo.db, collection_name)
            
            # Analyze pipeline stages
            optimization_suggestions = []
            
            for i, stage in enumerate(pipeline):
                stage_name = list(stage.keys())[0]
                
                # Check for early $match stages
                if stage_name == '$match' and i > 2:
                    optimization_suggestions.append(f"Stage {i}: Consider moving $match stage earlier in pipeline")
                
                # Check for $lookup without indexes
                if stage_name == '$lookup':
                    optimization_suggestions.append(f"Stage {i}: Ensure indexes exist on lookup fields")
                
                # Check for $sort without $limit
                if stage_name == '$sort':
                    has_limit = any('$limit' in str(s) for s in pipeline[i+1:])
                    if not has_limit:
                        optimization_suggestions.append(f"Stage {i}: Consider adding $limit after $sort")
            
            # Execute pipeline and measure performance
            start_time = time.time()
            result = list(collection.aggregate(pipeline, allowDiskUse=True))
            execution_time = time.time() - start_time
            
            return {
                'collection': collection_name,
                'pipeline_stages': len(pipeline),
                'execution_time_ms': round(execution_time * 1000, 2),
                'documents_returned': len(result),
                'optimization_suggestions': optimization_suggestions,
                'result': result
            }
            
        except Exception as e:
            current_app.logger.error(f"Error optimizing aggregation pipeline: {str(e)}")
            return {'error': str(e)}
    
    def implement_pagination(self, collection_name: str, query: Dict, 
                           page: int = 1, per_page: int = 20, sort_field: str = '_id',
                           sort_direction: int = -1) -> Dict:
        """Implement efficient pagination"""
        try:
            collection = getattr(mongo.db, collection_name)
            
            # Calculate skip value
            skip = (page - 1) * per_page
            
            # Get total count (cached if possible)
            count_cache_key = self.generate_cache_key(f'{collection_name}_count', query)
            total_count = self.cache_get(count_cache_key)
            
            if total_count is None:
                total_count = collection.count_documents(query)
                self.cache_set(count_cache_key, total_count, 60)  # Cache for 1 minute
            
            # Get paginated results
            start_time = time.time()
            results = list(
                collection.find(query)
                .sort(sort_field, sort_direction)
                .skip(skip)
                .limit(per_page)
            )
            execution_time = time.time() - start_time
            
            # Calculate pagination metadata
            total_pages = (total_count + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            return {
                'data': results,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_prev': has_prev,
                    'has_next': has_next,
                    'prev_page': page - 1 if has_prev else None,
                    'next_page': page + 1 if has_next else None
                },
                'performance': {
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'documents_returned': len(results)
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error implementing pagination: {str(e)}")
            return {'error': str(e)}
    
    def monitor_performance_metrics(self) -> Dict:
        """Monitor application performance metrics"""
        try:
            metrics = {
                'database': {},
                'cache': {},
                'application': {},
                'timestamp': datetime.utcnow()
            }
            
            # Database metrics
            db_stats = mongo.db.command('dbStats')
            metrics['database'] = {
                'collections': db_stats.get('collections', 0),
                'objects': db_stats.get('objects', 0),
                'data_size_mb': round(db_stats.get('dataSize', 0) / (1024 * 1024), 2),
                'storage_size_mb': round(db_stats.get('storageSize', 0) / (1024 * 1024), 2),
                'index_size_mb': round(db_stats.get('indexSize', 0) / (1024 * 1024), 2)
            }
            
            # Cache metrics
            if self.redis_client:
                redis_info = self.redis_client.info()
                metrics['cache'] = {
                    'used_memory_mb': round(redis_info.get('used_memory', 0) / (1024 * 1024), 2),
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0),
                    'hit_rate': round(
                        redis_info.get('keyspace_hits', 0) / 
                        max(redis_info.get('keyspace_hits', 0) + redis_info.get('keyspace_misses', 0), 1) * 100, 
                        2
                    )
                }
            
            # Collection-specific metrics
            collections = ['users', 'organizations', 'classes', 'payments', 'attendance', 'posts']
            collection_metrics = {}
            
            for collection_name in collections:
                collection = getattr(mongo.db, collection_name)
                stats = collection.estimated_document_count()
                collection_metrics[collection_name] = {
                    'document_count': stats,
                    'indexes': len(list(collection.list_indexes()))
                }
            
            metrics['collections'] = collection_metrics
            
            return metrics
            
        except Exception as e:
            current_app.logger.error(f"Error monitoring performance metrics: {str(e)}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
        """Clean up old data to maintain performance"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            cleanup_results = {}
            
            # Clean up old WhatsApp logs
            whatsapp_result = mongo.db.whatsapp_logs.delete_many({
                'timestamp': {'$lt': cutoff_date}
            })
            cleanup_results['whatsapp_logs'] = whatsapp_result.deleted_count
            
            # Clean up old RSVP logs
            rsvp_result = mongo.db.rsvp_logs.delete_many({
                'timestamp': {'$lt': cutoff_date}
            })
            cleanup_results['rsvp_logs'] = rsvp_result.deleted_count
            
            # Clean up old analytics reports
            analytics_result = mongo.db.whatsapp_analytics_reports.delete_many({
                'generated_at': {'$lt': cutoff_date}
            })
            cleanup_results['analytics_reports'] = analytics_result.deleted_count
            
            # Clean up old payment reminder history
            mongo.db.payments.update_many(
                {},
                {'$pull': {'reminder_history': {'sent_at': {'$lt': cutoff_date}}}}
            )
            
            return {
                'status': 'success',
                'cutoff_date': cutoff_date,
                'cleanup_results': cleanup_results,
                'total_deleted': sum(cleanup_results.values())
            }
            
        except Exception as e:
            current_app.logger.error(f"Error cleaning up old data: {str(e)}")
            return {'error': str(e)}
    
    def optimize_large_collections(self) -> Dict:
        """Optimize large collections for better performance"""
        try:
            optimization_results = {}
            
            # Analyze collection sizes
            collections_to_optimize = ['attendance', 'payments', 'whatsapp_logs', 'posts']
            
            for collection_name in collections_to_optimize:
                collection = getattr(mongo.db, collection_name)
                doc_count = collection.estimated_document_count()
                
                if doc_count > 10000:  # Only optimize large collections
                    # Create compound indexes for common queries
                    optimization_results[collection_name] = {
                        'document_count': doc_count,
                        'optimizations_applied': []
                    }
                    
                    if collection_name == 'attendance':
                        # Optimize for attendance queries
                        try:
                            collection.create_index([
                                ('student_id', 1),
                                ('created_at', -1)
                            ], background=True)
                            optimization_results[collection_name]['optimizations_applied'].append(
                                'Student attendance history index'
                            )
                        except Exception:
                            pass  # Index might already exist
                    
                    elif collection_name == 'payments':
                        # Optimize for payment queries
                        try:
                            collection.create_index([
                                ('organization_id', 1),
                                ('status', 1),
                                ('due_date', 1)
                            ], background=True)
                            optimization_results[collection_name]['optimizations_applied'].append(
                                'Organization payment status index'
                            )
                        except Exception:
                            pass
                    
                    elif collection_name == 'whatsapp_logs':
                        # Optimize for WhatsApp log queries
                        try:
                            collection.create_index([
                                ('message_type', 1),
                                ('timestamp', -1)
                            ], background=True)
                            optimization_results[collection_name]['optimizations_applied'].append(
                                'Message type timeline index'
                            )
                        except Exception:
                            pass
            
            return {
                'status': 'success',
                'optimization_results': optimization_results
            }
            
        except Exception as e:
            current_app.logger.error(f"Error optimizing large collections: {str(e)}")
            return {'error': str(e)}

# Global performance service instance
performance_service = PerformanceOptimizationService()
