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
from datetime import datetime, date, timedelta, time as dt_time
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
            cancelled_by=str(current_user_id),
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
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        # Use the new holiday service
        from app.services.holiday_service import HolidayService
        holidays = HolidayService.get_organization_holidays(
            organization_id=organization_id,
            year=year,
            include_inactive=include_inactive
        )
        
        return jsonify({
            'holidays': holidays,
            'year': year,
            'organization_id': organization_id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/master', methods=['GET'])
@jwt_or_session_required()
def api_get_master_holidays():
    """Get master holidays available for import"""
    try:
        # Import auth utilities
        from app.utils.auth import get_current_user_info
        user_info = get_current_user_info()
        
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
            
        organization_id = user_info.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Get query parameters
        year = request.args.get('year', type=int) or datetime.now().year
        
        # Use the new holiday service
        from app.services.holiday_service import HolidayService
        available_holidays = HolidayService.get_available_holidays_for_org(
            organization_id=organization_id,
            year=year
        )
        
        return jsonify({
            'holidays': available_holidays,
            'year': year,
            'organization_id': organization_id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting master holidays: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/api/holidays/import-selected', methods=['POST'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_import_selected_holidays():
    """Import selected master holidays to organization"""
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
        
        # Get request data
        data = request.get_json()
        holiday_ids = data.get('holiday_ids', [])
        
        if not holiday_ids:
            return jsonify({'error': 'No holidays selected for import'}), 400
        
        # Use the new holiday service
        from app.services.holiday_service import HolidayService
        result = HolidayService.import_holidays_to_organization(
            organization_id=organization_id,
            holiday_ids=holiday_ids,
            created_by=current_user_id
        )
        
        if result['success']:
            return jsonify({
                'message': f"Successfully imported {result['imported_count']} holidays",
                'imported_count': result['imported_count'],
                'errors': result['errors']
            }), 200
        else:
            return jsonify({
                'error': 'Failed to import holidays',
                'errors': result['errors']
            }), 400
        
    except Exception as e:
        current_app.logger.error(f"Error importing holidays: {str(e)}")
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
        
        # Use the new holiday service to create custom holiday
        from app.services.holiday_service import HolidayService
        result = HolidayService.create_custom_holiday(
            organization_id=organization_id,
            name=data['name'],
            date_observed=data['date_observed'],
            description=data.get('description'),
            affects_scheduling=data.get('affects_scheduling', True),
            created_by=current_user_id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Holiday created successfully',
                'holiday': result['master_holiday'],
                'org_holiday': result['org_holiday']
            }), 201
        else:
            return jsonify({'error': result['error']}), 400
        
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
            
            # Get date filters from query params or use defaults
            today = datetime.now()
            
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                    # Set end date to end of day
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                except ValueError:
                    start_date = today
                    end_date = today + timedelta(days=7)
            else:
                start_date = today
                end_date = today + timedelta(days=7)

            
            classes_cursor = mongo.db.classes.find({
                'organization_id': ObjectId(org_id),
                'scheduled_at': {'$gte': start_date, '$lte': end_date},
            }).sort('scheduled_at', 1)
            
            
            
            classes = []
            for class_data in classes_cursor:
                class_data['scheduled_at'] = class_data['scheduled_at'] + timedelta(hours=5, minutes=30)
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
            

            students = list(mongo.db.users.find({'organization_id': ObjectId(org_id), 'role': 'student'}).sort('name', 1))
            for student in students:
                student['_id'] = str(student['_id'])
                if 'organization_id' in student:
                    student['organization_id'] = str(student['organization_id'])
                student['organization_ids'] = [str(org_id) for org_id in student['organization_ids']]
                student['created_at'] = student['created_at'].strftime('%Y-%m-%d')
                if 'parent_id' in student:
                    student['parent_id'] = str(student['parent_id'])
                if 'subscription_ids' in student:
                    student['subscription_ids'] = [str(sid) for sid in student['subscription_ids']]

            print(students)

            return render_template('class_management.html',
                                 classes=classes,
                                 cancelled_classes=cancelled_classes,
                                 holidays=holidays,
                                 students=students,
                                 start_date=start_date.strftime('%Y-%m-%d'),
                                 end_date=end_date.strftime('%Y-%m-%d'),
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
        # try:
            org_id = session.get('organization_id')
            if not org_id:
                flash('Organization not found.', 'error')
                return redirect(url_for('web.dashboard'))
            
            # Get organization holidays using the new service
            current_year = datetime.now().year
            today = datetime.now()
            
            from app.services.holiday_service import HolidayService
            holidays = HolidayService.get_organization_holidays(
                organization_id=org_id,
                year=current_year,
                include_inactive=False
            )
            
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
            
            return render_template('holidays_management.html',
                                 holidays=holidays,
                                 centers=centers,
                                 current_year=current_year,
                                 today=today)
        
        # except Exception as e:
        #     current_app.logger.error(f"Error loading holidays management: {str(e)}")
        #     flash('Error loading holidays management page.', 'error')
        #     return redirect(url_for('web.dashboard'))
    
    return _holidays_management()

@class_cancellation_bp.route('/api/holidays/<org_holiday_id>/remove', methods=['DELETE'])
@jwt_or_session_required()
@require_role_hybrid(['org_admin', 'center_admin'])
def api_remove_holiday_from_organization(org_holiday_id):
    """Remove a holiday from organization"""
    try:
        # Import auth utilities
        from app.utils.auth import get_current_user_info
        user_info = get_current_user_info()
        
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
            
        organization_id = user_info.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Use the new holiday service
        from app.services.holiday_service import HolidayService
        result = HolidayService.remove_holiday_from_organization(
            organization_id=organization_id,
            org_holiday_id=org_holiday_id
        )
        
        if result['success']:
            return jsonify({'message': 'Holiday removed successfully', 'success': True}), 200
        else:
            return jsonify({'error': result['error']}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error removing holiday: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@class_cancellation_bp.route('/holidays/<holiday_id>/delete', methods=['DELETE'])
def delete_holiday(holiday_id):
    """Delete a holiday"""
    try:
        holiday = mongo.db.holidays.find_one({'_id': ObjectId(holiday_id)})
        if holiday.get('is_imported'):
            mongo.db.holidays.update_one({'_id': ObjectId(holiday_id)}, {'$set': {'is_imported': False}})
        else:
            mongo.db.holidays.delete_one({'_id': ObjectId(holiday_id)})

        return jsonify({'success': True, 'message': 'Holiday deleted successfully'}), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting holiday: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500 # TODO: add error message



@class_cancellation_bp.route('/api/holidays/indian/<int:year>', methods=['GET'])
def api_get_indian_holidays(year):
    # """Get Indian holidays for a specific year from database"""
    # try:
        # Get holidays from database (stored by the fetch script)

        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        print(start_date, end_date)
        start_of_year = datetime.combine(date(year, 1, 1), dt_time.min)
        end_of_year = datetime.combine(date(year, 12, 31), dt_time.max)
        print(start_of_year, end_of_year)

        holidays = list(mongo.db.holidays.find({
            'source': 'calendarific_api',
            'date_observed': {
                '$gte': start_of_year,
                '$lte': end_of_year
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
        
    # except Exception as e:
    #     current_app.logger.error(f"Error fetching Indian holidays: {str(e)}")
    #     return jsonify({'error': 'Internal server error'}), 500

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

@class_cancellation_bp.route('/generate-qr/<class_id>', methods=['POST'])
def generate_class_qr_code(class_id):
    """Generate QR code for a specific class"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = session.get('role')
        if user_role not in ['org_admin', 'center_admin', 'coach']:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        # Verify the class exists
        class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
        if not class_doc:
            return jsonify({'error': 'Class not found'}), 404
        
        # Import QR generation utilities from mobile_api
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        from mobile_api import generate_qr_token, QR_TOKEN_VALIDITY_MINUTES
        from datetime import timedelta
        import qrcode
        from io import BytesIO
        import base64
        
        # Create payload for QR code
        payload = {
            'class_id': class_id,
            'center_id': str(class_doc.get('center_id', '')),
            'type': 'class'
        }
        
        # Generate the QR token
        qr_token = generate_qr_token(payload)
        
        # Generate QR code image using Python qrcode library
        qr = qrcode.QRCode(
            version=1,  # Controls the size of the QR code
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_token)
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert image to base64 string for frontend
        img_buffer = BytesIO()
        qr_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Calculate expiry time
        valid_until = datetime.utcnow() + timedelta(minutes=QR_TOKEN_VALIDITY_MINUTES)
        
        return jsonify({
            'success': True,
            'qrCode': qr_token,
            'qrImageBase64': f"data:image/png;base64,{img_base64}",
            'qrString': qr_token,  # For direct display/printing
            'type': 'class',
            'className': class_doc.get('title', 'Unknown Class'),
            'validUntil': valid_until.isoformat(),
            'validityMinutes': QR_TOKEN_VALIDITY_MINUTES,
            'message': 'QR code generated successfully'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error generating QR code for class {class_id}: {str(e)}")
        return jsonify({'error': 'Failed to generate QR code'}), 500