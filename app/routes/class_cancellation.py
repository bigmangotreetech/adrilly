from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields, ValidationError
from app.services.cancellation_service import CancellationService
from app.models.class_schedule import Class
from app.models.holiday import Holiday, HolidayCalendar
from app.models.user import User
from app.extensions import mongo
from app.routes.auth import require_role
from bson import ObjectId
from datetime import datetime, date, timedelta
import sys
import os

# Add the project root to the path so we can import the fetcher
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from app.utils.auth import jwt_or_session_required, require_role_hybrid
except ImportError:
    # Fallback for systems without auth utils
    def jwt_or_session_required():
        def decorator(f):
            return f
        return decorator
    
    def require_role_hybrid(roles):
        def decorator(f):
            return f
        return decorator

class_cancellation_bp = Blueprint('class_cancellation', __name__)

# Request schemas
class CancelClassSchema(Schema):
    reason = fields.Str(required=True)
    cancellation_type = fields.Str(required=False, missing='manual', 
                                 validate=lambda x: x in ['manual', 'weather', 'facility', 'holiday', 'emergency'])
    refund_required = fields.Bool(required=False, missing=False)
    send_notifications = fields.Bool(required=False, missing=True)
    replacement_class_id = fields.Str(required=False, allow_none=True)

class BulkCancelSchema(Schema):
    class_ids = fields.List(fields.Str(), required=True)
    reason = fields.Str(required=True)
    cancellation_type = fields.Str(required=False, missing='bulk')
    refund_required = fields.Bool(required=False, missing=False)
    send_notifications = fields.Bool(required=False, missing=True)

class HolidaySchema(Schema):
    name = fields.Str(required=True)
    date_observed = fields.Date(required=True)
    description = fields.Str(required=False, allow_none=True)
    affects_scheduling = fields.Bool(required=False, missing=True)

# API Routes
@class_cancellation_bp.route('/api/classes/<class_id>/cancel', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin', 'coach'])
def api_cancel_class(class_id):
    """API endpoint to cancel a class"""
    try:
        schema = CancelClassSchema()
        data = schema.load(request.json)
        
        # Import auth utilities
        from app.utils.auth import get_current_user_id
        current_user_id = get_current_user_id()
        
        success, message, class_data = CancellationService.cancel_class(
            class_id=class_id,
            reason=data['reason'],
            cancelled_by=current_user_id,
            cancellation_type=data['cancellation_type'],
            refund_required=data['refund_required'],
            send_notifications=data['send_notifications'],
            replacement_class_id=data.get('replacement_class_id')
        )
        
        if success:
            return jsonify({
                'message': message,
                'class': class_data
            }), 200
        else:
            return jsonify({'error': message}), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error cancelling class via API: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/classes/bulk-cancel', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_bulk_cancel_classes():
    """API endpoint to cancel multiple classes"""
    try:
        schema = BulkCancelSchema()
        data = schema.load(request.json)
        
        # Import auth utilities
        from app.utils.auth import get_current_user_id
        current_user_id = get_current_user_id()
        
        success, message, results = CancellationService.bulk_cancel_classes(
            class_ids=data['class_ids'],
            reason=data['reason'],
            cancelled_by=current_user_id,
            cancellation_type=data['cancellation_type'],
            refund_required=data['refund_required'],
            send_notifications=data['send_notifications']
        )
        
        if success:
            return jsonify({
                'message': message,
                'results': results
            }), 200
        else:
            return jsonify({
                'error': message,
                'results': results
            }), 400
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error in bulk cancellation via API: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays', methods=['GET'])
@jwt_or_session_required()
def api_get_holidays():
    """Get holidays for the organization"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Get query parameters
        year = request.args.get('year', type=int) or datetime.now().year
        include_public = request.args.get('include_public', 'true').lower() == 'true'
        
        query = {'organization_id': ObjectId(organization_id)}
        if year:
            query['year'] = year
        
        holidays_cursor = mongo.db.holidays.find(query).sort('date_observed', 1)
        holidays = []
        
        for holiday_data in holidays_cursor:
            holiday = Holiday.from_dict(holiday_data)
            holidays.append(holiday.to_dict())
        
        return jsonify({
            'holidays': holidays,
            'year': year,
            'organization_id': organization_id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_create_holiday():
    """Create a new holiday"""
    try:
        schema = HolidaySchema()
        data = schema.load(request.json)
        
        # Import auth utilities
        from app.utils.auth import get_current_user_info
        user_info = get_current_user_info()
        
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
            
        organization_id = user_info.get('organization_id')
        current_user_id = user_info.get('user_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Check if holiday already exists
        existing = mongo.db.holidays.find_one({
            'organization_id': ObjectId(organization_id),
            'date_observed': data['date_observed'],
            'name': data['name']
        })
        
        if existing:
            return jsonify({'error': 'Holiday already exists for this date'}), 400
        
        holiday = Holiday(
            name=data['name'],
            date_observed=data['date_observed'],
            organization_id=organization_id,
            description=data.get('description'),
            affects_scheduling=data['affects_scheduling'],
            is_public_holiday=False  # Custom holidays are not public holidays
        )
        holiday.created_by = ObjectId(current_user_id)
        
        result = mongo.db.holidays.insert_one(holiday.to_dict())
        holiday._id = result.inserted_id
        
        return jsonify({
            'message': 'Holiday created successfully',
            'holiday': holiday.to_dict()
        }), 201
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating holiday: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/import', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin'])
def api_import_holidays():
    """Import public holidays for the year"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        year = request.json.get('year', datetime.now().year)
        country_code = request.json.get('country_code', 'IN')
        
        imported_holidays = HolidayCalendar.import_holidays_for_organization(
            organization_id, year, country_code
        )
        
        return jsonify({
            'message': f'Imported {len(imported_holidays)} holidays for {year}',
            'holidays': [h.to_dict() for h in imported_holidays],
            'year': year,
            'country_code': country_code
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error importing holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/<holiday_id>/cancel-classes', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_cancel_classes_for_holiday(holiday_id):
    """Cancel all classes on a holiday"""
    try:
        # Import auth utilities
        from app.utils.auth import get_current_user_info
        user_info = get_current_user_info()
        
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
            
        organization_id = user_info.get('organization_id')
        current_user_id = user_info.get('user_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Get the holiday
        holiday_data = mongo.db.holidays.find_one({'_id': ObjectId(holiday_id)})
        if not holiday_data:
            return jsonify({'error': 'Holiday not found'}), 404
        
        holiday = Holiday.from_dict(holiday_data)
        
        # Check organization access
        if str(holiday.organization_id) != organization_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Convert date to datetime for the cancellation service
        holiday_datetime = datetime.combine(holiday.date_observed, datetime.min.time())
        
        success, message, results = CancellationService.cancel_classes_for_holiday(
            organization_id=organization_id,
            holiday_date=holiday_datetime,
            cancelled_by=current_user_id,
            send_notifications=request.json.get('send_notifications', True)
        )
        
        if success:
            return jsonify({
                'message': message,
                'holiday': holiday.to_dict(),
                'results': results
            }), 200
        else:
            return jsonify({
                'error': message,
                'results': results
            }), 400
        
    except Exception as e:
        current_app.logger.error(f"Error cancelling classes for holiday: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/cancellation-stats', methods=['GET'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_get_cancellation_stats():
    """Get cancellation statistics"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Get date range from query parameters
        days_back = request.args.get('days', type=int) or 30
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        stats = CancellationService.get_cancellation_stats(
            organization_id, start_date, end_date
        )
        
        return jsonify(stats), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting cancellation stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Web Routes for UI
@class_cancellation_bp.route('/class-management')
def class_management():
    """Class management page with cancellation features"""
    from app.routes.web import login_required, role_required
    
    @login_required
    @role_required(['org_admin', 'center_admin', 'coach'])
    def _class_management():
        # try:
            org_id = session.get('organization_id')
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get upcoming classes
            today = datetime.now()
            next_week = today + timedelta(days=7)

            
            classes_cursor = mongo.db.classes.find({
                'organization_id': org_id,
                'scheduled_at': {'$gte': today, '$lte': next_week},
            }).sort('scheduled_at', 1)
            
            
            
            classes = []
            for class_data in classes_cursor:
                class_obj = Class.from_dict(class_data)
                classes.append(class_obj.to_dict())
            
            # Get recent cancellations
            last_30_days = today - timedelta(days=30)
            cancelled_classes = list(mongo.db.classes.find({
                'organization_id': ObjectId(org_id),
                'status': 'cancelled',
                'cancelled_at': {'$gte': last_30_days}
            }).sort('cancelled_at', -1).limit(10))
            
            # Convert datetime to string
            for classx in cancelled_classes:
                classx['cancelled_at'] = classx['cancelled_at'].strftime('%Y-%m-%d')
            
            # Get holidays for current month
            current_month_start = today.replace(day=1)
            next_month = (current_month_start + timedelta(days=32)).replace(day=1)
            
            holidays = list(mongo.db.holidays.find({
                'organization_id': ObjectId(org_id),
                'date_observed': {'$gte': current_month_start, '$lt': next_month}
            }).sort('date_observed', 1))

            # Convert datetime to string
            for holiday in holidays:
                holiday['date_observed'] = holiday['date_observed'].strftime('%Y-%m-%d')
            

            students = list(mongo.db.users.find({'organization_id': org_id, 'role': 'student'}).sort('name', 1))
            for student in students:
                student['_id'] = str(student['_id'])

            print(students)

            return render_template('class_management.html',
                                 classes=classes,
                                 cancelled_classes=cancelled_classes,
                                 holidays=holidays,
                                 students=students,
                                 )
        
        # except Exception as e:
        #     current_app.logger.error(f"Error loading class management: {str(e)}")
        #     flash('Error loading class management page.', 'error')
        #     return redirect(url_for('web.dashboard'))
    
    return _class_management()

@class_cancellation_bp.route('/holidays-management')
def holidays_management():
    """Holiday management page"""
    from app.routes.web import login_required, role_required
    
    @login_required
    @role_required(['org_admin', 'center_admin'])
    def _holidays_management():
        try:
            org_id = session.get('organization_id')
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get current year holidays
            current_year = datetime.now().year
            today = datetime.now().date()
            
            holidays = list(mongo.db.holidays.find({
                'organization_id': ObjectId(org_id),
            }).sort('date_observed', 1))
            
            # Convert and map fields for template compatibility
            for holiday in holidays:
                if 'date_observed' in holiday and holiday['date_observed'] is not None:
                    # Map date_observed to start_date for template compatibility
                    holiday['start_date'] = holiday['date_observed']
                    holiday['end_date'] = holiday['date_observed']  # Single day holiday
                    
                    # Add type field if not present
                    if 'type' not in holiday:
                        holiday['type'] = 'organization' if not holiday.get('is_public_holiday', True) else 'national'
            
            # Get centers for the dropdown
            centers = list(mongo.db.centers.find({
                'organization_id': ObjectId(org_id),
                'is_active': True
            }).sort('name', 1))
            
            print(holidays)
            return render_template('holidays_management.html',
                                 holidays=holidays,
                                 centers=centers,
                                 current_year=current_year,
                                 today=today)
        
        except Exception as e:
            current_app.logger.error(f"Error loading holidays management: {str(e)}")
            flash('Error loading holidays management page.', 'error')
            return redirect(url_for('web.dashboard'))
    
    return _holidays_management()

@class_cancellation_bp.route('/api/holidays/indian/<int:year>', methods=['GET'])
def api_get_indian_holidays(year):
    """Get Indian holidays for a specific year from database"""
    try:
        # Get holidays from database (stored by the fetch script)
        holidays = list(mongo.db.holidays.find({
            'source': 'calendarific_api',
            'date_observed': {
                '$gte': date(year, 1, 1),
                '$lte': date(year, 12, 31)
            }
        }).sort('date_observed', 1))
        
        # Convert ObjectId to string and format for frontend
        formatted_holidays = []
        for holiday in holidays:
            formatted_holiday = {
                '_id': str(holiday['_id']) if holiday.get('_id') else None,
                'name': holiday['name'],
                'date_observed': holiday['date_observed'].isoformat() if isinstance(holiday['date_observed'], date) else holiday['date_observed'],
                'description': holiday.get('description', ''),
                'locations': holiday.get('locations', 'All India'),
                'holiday_types': holiday.get('holiday_types', ['public']),
                'affects_scheduling': holiday.get('affects_scheduling', True),
                'is_enabled': holiday.get('is_enabled', True),
                'is_imported': holiday.get('is_imported', False),
                'source': holiday.get('source', 'calendarific_api')
            }
            formatted_holidays.append(formatted_holiday)
        
        return jsonify({
            'holidays': formatted_holidays,
            'year': year,
            'total': len(formatted_holidays)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching Indian holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/import-indian', methods=['POST'])
def api_import_indian_holidays():
    """Import selected Indian holidays into organization's holiday list"""
    try:
        data = request.get_json()
        holidays_to_import = data.get('holidays', [])
        year = data.get('year', datetime.now().year)
        
        # Get current user and organization
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_data = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        if not user_data or not user_data.get('organization_id'):
            return jsonify({'error': 'User not associated with an organization'}), 400
        
        organization_id = user_data['organization_id']
        imported_count = 0
        
        for holiday_data in holidays_to_import:
            try:
                # Parse the date
                if isinstance(holiday_data.get('date_observed'), str):
                    holiday_date = datetime.fromisoformat(holiday_data['date_observed']).date()
                else:
                    holiday_date = holiday_data['date_observed']
                
                # Check if holiday already exists for this organization
                existing = mongo.db.holidays.find_one({
                    'organization_id': organization_id,
                    'name': holiday_data['name'],
                    'date_observed': holiday_date
                })
                
                if not existing:
                    # Create new holiday for the organization
                    new_holiday = Holiday(
                        name=holiday_data['name'],
                        date_observed=holiday_date,
                        organization_id=organization_id,
                        description=holiday_data.get('description', ''),
                        locations=holiday_data.get('locations', 'All India'),
                        holiday_types=holiday_data.get('holiday_types', ['public']),
                        affects_scheduling=holiday_data.get('affects_scheduling', True),
                        source='imported_from_api',
                        is_enabled=True,
                        is_imported=True,
                        api_data=holiday_data
                    )
                    
                    result = mongo.db.holidays.insert_one(new_holiday.to_dict())
                    if result.inserted_id:
                        imported_count += 1
                        current_app.logger.info(f"Imported holiday: {holiday_data['name']}")
                
            except Exception as e:
                current_app.logger.error(f"Error importing holiday {holiday_data.get('name', 'Unknown')}: {str(e)}")
                continue
        
        return jsonify({
            'message': f'Successfully imported {imported_count} holidays',
            'imported_count': imported_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error importing holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/fetch/<int:year>', methods=['POST'])
def api_fetch_indian_holidays(year):
    """Fetch Indian holidays from Calendarific API for a specific year"""
    try:
        # Import the fetcher class
        try:
            from fetch_indian_holidays import IndianHolidayFetcher
        except ImportError:
            return jsonify({'error': 'Holiday fetcher service not available'}), 500
        
        # Check admin permissions
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_data = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        if not user_data or user_data.get('role') not in ['org_admin', 'center_admin']:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Fetch holidays using the fetcher
        fetcher = IndianHolidayFetcher()
        success = fetcher.fetch_and_store_holidays(year)
        
        if success:
            # Get the stored holidays count
            holidays_count = mongo.db.holidays.count_documents({
                'source': 'calendarific_api',
                'date_observed': {
                    '$gte': date(year, 1, 1),
                    '$lte': date(year, 12, 31)
                }
            })
            
            return jsonify({
                'message': f'Successfully fetched holidays for {year}',
                'year': year,
                'holidays_count': holidays_count
            }), 200
        else:
            return jsonify({'error': f'Failed to fetch holidays for {year}'}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error fetching holidays via API: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
