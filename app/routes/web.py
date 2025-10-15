from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from bson import ObjectId
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
from app.extensions import mongo
from app.services.auth_service import AuthService
from app.models.user import User
from functools import wraps
from app.utils.auth import jwt_or_session_required, get_current_user_info
from app.services.holiday_service import HolidayService
from app.routes.class_cancellation import HolidaySchema
from app.services.whatsapp_service import WhatsAppService
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields, ValidationError
import traceback
from daily_class_creator import DailyClassCreator
import secrets
from app.models.activity_links import ActivityLink
from app.services.file_upload_service import FileUploadService
from app.helpers.app_helper import get_user_info_from_session_or_claims
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService



def get_class_info(class_id):
    """Get detailed information about a class"""
    class_doc = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
    if not class_doc:
        return None
    
    schedule = mongo.db.schedules.find_one({'_id': class_doc['schedule_id']})
    activity = mongo.db.activities.find_one({'_id': schedule['activity_id']})
    center = mongo.db.centers.find_one({'_id': schedule['center_id']})
    
    return {
        'activity_name': activity['name'],
        'schedule_time': schedule['time'].strftime('%I:%M %p'),
        'center_name': center['name']
    }

def serialize_for_json(data):
    """Convert MongoDB documents to JSON-serializable format"""
    if isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    elif isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif hasattr(value, 'isoformat'):  # datetime objects
                result[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                result[key] = serialize_for_json(value)
            else:
                result[key] = value
        return result
    elif isinstance(data, ObjectId):
        return str(data)
    elif hasattr(data, 'isoformat'):
        return data.isoformat()
    else:
        return data

# Create blueprint
web_bp = Blueprint('web', __name__)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('web.login'))
        
        # Handle organization_ids for multi-organization support
        if 'organization_id' not in session or session['organization_id'] is None:
            user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
            if user is None:
                return redirect(url_for('web.logout'))
            
            # Try to get organization_ids first (new field), then fallback to organization_id
            org_ids = user.get('organization_ids', [])
            if not org_ids and user.get('organization_id'):
                org_ids = [user['organization_id']]
            
            if org_ids:
                # Store all organization_ids in session
                session['organization_ids'] = [str(oid) for oid in org_ids]
                # Set active organization to first one
                session['organization_id'] = str(org_ids[0])
            else:
                # User has no organizations
                session['organization_ids'] = []
                session['organization_id'] = None
        
        print(session.get('organization_id'))
        return f(*args, **kwargs)
    return wrapper

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('web.login'))
            
            user_role = session.get('role')
            print(f"User role: {user_role}, roles: {roles}")
            if user_role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('web.dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@web_bp.route('/test-whatsapp', methods=['GET'])
def test_whatsapp():
    """Test WhatsApp endpoint"""
    whatsapp_service = WhatsAppService()
    whatsapp_service.send_message('+919945613932', 'Hello, this is a test message')
    return jsonify({'message': 'WhatsApp message sent'}), 200

@web_bp.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@web_bp.route('/login', methods=['GET'])
def login():
    """Login page - now shows phone verification form"""
    return render_template('login.html')

@web_bp.route('/send-verification', methods=['POST'])
def send_verification():
    """Send verification code to user's email"""
    try:
        phone_number = request.form.get('phone_number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Send verification code
        result, status_code = AuthService.send_verification_code(phone_number)
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Send verification error: {str(e)}")
        return jsonify({'error': 'Failed to send verification code'}), 500

@web_bp.route('/verify-code', methods=['POST'])
def verify_code():
    """Verify code and login user"""
    try:
        phone_number = request.form.get('phone_number')
        verification_code = request.form.get('verification_code')
        
        if not phone_number or not verification_code:
            return jsonify({'error': 'Phone number and verification code are required'}), 400
        
        # Verify code and login
        result, status_code = AuthService.verify_code_and_login(phone_number, verification_code)
        
        if status_code == 200:
            user_data = result['user']
            # Set session
            session['user_id'] = str(user_data['_id'])
            session['email'] = user_data.get('email', '')
            session['first_name'] = user_data.get('first_name', 'User')
            session['last_name'] = user_data.get('last_name', '')
            session['role'] = user_data.get('role', 'student')
            session['phone_number'] = user_data.get('phone_number', '')
            
            # Handle multiple organizations - store all organization_ids and set active one
            organization_ids = user_data.get('organization_ids', [])
            if not organization_ids and user_data.get('organization_id'):
                # Backward compatibility: if only organization_id exists, use it
                organization_ids = [str(user_data['organization_id'])]
            
            session['organization_ids'] = [str(oid) for oid in organization_ids] if organization_ids else []
            
            # Set active organization (default to first one)
            if organization_ids:
                session['organization_id'] = str(organization_ids[0])
            elif user_data.get('organization_id'):
                session['organization_id'] = str(user_data['organization_id'])
            
            # Return success response for AJAX
            return jsonify({
                'message': 'Login successful',
                'redirect': url_for('web.dashboard')
            }), 200
        else:
            return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Verify code error: {str(e)}")
        return jsonify({'error': 'Failed to verify code'}), 500

# Legacy email/password login route (for backward compatibility)
@web_bp.route('/legacy-login', methods=['POST'])
def legacy_login():
    """Legacy email/password login (kept for backward compatibility)"""
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Please provide both email and password.', 'error')
        return render_template('login.html')
    
    try:
        # Authenticate user
        user = AuthService.authenticate_user(email, password)
        if user:
            # Set session
            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['first_name'] = user.get('first_name', 'User')
            session['last_name'] = user.get('last_name', '')
            session['role'] = user.get('role', 'student')
            
            # Handle multiple organizations - store all organization_ids and set active one
            organization_ids = user.get('organization_ids', [])
            if not organization_ids and user.get('organization_id'):
                # Backward compatibility: if only organization_id exists, use it
                organization_ids = [str(user['organization_id'])]
            
            session['organization_ids'] = [str(oid) for oid in organization_ids] if organization_ids else []
            
            # Set active organization (default to first one)
            if organization_ids:
                session['organization_id'] = str(organization_ids[0])
            elif user.get('organization_id'):
                session['organization_id'] = str(user['organization_id'])
            
            flash(f'Welcome back, {user.get("first_name", "User")}!', 'success')
            return redirect(url_for('web.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        flash('An error occurred during login. Please try again.', 'error')

    return render_template('login.html')

@web_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role', 'student')
        
        # Validation
        if not all([email, password, confirm_password, first_name, last_name]):
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        try:
            # Create user
            user_data = {
                'email': email,
                'password': password,
                'first_name': first_name,
                'last_name': last_name,
                'role': role
            }
            
            user_id = AuthService.create_user(user_data)
            if user_id:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('web.login'))
            else:
                flash('Registration failed. Email may already exist.', 'error')
        except Exception as e:
            current_app.logger.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('register.html')

@web_bp.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('web.login'))

@web_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard for all user roles"""
    try:
        user_role = session.get('role')
        user_name = session.get('first_name', 'User')
        current_user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        org_id = ObjectId(session.get('organization_id'))
        import time
        # Get today's date
        today = datetime.now()
        start_of_day = datetime.combine(today.date(), datetime.min.time())
        end_of_day = datetime.combine(today.date(), datetime.max.time())
        start_of_month = datetime(today.year, today.month, 1)
        
        # Initialize stats
        stats = {}
        weekly_schedule = []
        todays_classes = []
        updates = []
        attendance_data = []
        revenue_data = []

        if user_role == 'super_admin':
            # Super admin stats
            total_orgs = mongo.db.organizations.count_documents({})
            total_users = mongo.db.users.count_documents({})
            active_orgs = mongo.db.organizations.count_documents({'is_active': True})
            
            stats = {
                'today_classes': mongo.db.classes.count_documents({'date': {'$gte': start_of_day, '$lte': end_of_day}}),
                'attendance_rate': 85,  # Calculate from actual data
                'no_shows': mongo.db.attendance.count_documents({'date': {'$gte': start_of_day}, 'status': 'absent'}),
                'monthly_revenue': sum(p.get('amount', 0) for p in mongo.db.payments.find({'date': {'$gte': start_of_month}}))
            }
            
            # Get recent updates
            updates = list(mongo.db.announcements.find().sort('created_at', -1).limit(5))
        
        elif user_role in ['org_admin', 'coach_admin']:
            # Get today's classes
            todays_classes = list(mongo.db.classes.find({
                'organization_id': org_id,
                'scheduled_at': {'$gte': start_of_day, '$lte': end_of_day}
            }))
            
            # Get next upcoming class
            next_class_data = mongo.db.classes.find_one({
                'organization_id': org_id,
                'scheduled_at': {'$gt': datetime.now()},
                'status': {'$ne': 'cancelled'}
            }, sort=[('scheduled_at', 1)])

            if next_class_data:
                # Get coach details
                coach = mongo.db.users.find_one({'_id': next_class_data.get('coach_id')})
                coach_name = f"{coach.get('first_name', '')} {coach.get('last_name', '')}" if coach else 'Unassigned'
                
                # Get center details
                center = mongo.db.centers.find_one({'_id': next_class_data.get('center_id')})
                center_name = center.get('name', 'No location') if center else 'No location'
                
                # Get enrollment count
                total_students = mongo.db.class_enrollments.count_documents({
                    'class_id': next_class_data['_id']
                })
                
                # Get RSVP count
                rsvp_count = mongo.db.class_enrollments.count_documents({
                    'class_id': next_class_data['_id'],
                    'rsvp_status': 'confirmed'
                })
                
                next_class = {
                    'title': next_class_data.get('title', 'Untitled Class'),
                    'time': next_class_data['scheduled_at'].strftime('%I:%M %p'),
                    'total_students': total_students,
                    'rsvp_count': rsvp_count,
                    'coach_name': coach_name,
                    'center': center_name
                }
            else:
                next_class = None
            
            # Calculate attendance rate
            total_attendance = mongo.db.attendance.count_documents({'organization_id': org_id})
            present_attendance = mongo.db.attendance.count_documents({'organization_id': org_id, 'status': 'present'})
            attendance_rate = (present_attendance / total_attendance * 100) if total_attendance > 0 else 0
            
            # Get monthly revenue
            monthly_revenue = sum(p.get('amount', 0) for p in mongo.db.payments.find({
                'organization_id': org_id,
                'date': {'$gte': start_of_month}
            }))
            
            stats = {
                'today_classes': len(todays_classes),
                'attendance_rate': round(attendance_rate, 1),
                'no_shows': mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'date': {'$gte': start_of_day},
                    'status': 'absent'
                }),
                'monthly_revenue': monthly_revenue
            }
            
            # Get weekly schedule
            # Get current week's start and end
            today = datetime.now()
            week_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            weekly_schedule = list(mongo.db.classes.find({
                'organization_id': org_id,
                'scheduled_at': {'$gte': week_start, '$lte': week_end}
            }).sort('scheduled_at', 1))
            
            
            # Format classes for display
            for class_ in todays_classes:
                print(class_)
                checked_in = mongo.db.attendance.count_documents({
                    'class_id': class_['_id'],
                    'status': 'present'
                })
                total_students = mongo.db.class_enrollments.count_documents({
                    'class_id': class_['_id']
                })
                class_['checked_in'] = checked_in
                class_['total'] = total_students
            
            # Get recent updates
            updates = list(mongo.db.announcements.find({
                'organization_id': org_id
            }).sort('created_at', -1).limit(5))
            
            # Get attendance trend data (last 7 days)
            attendance_labels = []
            attendance_data = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                total = mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'scheduled_at': {'$gte': datetime.combine(date.date(), datetime.min.time()),
                            '$lte': datetime.combine(date.date(), datetime.max.time())}
                })
                present = mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'scheduled_at': {'$gte': datetime.combine(date.date(), datetime.min.time()),
                            '$lte': datetime.combine(date.date(), datetime.max.time())},
                    'status': 'present'
                })
                rate = (present / total * 100) if total > 0 else 0
                attendance_labels.append(date.strftime('%d %b'))
                attendance_data.append(round(rate, 1))
            
            # Get revenue trend data (last 6 months)
            revenue_labels = []
            revenue_data = []
            for i in range(5, -1, -1):
                month_date = today - relativedelta(months=i)
                month_start = datetime(month_date.year, month_date.month, 1)
                month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
                revenue = sum(p.get('amount', 0) for p in mongo.db.payments.find({
                    'organization_id': org_id,
                    'date': {'$gte': month_start, '$lte': month_end}
                }))
                revenue_labels.append(month_date.strftime('%b %Y'))
                revenue_data.append(revenue)
        
        elif user_role == 'coach':
            # Get today's classes for this coach
            todays_classes = list(mongo.db.classes.find({
                'organization_id': org_id,
                'coach_id': ObjectId(session.get('user_id')),
                'scheduled_at': {'$gte': start_of_day, '$lte': end_of_day}
            }))
            
            # Calculate attendance rate for coach's classes
            total_attendance = mongo.db.attendance.count_documents({
                'organization_id': org_id,
                'coach_id': ObjectId(session.get('user_id'))
            })
            present_attendance = mongo.db.attendance.count_documents({
                'organization_id': org_id,
                'coach_id': ObjectId(session.get('user_id')),
                'status': 'present'
            })
            attendance_rate = (present_attendance / total_attendance * 100) if total_attendance > 0 else 0
            
            stats = {
                'today_classes': len(todays_classes),
                'attendance_rate': round(attendance_rate, 1),
                'no_shows': mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'coach_id': ObjectId(session.get('user_id')),
                    'date': {'$gte': start_of_day},
                    'status': 'absent'
                }),
                'monthly_revenue': 0  # Coaches don't see revenue
            }
            
            # Get weekly schedule for this coach
            # Get current week's start and end
            today = datetime.now()
            week_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            weekly_schedule = list(mongo.db.classes.find({
                'organization_id': org_id,
                'coach_id': ObjectId(session.get('user_id')),
                'scheduled_at': {'$gte': week_start, '$lte': week_end}
            }).sort('scheduled_at', 1))
            
            # Format classes for display
            for class_ in todays_classes:
                checked_in = mongo.db.attendance.count_documents({
                    'class_id': class_['_id'],
                    'status': 'present'
                })
                total_students = mongo.db.class_enrollments.count_documents({
                    'class_id': class_['_id']
                })
                class_['checked_in'] = checked_in
                class_['total'] = total_students
            
            # Get recent updates
            updates = list(mongo.db.announcements.find({
                'organization_id': org_id
            }).sort('created_at', -1).limit(5))
            
            # Get attendance trend data (last 7 days)
            attendance_labels = []
            attendance_data = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                total = mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'coach_id': ObjectId(session.get('user_id')),
                    'scheduled_at': {'$gte': datetime.combine(date.date(), datetime.min.time()),
                            '$lte': datetime.combine(date.date(), datetime.max.time())}
                })
                present = mongo.db.attendance.count_documents({
                    'organization_id': org_id,
                    'coach_id': ObjectId(session.get('user_id')),
                    'scheduled_at': {'$gte': datetime.combine(date.date(), datetime.min.time()),
                            '$lte': datetime.combine(date.date(), datetime.max.time())},
                    'status': 'present'
                })
                rate = (present / total * 100) if total > 0 else 0
                attendance_labels.append(date.strftime('%d %b'))
                attendance_data.append(round(rate, 1))
            
            # Coaches don't see revenue data
            revenue_labels = []
            revenue_data = []

        # Format weekly schedule for display
        # Get the current week's start (Monday)
        today = datetime.now()
        current_weekday = today.weekday()  # Monday is 0, Sunday is 6
        week_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        formatted_schedule = {'days': []}
        
        # Create entries for each day of the week
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_classes = [c for c in weekly_schedule if c['scheduled_at'].date() == current_date.date()]
            
            day_data = {
                'name': current_date.strftime('%A'),  # Full day name
                'date': current_date.strftime('%b %d'),  # Month and day
                'is_today': current_date.date() == today.date(),
                'class_count': len(day_classes),
                'classes': []
            }
            
            # Format classes for this day
            for class_ in day_classes:
                day_data['classes'].append({
                    'title': class_.get('title', 'Untitled Class'),
                    'time': class_['scheduled_at'].strftime('%I:%M %p')
                })
            
            formatted_schedule['days'].append(day_data)
        
        # Replace the weekly_schedule with our formatted version
        weekly_schedule = formatted_schedule

        # Format updates for display
        for update in updates:
            update['time'] = update['created_at'].strftime('%d %b, %I:%M %p')

        return render_template('dashboard.html',
            stats=stats,
            weekly_schedule=weekly_schedule,
            todays_classes=todays_classes,
            updates=updates,
            attendance_labels=attendance_labels,
            attendance_data=attendance_data,
            revenue_labels=revenue_labels,
            revenue_data=revenue_data,
            next_class=next_class
        )

       
    except Exception as e:
        current_app.logger.error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html', stats={})

def _get_pagination_range(current_page, total_pages, window=5):
    """Generate a smart pagination range with ellipsis support"""
    if total_pages <= window:
        return list(range(1, total_pages + 1))
    
    # Calculate the range around current page
    half_window = window // 2
    start = max(1, current_page - half_window)
    end = min(total_pages, current_page + half_window)
    
    # Adjust if we're near the beginning or end
    if start <= 3:
        return list(range(1, min(window + 1, total_pages + 1)))
    elif end >= total_pages - 2:
        return list(range(max(1, total_pages - window + 1), total_pages + 1))
    else:
        return list(range(start, end + 1))

@web_bp.route('/users')
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def users():
    """Users management page"""
    try:
        user_role = session.get('role')
        # Build query based on user role
        query = {}
        if user_role in ['org_admin', 'coach_admin']:
            org_id = session.get('organization_id')
            if org_id:
                # Check if organization_id is in user's organization_ids array (multi-org support)
                query['organization_ids'] = ObjectId(org_id)
        
        # Get search and filter parameters with validation
        search = request.args.get('search', '').strip()[:100]  # Limit search length
        role_filter = request.args.get('role', '')
        status_filter = request.args.get('status', '')
        org_filter = request.args.get('organization', '')
        sort_by = request.args.get('sort', 'name')
        sort_order = request.args.get('order', 'asc')
        
        # Pagination parameters with validation
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(5, int(request.args.get('per_page', 20))))  # Allow customizable page size
        except (ValueError, TypeError):
            page = 1
            per_page = 20
        
        # Handle search with proper field name support
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'phone_number': {'$regex': search, '$options': 'i'}}
            ]
        
        if role_filter:
            query['role'] = role_filter

        if status_filter:
            if status_filter == 'active':
                query['is_active'] = True
            elif status_filter == 'inactive':
                query['is_active'] = False
        
        # Organization filter (only for super admin)
        if org_filter and user_role == 'super_admin':
            query['organization_ids'] = ObjectId(org_filter)
        else:
            query['organization_ids'] = ObjectId(session.get('organization_id'))
        
        # Handle sorting
        sort_direction = 1 if sort_order == 'asc' else -1
        sort_field_map = {
            'name': 'name',
            'email': 'email',
            'phone': 'phone_number',
            'role': 'role',
            'status': 'is_active',
            'last_login': 'last_login',
            'created_at': 'created_at'
        }
        
        mongo_sort_field = sort_field_map.get(sort_by, 'created_at')
        
        # Get total count for pagination
        total_count = mongo.db.users.count_documents(query)
        
        # Calculate pagination with bounds checking
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = min(page, total_pages)  # Ensure page doesn't exceed total pages
        skip = (page - 1) * per_page
        
        # Get users with pagination and sorting
        print(query)
        users_cursor = mongo.db.users.find(query).sort(mongo_sort_field, sort_direction).skip(skip).limit(per_page)
        users = list(users_cursor)
        
        # Create comprehensive pagination info
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None,
            'start_index': skip + 1 if total_count > 0 else 0,
            'end_index': min(skip + per_page, total_count),
            'iter_pages': _get_pagination_range(page, total_pages),
            'per_page_options': [10, 20, 50, 100],
            'showing_all': total_count <= per_page
        }
        
        # Convert ObjectId to string for template
        for user in users:
            user['_id'] = str(user['_id'])
            if user.get('organization_id'):
                user['organization_id'] = str(user['organization_id'])
        
        # Get organizations list for super admin filter dropdown
        organizations = []
        if user_role == 'super_admin':
            orgs_cursor = mongo.db.organizations.find({}, {'name': 1}).sort('name', 1)
            organizations = list(orgs_cursor)
            for org in organizations:
                org['_id'] = str(org['_id'])

        subscriptions = mongo.db.subscriptions.find({'organization_id': ObjectId(session.get('organization_id'))})
        subscriptions = list(subscriptions)
        for subscription in subscriptions:
            subscription['_id'] = str(subscription['_id'])
            if subscription.get('organization_id'):
                subscription['organization_id'] = str(subscription['organization_id'])

        
        return render_template('users.html', users=users, pagination=pagination, organizations=organizations, subscriptions=subscriptions)
    
    except Exception as e:
        current_app.logger.error(f"Users page error: {str(e)}")
        flash('Error loading users.', 'error')
        return render_template('users.html', users=[], organizations=[])
    
@web_bp.route('/api/dashboard/stats/<user_id>', methods=['GET'])
@login_required
def user_stats(user_id):
    print("Getting user stats for user: ", user_id)
    """User stats page"""
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        flash('User not found.', 'error')
        print("User not found")
        return jsonify({'error': 'User not found'}), 404
    if user['role'] == 'coach':
        print("Getting classes for cocah")
        classes_today = mongo.db.classes.count_documents({'coach_id': ObjectId(user_id), 'scheduled_at': {'$gte': datetime.now()}})
        from datetime import datetime, timedelta
        start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())
        end_of_week = start_of_week + timedelta(days=7) 
        this_weeks_classes = mongo.db.classes.count_documents({'coach_id': ObjectId(user_id), 'scheduled_at': {'$gte': start_of_week, '$lte': end_of_week}})
        print("Classes today: ", classes_today)
        print("Classes this week: ", this_weeks_classes)
        return jsonify({'todaysClasses': classes_today, 'thisWeeksClasses': this_weeks_classes})
    

@web_bp.route('/users/<user_id>')
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def user_detail(user_id):
    """User detail page"""
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('web.users'))
        
        # Check permissions
        current_role = session.get('role')
        if current_role in ['org_admin', 'coach_admin']:
            current_org_id = session.get('organization_id')
            if str(user.get('organization_id')) != current_org_id:
                flash('You do not have permission to view this user.', 'error')
                return redirect(url_for('web.users'))
        
        # Convert ObjectId to string
        user['_id'] = str(user['_id'])
        if user.get('organization_id'):
            user['organization_id'] = str(user['organization_id'])
        
        return render_template('user_detail.html', user=user)
    
    except Exception as e:
        current_app.logger.error(f"User detail error: {str(e)}")
        flash('Error loading user details.', 'error')
        return redirect(url_for('web.users'))

@web_bp.route('/user-dashboard')
@login_required
def user_dashboard():
    """User dashboard page with classes, payments, and child profiles"""
    try:
        user_id = request.args.get('user_id')
        organization_id = request.args.get('organization_id')
        
        # Get user data
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        print(user_data)
        if not user_data:
            flash('User not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Convert ObjectIds to strings
        user_data['_id'] = str(user_data['_id'])
        if user_data.get('organization_id'):
            user_data['organization_id'] = str(user_data['organization_id'])
        
        # Get organization data
        organization_data = None
        if organization_id:
            organization_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
            if organization_data:
                organization_data['_id'] = str(organization_data['_id'])
        
        return render_template('user_dashboard.html', user=user_data, organization=organization_data)
    
    except Exception as e:
        current_app.logger.error(f"User dashboard error: {str(e)}")
        flash('Error loading dashboard.', 'error')
        return redirect(url_for('web.dashboard'))

@web_bp.route('/user-dashboard/<user_id>')
@login_required
def user_dashboard_by_id(user_id):
    """User dashboard page for admins to view any user"""
    try:
        current_user_id = session.get('user_id')
        current_role = session.get('role')
        organization_id = session.get('organization_id')
        
        # Check permissions
        if current_role not in ['super_admin', 'org_admin', 'center_admin', 'coach'] and str(current_user_id) != str(user_id):
            flash('You do not have permission to view this dashboard.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Get user data
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user_data:
            flash('User not found.', 'error')
            return redirect(url_for('web.users'))
        
        # Check organization permissions
        if current_role in ['org_admin', 'center_admin', 'coach']:
            if str(user_data.get('organization_id')) != organization_id:
                flash('You do not have permission to view this user.', 'error')
                return redirect(url_for('web.users'))
        
        # Convert ObjectIds to strings
        user_data['_id'] = str(user_data['_id'])
        if user_data.get('organization_id'):
            user_data['organization_id'] = str(user_data['organization_id'])
        
        # Get organization data
        organization_data = None
        if user_data.get('organization_id'):
            organization_data = mongo.db.organizations.find_one({'_id': ObjectId(user_data['organization_id'])})
            if organization_data:
                organization_data['_id'] = str(organization_data['_id'])
        
        return render_template('user_dashboard.html', user=user_data, organization=organization_data)
    
    except Exception as e:
        current_app.logger.error(f"User dashboard error: {str(e)}")
        flash('Error loading dashboard.', 'error')
        return redirect(url_for('web.users'))

@web_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    try:
        user_id = session.get('user_id')
        organization_id = session.get('organization_id')
        
        if not user_id:
            flash('Please log in to view your profile.', 'error')
            return redirect(url_for('auth.login'))
        
        print(user_id)
        print(organization_id)
        # Get user data
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        print(user_data)
        if not user_data:
            flash('User not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Get organization data if user belongs to one
        organization_data = None
        if organization_id:
            organization_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
        
        # Convert ObjectId to string for template
        if user_data and '_id' in user_data:
            user_data['_id'] = str(user_data['_id'])
        if organization_data and '_id' in organization_data:
            organization_data['_id'] = str(organization_data['_id'])
        
        return render_template('profile.html', 
                             user=user_data, 
                             organization=organization_data)
    
    except Exception as e:
        current_app.logger.error(f"Error loading profile: {str(e)}")
        flash('Error loading profile. Please try again.', 'error')
        return redirect(url_for('web.dashboard'))

@web_bp.route('/equipment')
@login_required
def equipment():
    """Equipment management page"""
    try:
        user_role = session.get('role')
        
        # Build query based on user role
        query = {}
        if user_role != 'super_admin':
            org_id = session.get('organization_id')
            if org_id:
                query['organization_id'] = ObjectId(org_id)
        
        # Get search parameters
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        status = request.args.get('status', '')
        
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'brand': {'$regex': search, '$options': 'i'}},
                {'model': {'$regex': search, '$options': 'i'}}
            ]
        
        if category:
            query['category'] = category
        
        if status:
            query['status'] = status
        
        # Mock equipment data
        equipment_list = [
            {
                '_id': '1',
                'name': 'Football',
                'category': 'Sports',
                'brand': 'Nike',
                'model': 'Pro',
                'quantity': 15,
                'available': 12,
                'status': 'Available',
                'condition': 'Good',
                'last_maintenance': '2024-01-15'
            },
            {
                '_id': '2',
                'name': 'Basketball',
                'category': 'Sports',
                'brand': 'Spalding',
                'model': 'NBA Official',
                'quantity': 8,
                'available': 5,
                'status': 'Available',
                'condition': 'Excellent',
                'last_maintenance': '2024-01-20'
            }
        ]
        
        return render_template('equipment.html', equipment=equipment_list)
    
    except Exception as e:
        current_app.logger.error(f"Equipment page error: {str(e)}")
        flash('Error loading equipment.', 'error')
        return render_template('equipment.html', equipment=[])

@web_bp.route('/classes')
@login_required
def classes():
    """Classes management page"""
    try:
        user_role = session.get('role')
        user_id = session.get('user_id')
        
        # Build query based on user role
        query = {}
        if user_role == 'student':
            # Students see only their enrolled classes
            query['students'] = ObjectId(user_id)
        elif user_role == 'coach':
            # Coaches see only their classes
            query['coach_id'] = ObjectId(user_id)
        elif user_role in ['org_admin', 'coach_admin']:
            # Org admins see all classes in their organization
            org_id = session.get('organization_id')
            if org_id:
                query['organization_id'] = ObjectId(org_id)
        
        # Get filter parameters
        sport = request.args.get('sport', '')
        status = request.args.get('status', '')
        
        if sport:
            query['sport'] = sport
        
        if status:
            query['status'] = status
        
        # Mock classes data
        classes_list = [
            {
                '_id': '1',
                'name': 'Football Training - Beginners',
                'sport': 'Football',
                'coach': 'John Smith',
                'schedule': 'Mon, Wed, Fri 4:00 PM',
                'duration': '1.5 hours',
                'students_enrolled': 15,
                'max_capacity': 20,
                'status': 'Active',
                'level': 'Beginner',
                'price': '$80/month'
            },
            {
                '_id': '2',
                'name': 'Basketball Advanced',
                'sport': 'Basketball',
                'coach': 'Mike Johnson',
                'schedule': 'Tue, Thu 6:00 PM',
                'duration': '2 hours',
                'students_enrolled': 12,
                'max_capacity': 15,
                'status': 'Active',
                'level': 'Advanced',
                'price': '$100/month'
            }
        ]
        
        return render_template('classes.html', classes=classes_list)
    
    except Exception as e:
        current_app.logger.error(f"Classes page error: {str(e)}")
        flash('Error loading classes.', 'error')
        return render_template('classes.html', classes=[])

import razorpay
from os import environ

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(environ.get('RAZORPAY_API_KEY'), environ.get('RAZORPAY_API_SECRET'))
)

@web_bp.route('/payment/<token>', methods=['GET'])
def process_payment(token):
    try:
        # Get payment link details
        payment_link = mongo.db.payment_links.find_one({
            'token': token,
            'status': 'pending',
            'expires_at': {'$gt': datetime.utcnow()}
        })
        
        if not payment_link:
            flash('Invalid or expired payment link', 'error')
            return redirect(url_for('web.dashboard'))
            
        # Get user and subscription details
        user = mongo.db.users.find_one({'_id': payment_link['user_id']})
        subscription = mongo.db.subscriptions.find_one({'_id': payment_link['subscription_id']})
        
        # Create Razorpay order
        order_amount = subscription['price'] * 100  # Convert to paise
        order_currency = 'INR'
        
        order_data = {
            'amount': order_amount,
            'currency': order_currency,
            'payment_capture': 1,  # Auto-capture payment
            'notes': {
                'payment_link_id': str(payment_link['_id']),
                'user_id': str(user['_id']),
                'subscription_id': str(subscription['_id'])
            }
        }
        
        # Create order
        order = razorpay_client.order.create(data=order_data)
        
        # Update payment link with order details
        mongo.db.payment_links.update_one(
            {'_id': payment_link['_id']},
            {
                '$set': {
                    'razorpay_order_id': order['id'],
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return render_template(
            'payment.html',
            payment_link=payment_link,
            user=user,
            subscription=subscription,
            razorpay_order=order,
            razorpay_key=environ.get('RAZORPAY_API_KEY')
        )
        
    except Exception as e:
        current_app.logger.error(f"Error processing payment: {str(e)}")
        flash('Error processing payment', 'error')
        return redirect(url_for('web.dashboard'))

@web_bp.route('/payment/verify', methods=['POST'])
def verify_payment():
    try:
        # Get payment verification data
        payment_id = request.form.get('razorpay_payment_id')
        order_id = request.form.get('razorpay_order_id')
        signature = request.form.get('razorpay_signature')
        
        # Verify signature
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            })
        except Exception as e:
            current_app.logger.error(f"Payment signature verification failed: {str(e)}")
            return jsonify({'error': 'Payment verification failed'}), 400
        
        # Get payment link from order ID
        payment_link = mongo.db.payment_links.find_one({'razorpay_order_id': order_id})
        if not payment_link:
            return jsonify({'error': 'Payment link not found'}), 404
            
        # Update payment link status
        mongo.db.payment_links.update_one(
            {'_id': payment_link['_id']},
            {
                '$set': {
                    'status': 'completed',
                    'paid_at': datetime.utcnow(),
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                }
            }
        )
        
        # Update user's subscription
        mongo.db.users.update_one(
            {'_id': payment_link['user_id']},
            {
                '$set': {
                    'subscription_ids': [payment_link['subscription_id']],
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return jsonify({'success': True, 'redirect_url': url_for('web.dashboard')})
        
    except Exception as e:
        current_app.logger.error(f"Error verifying payment: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    try:
        # Verify webhook signature
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        webhook_secret = environ.get('RAZORPAY_WEBHOOK_SECRET')
        
        razorpay_client.utility.verify_webhook_signature(
            request.data.decode(),
            webhook_signature,
            webhook_secret
        )
        
        # Process webhook event
        event_data = request.json
        event_type = event_data.get('event')
        
        if event_type == 'payment.captured':
            payment_id = event_data['payload']['payment']['entity']['id']
            order_id = event_data['payload']['payment']['entity']['order_id']
            
            # Update payment status
            payment_link = mongo.db.payment_links.find_one({'razorpay_order_id': order_id})
            if payment_link and payment_link['status'] != 'completed':
                # Update payment link status
                mongo.db.payment_links.update_one(
                    {'_id': payment_link['_id']},
                    {
                        '$set': {
                            'status': 'completed',
                            'paid_at': datetime.utcnow(),
                            'razorpay_payment_id': payment_id
                        }
                    }
                )
                
                # Update user's subscription
                mongo.db.users.update_one(
                    {'_id': payment_link['user_id']},
                    {
                        '$set': {
                            'subscription_ids': [payment_link['subscription_id']],
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/generate-payment-link', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def generate_payment_link():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        subscription_id = data.get('subscription_id')
        
        if not all([user_id, subscription_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Get user and subscription details
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        subscription = mongo.db.subscriptions.find_one({'_id': ObjectId(subscription_id)})
        
        if not user or not subscription:
            return jsonify({'error': 'Invalid user or subscription'}), 404
            
        # Generate a unique token for the payment link
        token = secrets.token_urlsafe(32)
        
        # Store payment link details
        payment_link = {
            'token': token,
            'user_id': ObjectId(user_id),
            'subscription_id': ObjectId(subscription_id),
            'amount': subscription['price'],
            'status': 'pending',
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'created_at': datetime.utcnow(),
            'created_by': ObjectId(session['user_id'])
        }
        
        result = mongo.db.payment_links.insert_one(payment_link)
        
        if not result.inserted_id:
            return jsonify({'error': 'Failed to generate payment link'}), 500
            
        # Generate the actual payment URL
        payment_url = url_for('web.process_payment', token=token, _external=True)
        
        return jsonify({
            'payment_link': payment_url,
            'expires_at': payment_link['expires_at'].isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error generating payment link: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/users/<user_id>/subscription', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def update_user_subscription(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        subscription_id = data.get('subscription_id')
        if not subscription_id:
            return jsonify({'error': 'Subscription ID is required'}), 400
            
        # Convert IDs to ObjectId
        user_id = ObjectId(user_id)
        subscription_id = ObjectId(subscription_id)
        
        # Get user and subscription
        user = mongo.db.users.find_one({'_id': user_id})
        subscription = mongo.db.subscriptions.find_one({'_id': subscription_id})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
            
        # Update user's subscription
        result = mongo.db.users.update_one(
            {'_id': user_id},
            {
                '$set': {
                    'subscription_ids': [subscription_id],
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({'message': 'Subscription updated successfully'}), 200
        else:
            return jsonify({'error': 'Failed to update subscription'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@web_bp.route('/create_subscription', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def create_subscription():
    try:
        # Get form data
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        cycle_type = request.form.get('cycle_type')
        
        # Validate required fields
        if not all([name, price, cycle_type]):
            flash('Name and price are required', 'error')
            return redirect(url_for('web.payments'))
        
        # Convert price to integer
        try:
            price = int(price)
            if price < 0:
                raise ValueError("Price cannot be negative")
        except ValueError:
            flash('Invalid price value', 'error')
            return redirect(url_for('web.payments'))
        
        # Get organization ID from session
        organization_id = session.get('organization_id')
        
        # Create subscription
        from app.models.subscription import Subscription
        subscription = Subscription.create(
            name=name,
            price=price,
            description=description,
            cycle_type=cycle_type,
            organization_id=organization_id,
        )
        
        if subscription:
            flash('Subscription plan created successfully', 'success')
        else:
            flash('Failed to create subscription plan', 'error')
            
    except Exception as e:
        flash(f'Error creating subscription: {str(e)}', 'error')
    
    return redirect(url_for('web.payments'))

@web_bp.route('/api/subscriptions/<subscription_id>/<action>', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def toggle_subscription(subscription_id, action, cycle_type):
    try:
        from app.models.subscription import Subscription
        
        if action not in ['activate', 'deactivate']:
            return jsonify({'error': 'Invalid action'}), 400
        
        active_status = action == 'activate'
        success = Subscription.toggle_status(subscription_id, active_status, cycle_type)
        
        if success:
            return jsonify({'message': f'Subscription {action}d successfully'}), 200
        else:
            return jsonify({'error': 'Failed to update subscription status'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@web_bp.route('/payments')
@login_required
def payments():
    """Payment management page - shows users with billing dates and subscription plans"""
    try:
        user_role = session.get('role')
        user_id = session.get('user_id')
        organization_id = session.get('organization_id')
        
        # Get subscriptions if user is org_admin or coach_admin
        subscriptions = []
        if user_role in ['org_admin', 'coach_admin']:
            from app.models.subscription import Subscription
            subscriptions = Subscription.get_all(organization_id)
        org_id = session.get('organization_id')
        
        # Students redirect to their own payments
        if user_role == 'student':
            return redirect(url_for('web.user_payments', user_id=user_id))
        
        # For admins and coaches, show users with billing dates
        if user_role in ['org_admin', 'coach_admin'] and org_id:
            # Get users with billing_date in the organization
            users_query = {
                'organization_id': ObjectId(org_id),
                'role': 'student',
                'billing_start_date': {'$exists': True, '$ne': None}
            }
            
            # Get search filter
            search = request.args.get('search', '').strip()
            if search:
                users_query['$or'] = [
                    {'name': {'$regex': search, '$options': 'i'}},
                    {'email': {'$regex': search, '$options': 'i'}},
                    {'phone_number': {'$regex': search, '$options': 'i'}}
                ]
            
            current_app.logger.info(f"Users query: {users_query}")
            users = list(mongo.db.users.find(users_query).sort('name', 1))
            current_app.logger.info(f"Found {len(users)} users with search: '{search}'")
            
            # Get payment summary for each user
            for user in users:
                user['_id'] = str(user['_id'])
                
                # Get payment statistics for this user
                payment_stats = mongo.db.payments.aggregate([
                    {
                        '$match': {
                            'student_id': ObjectId(user['_id']),
                            'organization_id': ObjectId(org_id)
                        }
                    },
                    {
                        '$group': {
                            '_id': '$status',
                            'count': {'$sum': 1},
                            'total_amount': {'$sum': '$amount'}
                        }
                    }
                ])
                
                stats = {stat['_id']: {'count': stat['count'], 'amount': stat['total_amount']} 
                        for stat in payment_stats}
                
                user['payment_stats'] = {
                    'total_payments': sum(s['count'] for s in stats.values()),
                    'total_amount': sum(s['amount'] for s in stats.values()),
                    'paid_count': stats.get('paid', {}).get('count', 0),
                    'paid_amount': stats.get('paid', {}).get('amount', 0),
                    'pending_count': stats.get('pending', {}).get('count', 0),
                    'pending_amount': stats.get('pending', {}).get('amount', 0),
                    'overdue_count': stats.get('overdue', {}).get('count', 0),
                    'overdue_amount': stats.get('overdue', {}).get('amount', 0)
                }
                
                # Get next billing date
                if user.get('billing_date'):
                    from datetime import datetime, timedelta
                    today = datetime.now().date()
                    billing_day = user['billing_date']
                    
                    # Calculate next billing date
                    current_month_billing = today.replace(day=billing_day)
                    if current_month_billing <= today:
                        # Next month
                        if today.month == 12:
                            next_billing = current_month_billing.replace(year=today.year + 1, month=1)
                        else:
                            next_billing = current_month_billing.replace(month=today.month + 1)
                    else:
                        next_billing = current_month_billing
                    
                    user['next_billing_date'] = next_billing
                    user['days_until_billing'] = (next_billing - today).days
            
            return render_template('payments_new.html', users=users, search=search, subscriptions=subscriptions)
        
        else:
            flash('Access denied.', 'error')
            return redirect(url_for('web.dashboard'))
    
    except Exception as e:
        current_app.logger.error(f"Payments page error: {str(e)}")
        flash('Error loading payment users.', 'error')
        return render_template('payments_new.html', users=[])

@web_bp.route('/payments/user/<user_id>')
@login_required
def user_payments(user_id):
    """Show all payments for a specific user"""
    try:
        user_role = session.get('role')
        current_user_id = session.get('user_id')
        org_id = session.get('organization_id')
        
        # Check permissions
        if user_role == 'student' and str(current_user_id) != str(user_id):
            flash('Access denied.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Get user details
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('web.payments'))
        
        # For org admins, ensure user is in their organization
        user_org_ids = user.get('organization_ids', [])
        if not user_org_ids and user.get('organization_id'):
            user_org_ids = [user['organization_id']]
        
        if user_role in ['org_admin', 'coach_admin'] and org_id not in [str(oid) for oid in user_org_ids]:
            flash('Access denied.', 'error')
            return redirect(url_for('web.payments'))
        
        # Get all payments for this user
        payments_query = {'student_id': ObjectId(user_id)}
        if org_id:
            payments_query['organization_id'] = ObjectId(org_id)
        
        payments = list(mongo.db.payments.find(payments_query).sort('created_at', -1))
        print(payments)
        # Convert ObjectIds to strings
        for payment in payments:
            payment['_id'] = str(payment['_id'])
            payment['student_id'] = str(payment['student_id'])
            payment['organization_id'] = str(payment['organization_id'])
        
        user['_id'] = str(user['_id'])
        if user.get('organization_id'):
            user['organization_id'] = str(user['organization_id'])
        
        return render_template('user_payments.html', user=user, payments=payments)
    
    except Exception as e:
        current_app.logger.error(f"User payments error: {str(e)}")
        flash('Error loading user payments.', 'error')
        return redirect(url_for('web.payments'))

@web_bp.route('/payments/create', methods=['GET', 'POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def create_payment():
    """Create new payment"""
    if request.method == 'GET':
        # Show create payment form
        org_id = session.get('organization_id')
        user_id = request.args.get('user_id')
        
        # Get students in the organization
        students_query = {
            'organization_id': ObjectId(org_id),
            'role': 'student'
        }
        
        current_app.logger.info(f"Students query: {students_query}")
        
        students = list(mongo.db.users.find(students_query).sort('name', 1))
        
        # Convert ObjectIds to strings
        for student in students:
            student['_id'] = str(student['_id'])
            if student.get('organization_id'):
                student['organization_id'] = str(student['organization_id'])
        
        print(f"Found {len(students)} students for organization {org_id}")
        if len(students) == 0:
            current_app.logger.warning(f"No students found for organization {org_id}. Check if students exist and are active.")
        
        return render_template('create_payment.html', students=students, selected_user_id=user_id)
    
    else:
            org_id = session.get('organization_id')
            created_by = session.get('user_id')
            
            # Get form data
            student_id = request.form.get('student_id')
            amount = float(request.form.get('amount', 0))
            description = request.form.get('description', '')
            due_date_str = request.form.get('due_date')
            payment_type = request.form.get('payment_type', 'monthly')
            notes = request.form.get('notes', '')
            
            # Validate required fields
            if not all([student_id, amount, description, due_date_str]):
                flash('Please fill in all required fields.', 'error')
                return redirect(request.url)
            
            # Parse due date
            from datetime import datetime
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            print(due_date)
            
            # Create payment record
            payment = {
                'student_id': ObjectId(student_id),
                'organization_id': ObjectId(org_id),
                'amount': amount,
                'description': description,
                'due_date': due_date_str,
                'payment_type': payment_type,
                'status': 'pending',
                'notes': notes,
                'created_at': datetime.now(),
                'created_by': ObjectId(created_by),
                'updated_at': datetime.now()
            }
            
            result = mongo.db.payments.insert_one(payment)
            
            flash('Payment created successfully!', 'success')
            return redirect(url_for('web.user_payments', user_id=student_id))
            
        

@web_bp.route('/api/payments/<payment_id>/mark-paid', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def mark_payment_paid(payment_id):
    """Mark a payment as paid"""
    try:
        org_id = session.get('organization_id')
        
        # Get the payment
        payment = mongo.db.payments.find_one({
            '_id': ObjectId(payment_id),
            'organization_id': ObjectId(org_id)
        })
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Get form data
        data = request.get_json()
        paid_amount = float(data.get('paid_amount', 0))
        payment_method = data.get('payment_method', '')
        payment_reference = data.get('payment_reference', '')
        notes = data.get('notes', '')
        
        # Validate required fields
        if not paid_amount or not payment_method:
            return jsonify({'error': 'Amount and payment method are required'}), 400
        
        # Update payment
        from datetime import datetime
        update_data = {
            'status': 'paid',
            'paid_amount': paid_amount,
            'paid_date': datetime.now().date(),
            'payment_method': payment_method,
            'payment_reference': payment_reference,
            'updated_at': datetime.now()
        }
        
        if notes:
            # Append to existing notes if any
            existing_notes = payment.get('notes', '')
            if existing_notes:
                update_data['notes'] = f"{existing_notes}\n\nPayment recorded: {notes}"
            else:
                update_data['notes'] = f"Payment recorded: {notes}"
        
        result = mongo.db.payments.update_one(
            {'_id': ObjectId(payment_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': 'Payment marked as paid successfully'})
        else:
            return jsonify({'error': 'Failed to update payment'}), 500
            
    except ValueError as e:
        return jsonify({'error': 'Invalid amount format'}), 400
    except Exception as e:
        current_app.logger.error(f"Mark payment paid error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/groups')
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def groups():
    """Groups/Teams management page"""
    flash('Groups management coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/coaches')
@login_required
@role_required(['org_admin', 'coach_admin'])
def coaches():
    """Coaches management page"""
    flash('Coaches management coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/attendance')
@login_required
@role_required(['coach', 'coach_admin'])
def attendance():
    """Attendance management page"""
    flash('Attendance management coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/progress')
@login_required
@role_required(['coach', 'coach_admin'])
def progress():
    """Progress tracking page"""
    flash('Progress tracking coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/my_classes')
@login_required
@role_required(['student'])
def my_classes():
    """Student's classes page"""
    flash('My classes page coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/my_progress')
@login_required
@role_required(['student'])
def my_progress():
    """Student's progress page"""
    flash('My progress page coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/my_payments')
@login_required
@role_required(['student'])
def my_payments():
    """Student's payments page"""
    flash('My payments page coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/reports')
@login_required
@role_required(['org_admin', 'coach_admin'])
def reports():
    """Reports page"""
    flash('Reports coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/class/<class_id>')
@login_required
def class_detail(class_id):
    """Class detail page"""
    flash('Class details coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/schedule_class')
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def schedule_class():
    """Schedule new class page"""
    flash('Class scheduling coming soon!', 'info')
    return redirect(url_for('web.dashboard'))

@web_bp.route('/organizations')
@login_required
@role_required(['super_admin'])
def organizations():
    """Organizations management page for super admin"""
    # Get search and filter parameters
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    activity = request.args.get('activity', '')
    
    # Sort by created_at
    sort_by = request.args.get('sort', '_id')
    sort_order = request.args.get('order', 'asc')
    query = {}


    if sort_order == 'asc':
        sort_direction = 1
    else:
        sort_direction = -1
        
        # Build query
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'contact_info.email': {'$regex': search, '$options': 'i'}},
                {'address.city': {'$regex': search, '$options': 'i'}}
            ]
        
        if status:
            if status == 'active':
                query['is_active'] = True
            elif status == 'inactive':
                query['is_active'] = False
        
    if activity:
        query['activities'] = activity
        
    # Get organizations
    orgs_cursor = mongo.db.organizations.find(query).sort(sort_by, sort_direction)
    organizations_list = []
    print(orgs_cursor)
    for org in orgs_cursor:
            # Get admin user details
            admin = None
            if org.get('owner_id'):
                admin = mongo.db.users.find_one({'_id': org['owner_id']})

            
            # Get user count
            user_count = mongo.db.users.count_documents({'organization_id': org['_id']})
            
            # Get center count
            center_count = mongo.db.centers.count_documents({'organization_id': org['_id']}) if 'centers' in mongo.db.list_collection_names() else 0
            
            org_data = {
                '_id': str(org['_id']),
                'name': org['name'],
            'admin_name': f"{admin.get('name', '')}" if admin else 'No Admin',
                'admin_email': admin.get('email', '') if admin else '',
                'admin_phone': org.get('contact_info', {}).get('phone', ''),
                'whatsapp_number': org.get('whatsapp_number', ''),
                'address': org.get('address', {}),
            'activities': org.get('activities', []),
                'user_count': user_count,
                'center_count': center_count,
                'is_active': org.get('is_active', True),
                'created_at': org.get('created_at', datetime.utcnow()),
                'subscription_status': org.get('subscription_status', 'active')
            }
            organizations_list.append(org_data)
        
    stats = {}

    stats = {
        'total_organizations': len(organizations_list),
        'active_organizations': sum(1 for org in organizations_list if org['is_active']),
        'total_users': sum(org['user_count'] for org in organizations_list),
        'total_revenue': 0  # Placeholder
    }

    print(organizations_list)
    return render_template('organizations.html', organizations=organizations_list, stats=stats)
    
    

@web_bp.route('/create_organization', methods=['GET'])
@login_required
@role_required(['super_admin'])
def create_organization():
    """Show create organization form"""
    return redirect(url_for('web.organizations'))

@web_bp.route('/create_organization_submit', methods=['POST'])
@login_required
@role_required(['super_admin'])
def create_organization_submit():
    """Handle organization creation form submission"""
    try:
        # Get form data
        org_name = request.form.get('org_name')
        description = request.form.get('description', '')
        whatsapp_number = request.form.get('whatsapp_number', '')
        
        # Address data
        address = {
            'street': request.form.get('street', ''),
            'city': request.form.get('city', ''),
            'state': request.form.get('state', ''),
            'zipcode': request.form.get('zipcode', ''),
            'country': request.form.get('country', '')
        }
        
        # Admin user data
        admin_email = request.form.get('admin_email')
        admin_password = request.form.get('admin_password')
        admin_first_name = request.form.get('admin_first_name')
        admin_last_name = request.form.get('admin_last_name')
        admin_phone = request.form.get('admin_phone', '')
        
        # Activities
        activities_str = request.form.get('activities', '')
        activities = [activity.strip() for activity in activities_str.split(',') if activity.strip()]
        
        # Validation
        if not all([org_name, admin_email, admin_password, admin_first_name, admin_last_name]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('web.organizations'))
        
        if not admin_phone:
            flash('Admin phone number is required.', 'error')
            return redirect(url_for('web.organizations'))
        
        # Prepare contact info
        contact_info = {
            'email': admin_email,
            'phone': admin_phone
        }
        
        # Prepare admin name
        admin_name = f"{admin_first_name} {admin_last_name}"
        
        # Create organization with admin
        result, status_code = AuthService.create_organization_with_admin(
            org_name, contact_info, address, activities, 
            admin_phone, admin_name, admin_password
        )
        
        if status_code == 201 and 'organization' in result:
            org = result['organization']
            org_id = org['_id']
            
            # Update organization with additional details
            update_data = {
                'description': description,
                'whatsapp_number': whatsapp_number,
            }
            
            mongo.db.organizations.update_one(
                {'_id': ObjectId(org_id)},
                {'$set': update_data}
            )
            
            flash(f'Organization "{org_name}" created successfully!', 'success')
        else:
            error_msg = result.get('error', 'Failed to create organization')
            flash(error_msg, 'error')
    
    except Exception as e:
        current_app.logger.error(f"Create organization error: {str(e)}")
        flash('An error occurred while creating organization.', 'error')
    
    return redirect(url_for('web.organizations'))

@web_bp.route('/api/organizations/<org_id>')
@login_required
@role_required(['super_admin'])
def api_get_organization(org_id):
    """API endpoint to get organization data for editing"""
    try:
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Convert ObjectId to string
        org['_id'] = str(org['_id'])
        if org.get('owner_id'):
            admin = mongo.db.users.find_one({'_id': org['owner_id']})   
            org['owner_id'] = str(org['owner_id'])

            print(admin)
            org['admin_name'] = f"{admin.get('name', '')}" if admin else 'No Admin'
            org['admin_email'] = admin.get('email', '') if admin else ''
            org['admin_phone'] = org.get('contact_info', {}).get('phone', '')

            org['whatsapp_number'] = org.get('whatsapp_number', '')

        # Get user and center counts
        org['user_count'] = mongo.db.users.count_documents({'organization_id': org['_id']})
        org['center_count'] = mongo.db.centers.count_documents({'organization_id': org['_id']}) if 'centers' in mongo.db.list_collection_names() else 0
            
        
        return jsonify(org), 200
    
    except Exception as e:
        current_app.logger.error(f"API get organization error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/organizations/<org_id>/edit', methods=['POST'])
@login_required
@role_required(['super_admin'])
def edit_organization(org_id):
    """Update organization"""
    try:
        # Get form data
        org_name = request.form.get('org_name', '').strip()
        description = request.form.get('description', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        is_active = request.form.get('is_active') == 'true'
        
        # Address data
        address = {
            'street': request.form.get('street', '').strip(),
            'city': request.form.get('city', '').strip(),
            'state': request.form.get('state', '').strip(),
            'zipcode': request.form.get('zipcode', '').strip(),
            'country': request.form.get('country', '').strip()
        }
        
        # Activities
        activities_str = request.form.get('activities', '')
        activities = [activity.strip() for activity in activities_str.split(',') if activity.strip()]
        
        # Admin data
        admin_name = request.form.get('admin_name', '').strip()
        admin_email = request.form.get('admin_email', '').strip()
        admin_phone = request.form.get('admin_phone', '').strip()
        
        # Basic validation
        if not org_name:
            flash('Organization name is required.', 'error')
            return redirect(url_for('web.organizations'))
        
        if not all([admin_name, admin_email, admin_phone]):
            flash('Admin name, email, and phone are required.', 'error')
            return redirect(url_for('web.organizations'))
        
        # Get current organization data
        current_org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not current_org:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.organizations'))
        
        # Check for duplicate name (excluding current organization)
        existing_org = mongo.db.organizations.find_one({
            'name': org_name,
            '_id': {'$ne': ObjectId(org_id)}
        })
        if existing_org:
            flash('An organization with this name already exists.', 'error')
            return redirect(url_for('web.organizations'))
        
        # Update admin user if exists
        admin_updated = False
        if current_org.get('owner_id'):
            admin_user = mongo.db.users.find_one({'_id': current_org['owner_id']})
            if admin_user:
                # Split admin name into first and last name
                name_parts = admin_name.split(' ', 1)
                admin_first_name = name_parts[0] if len(name_parts) > 0 else ''
                admin_last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                # Check if email is changing and if it conflicts with another user
                if admin_email != admin_user.get('email', ''):
                    existing_user = mongo.db.users.find_one({
                        'email': admin_email,
                        '_id': {'$ne': current_org['owner_id']}
                    })
                    if existing_user:
                        flash('This email is already used by another user.', 'error')
                        return redirect(url_for('web.organizations'))
                
                # Update admin user
                admin_update_data = {
                    'first_name': admin_first_name,
                    'last_name': admin_last_name,
                    'email': admin_email,
                    'phone_number': admin_phone,
                    'updated_at': datetime.utcnow()
                }
                
                admin_result = mongo.db.users.update_one(
                    {'_id': current_org['owner_id']},
                    {'$set': admin_update_data}
                )
                admin_updated = admin_result.modified_count > 0
        
        # Prepare organization update data
        update_data = {
            'name': org_name,
            'description': description,
            'whatsapp_number': whatsapp_number,
            'address': address,
            'activities': activities,
            'is_active': is_active,
            'contact_info': {
                'email': admin_email,
                'phone': admin_phone
            },
            'updated_at': datetime.utcnow()
        }
        
        # Update organization
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(org_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0 or admin_updated:
            message = f'Organization "{org_name}" has been successfully updated.'
            if admin_updated:
                message += ' Admin information has also been updated.'
            flash(message, 'success')
        else:
            flash('No changes were made to the organization.', 'info')
        
    except Exception as e:
        current_app.logger.error(f"Edit organization error: {str(e)}")
        flash('An unexpected error occurred while updating the organization.', 'error')
    
    return redirect(url_for('web.organizations'))

@web_bp.route('/api/organizations/<org_id>', methods=['DELETE'])
@login_required
@role_required(['super_admin'])
def delete_organization(org_id):
    """Delete organization"""
    try:
        # Get organization data
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Check if organization has users
        user_count = mongo.db.users.count_documents({'organization_id': ObjectId(org_id)})
        if user_count > 0:
            return jsonify({'error': f'Cannot delete organization with {user_count} users. Please remove all users first.'}), 400
        
        # Delete organization
        result = mongo.db.organizations.delete_one({'_id': ObjectId(org_id)})
        
        if result.deleted_count > 0:
            return jsonify({'success': True, 'message': f'Organization "{org.get("name", "Unknown")}" has been deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete organization'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Delete organization error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@web_bp.route('/api/organizations/<org_id>/status', methods=['PUT'])
@login_required
@role_required(['super_admin'])
def update_organization_status(org_id):
    """Update organization status"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['active', 'suspended', 'inactive']:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Get organization
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            return jsonify({'error': 'Organization not found'}), 404
        
        # Update status
        is_active = status == 'active'
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(org_id)},
            {'$set': {
                'is_active': is_active,
                'subscription_status': status,
                'updated_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': f'Organization status updated to {status}'}), 200
        else:
            return jsonify({'error': 'Failed to update organization status'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Update organization status error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@web_bp.route('/organizations/<org_id>')
@login_required
@role_required(['super_admin'])
def organization_detail(org_id):
    """Organization detail page"""
    try:
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.organizations'))
        
        # Get admin user
        admin = None
        if org.get('owner_id'):
            admin = mongo.db.users.find_one({'_id': org['owner_id']})
        
        # Get users and centers
        users = list(mongo.db.users.find({'organization_id': ObjectId(org_id)}))
        centers = list(mongo.db.centers.find({'organization_id': ObjectId(org_id)})) if 'centers' in mongo.db.list_collection_names() else []
        
        return render_template('organization_detail.html', org=org, admin=admin, users=users, centers=centers)
    
    except Exception as e:
        flash('Error loading organization details.', 'error')
        return redirect(url_for('web.organizations'))

@web_bp.route('/organization_settings', methods=['GET', 'POST'])
@login_required
@role_required(['org_admin'])
def organization_settings():
    """Organization settings page for org admin"""
    try:
        org_id = session.get('organization_id')
        if not org_id:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        org = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        if request.method == 'POST':
            # Handle organization settings update
            return update_organization_settings(org_id, org)
        
        # GET request - show settings page
        # Get centers for this organization
        centers = list(mongo.db.centers.find({'organization_id': ObjectId(org_id)}))
        
        return render_template('organization_settings.html', org=org, centers=centers)
    
    except Exception as e:
        flash('Error loading organization settings.', 'error')
        return redirect(url_for('web.dashboard'))

def update_organization_settings(org_id, current_org):
    """Update organization settings"""
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        google_maps_link = request.form.get('google_maps_link', '').strip()
        terms_and_conditions = request.form.get('terms_and_conditions', '').strip()
        
        # Contact information
        contact_email = request.form.get('contact_info[email]', '').strip()
        contact_phone = request.form.get('contact_info[phone]', '').strip()
        
        # Address information
        address = {
            'street': request.form.get('address[street]', '').strip(),
            'city': request.form.get('address[city]', '').strip(),
            'state': request.form.get('address[state]', '').strip(),
            'zipcode': request.form.get('address[zipcode]', '').strip(),
            'country': request.form.get('address[country]', '').strip()
        }

        logo_url = None
        banner_url = None

        # Initialize file upload service
        upload_service = FileUploadService()

        print(request.files, 'logo' in request.files, 'banner' in request.files)
        # Implement logo and banner
        if 'logo' in request.files:
            logo = request.files['logo']
            if logo.filename != '':
                success, message, logo_url = upload_service.upload_file(
                    file=logo,
                    upload_type='logo',
                    organization_id=str(org_id),
                    user_id=session.get('user_id')
                )
                print(success, message, banner_url)
                if not success:
                    flash(f'Error uploading logo: {message}', 'error')
                    return redirect(url_for('web.organization_settings'))
        
        if 'banner' in request.files:
            banner = request.files['banner']
            if banner.filename != '':
                success, message, banner_url = upload_service.upload_file(
                    file=banner,
                    upload_type='banner',
                    organization_id=str(org_id),
                    user_id=session.get('user_id')
                )
                print(success, message, banner_url)
                if not success:
                    flash(f'Error uploading banner: {message}', 'error')
                    return redirect(url_for('web.organization_settings'))
        
        print(logo_url, banner_url)
        # Activities
        activities_str = request.form.get('activities', '')
        activities = [activity.strip() for activity in activities_str.split(',') if activity.strip()]
        
        # Basic validation
        if not name:
            flash('Organization name is required.', 'error')
            return redirect(url_for('web.organization_settings'))
        
        # Check for duplicate name (excluding current organization)
        existing_org = mongo.db.organizations.find_one({
            'name': name,
            '_id': {'$ne': ObjectId(org_id)}
        })
        if existing_org:
            flash('An organization with this name already exists.', 'error')
            return redirect(url_for('web.organization_settings'))
        
        # Prepare update data
        update_data = {
            'name': name,
            'description': description,
            'whatsapp_number': whatsapp_number,
            'google_maps_link': google_maps_link,
            'terms_and_conditions': terms_and_conditions,
            'contact_info': {
                'email': contact_email,
                'phone': contact_phone
            },
            'address': address,
            'activities': activities,
            'updated_at': datetime.utcnow()
        }

        if logo_url:
            update_data['logo_url'] = logo_url
        if banner_url:
            update_data['banner_url'] = banner_url
        
        # Update organization
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(org_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            flash(f'Organization "{name}" settings have been successfully updated.', 'success')
        else:
            flash('No changes were made to the organization settings.', 'info')
    
    except Exception as e:
        current_app.logger.error(f"Update organization settings error: {str(e)}")
        flash('An unexpected error occurred while updating organization settings.', 'error')
    
    return redirect(url_for('web.organization_settings'))

@web_bp.route('/organization_signup_management')
@login_required
@role_required(['org_admin'])
def organization_signup_management():
    """Organization signup link management page"""
    try:
        from app.models.organization import Organization
        
        org_id = session.get('organization_id')
        if not org_id:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        org_data = mongo.db.organizations.find_one({'_id': ObjectId(org_id)})
        if not org_data:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        org = Organization.from_dict(org_data)
        
        # Get signup statistics
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        last_week = datetime.utcnow() - timedelta(days=7)
        last_month = datetime.utcnow() - timedelta(days=30)
        
        stats = {
            'total_students': mongo.db.users.count_documents({
                'organization_id': ObjectId(org_id),
                'role': 'student'
            }),
            'signups_today': mongo.db.users.count_documents({
                'organization_id': ObjectId(org_id),
                'role': 'student',
                'created_at': {'$gte': yesterday}
            }),
            'signups_week': mongo.db.users.count_documents({
                'organization_id': ObjectId(org_id),
                'role': 'student',
                'created_at': {'$gte': last_week}
            }),
            'signups_month': mongo.db.users.count_documents({
                'organization_id': ObjectId(org_id),
                'role': 'student',
                'created_at': {'$gte': last_month}
            })
        }
        
        return render_template('organization_signup_management.html', 
                             organization=org, 
                             stats=stats)
        
    except Exception as e:
        current_app.logger.error(f"Organization signup management error: {str(e)}")
        flash('Error loading signup management page.', 'error')
        return redirect(url_for('web.dashboard'))

@web_bp.route('/organization_signup_management/regenerate', methods=['POST'])
@login_required
@role_required(['org_admin'])
def regenerate_signup_credentials():
    """Regenerate organization signup credentials"""
    try:
        from app.services.organization_signup_service import OrganizationSignupService
        
        org_id = session.get('organization_id')
        user_id = session.get('user_id')
        
        if not org_id or not user_id:
            flash('Invalid session.', 'error')
            return redirect(url_for('web.dashboard'))
        
        success, message, credentials = OrganizationSignupService.generate_new_signup_credentials(
            org_id, user_id
        )
        
        if success:
            flash(f'New signup credentials generated successfully! New center code: {credentials["center_code"]}', 'success')
        else:
            flash(f'Error: {message}', 'error')
        
    except Exception as e:
        current_app.logger.error(f"Regenerate credentials error: {str(e)}")
        flash('Error regenerating credentials.', 'error')
    
    return redirect(url_for('web.organization_signup_management'))

@web_bp.route('/organization_signup_management/settings', methods=['POST'])
@login_required
@role_required(['org_admin'])
def update_signup_settings():
    """Update organization signup settings"""
    try:
        org_id = session.get('organization_id')
        if not org_id:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Get form data
        signup_enabled = request.form.get('signup_enabled') == 'on'
        max_signups_per_day = int(request.form.get('max_signups_per_day', 50))
        signup_requires_approval = request.form.get('signup_requires_approval') == 'on'
        
        # Validate
        if max_signups_per_day < 1 or max_signups_per_day > 1000:
            flash('Max signups per day must be between 1 and 1000.', 'error')
            return redirect(url_for('web.organization_signup_management'))
        
        # Update settings
        update_data = {
            'signup_enabled': signup_enabled,
            'max_signups_per_day': max_signups_per_day,
            'signup_requires_approval': signup_requires_approval,
            'updated_at': datetime.utcnow()
        }
        
        result = mongo.db.organizations.update_one(
            {'_id': ObjectId(org_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            flash('Signup settings updated successfully.', 'success')
        else:
            flash('No changes were made.', 'info')
        
    except ValueError:
        flash('Invalid number for max signups per day.', 'error')
    except Exception as e:
        current_app.logger.error(f"Update signup settings error: {str(e)}")
        flash('Error updating signup settings.', 'error')
    
    return redirect(url_for('web.organization_signup_management'))

@web_bp.route('/centers')
@login_required
@role_required(['org_admin', 'coach_admin'])
def centers():
    """Centers management page"""
    try:
        org_id = session.get('organization_id')
        if not org_id:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.dashboard'))
        
        # Get centers for this organization
        centers_list = []
        centers_cursor = mongo.db.centers.find({'organization_id': ObjectId(org_id)})
        
        for center in centers_cursor:
            # Get assigned coaches
            coach_count = len(center.get('coaches', []))
            
            # Mock class count for now
            class_count = 0  # Will be replaced with actual query when classes collection is set up
            
            center_data = {
                '_id': str(center['_id']),
                'name': center['name'],
                'address': center.get('address', {}),
                'contact_info': center.get('contact_info', {}),
                'facilities': center.get('facilities', []),
                'coach_count': coach_count,
                'class_count': class_count,
                'is_active': center.get('is_active', True),
                'created_at': center.get('created_at', datetime.utcnow())
            }
            centers_list.append(center_data)
        
        # Get available coaches for assignment
        coaches = list(mongo.db.users.find({
            'organization_id': ObjectId(org_id),
            'role': {'$in': ['coach', 'coach_admin']}
        }))
        
        return render_template('centers.html', centers=centers_list, coaches=coaches)
    
    except Exception as e:
        current_app.logger.error(f"Centers page error: {str(e)}")
        flash('Error loading centers.', 'error')
        return render_template('centers.html', centers=[], coaches=[])

@web_bp.route('/calendar')
@login_required
def calendar():
    """Calendar view for classes and events"""
    try:
        user_role = session.get('role')
        user_id = session.get('user_id')
        
        # Get classes based on user role
        classes = []
        
        # Mock calendar data for now
        events = [
            {
                'id': '1',
                'title': 'Football Training - Beginners',
                'coach': 'John Smith',
                'sport': 'Football',
                'date': '2024-02-05',
                'time': '16:00',
                'duration': '1.5 hours',
                'location': 'Field A',
                'status': 'scheduled'
            },
            {
                'id': '2',
                'title': 'Basketball Advanced',
                'coach': 'Mike Johnson',
                'sport': 'Basketball',
                'date': '2024-02-06',
                'time': '18:00',
                'duration': '2 hours',
                'location': 'Court 1',
                'status': 'scheduled'
            }
        ]
        
        return render_template('calendar.html', events=events)
    
    except Exception as e:
        current_app.logger.error(f"Calendar page error: {str(e)}")
        flash('Error loading calendar.', 'error')
        return render_template('calendar.html', events=[])

# Export routes
@web_bp.route('/export_users')
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def export_users():
    """Export users to CSV"""
    import csv
    import io
    from flask import make_response
    from datetime import datetime
    
    try:
        user_role = session.get('role')
        
        # Build query based on user role - same logic as users page
        query = {}
        if user_role in ['org_admin', 'coach_admin']:
            org_id = session.get('organization_id')
            if org_id:
                query['organization_ids'] = ObjectId(org_id)
        
        # Get filter parameters from request args
        search = request.args.get('search', '')
        role_filter = request.args.get('role', '')
        status_filter = request.args.get('status', '')
        org_filter = request.args.get('organization', '')
        
        # Apply same filters as users page
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}},
                {'phone_number': {'$regex': search, '$options': 'i'}}
            ]
        
        if role_filter:
            query['role'] = role_filter
            
        if status_filter:
            if status_filter == 'active':
                query['is_active'] = True
            elif status_filter == 'inactive':
                query['is_active'] = False
        
        # Organization filter (only for super admin)
        if org_filter and user_role == 'super_admin':
            query['organization_ids'] = ObjectId(org_filter)
        
        # Get all users (no pagination for export)
        users_cursor = mongo.db.users.find(query).sort('created_at', -1)
        users = list(users_cursor)
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            'Name', 'Email', 'Phone', 'Role', 'Status', 'Organization',
            'Groups', 'Last Login', 'Created Date', 'Age', 'Emergency Contact',
            'Specialization', 'Experience Years'
        ]
        writer.writerow(headers)
        
        # Write user data
        for user_data in users:
            user = User.from_dict(user_data)
            
            # Get organization name
            org_name = ''
            if user.organization_id:
                org_data = mongo.db.organizations.find_one({'_id': user.organization_id})
                if org_data:
                    org_name = org_data['name']
            
            # Get group names
            group_names = []
            if user.role == 'student' and user.groups:
                for group_id in user.groups:
                    group_data = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
                    if group_data:
                        group_names.append(group_data['name'])
            
            # Get profile data
            profile_data = user.profile_data or {}
            age = profile_data.get('age', '')
            emergency_contact = profile_data.get('emergency_contact', '')
            specialization = profile_data.get('specialization', '')
            experience_years = profile_data.get('experience_years', '')
            
            # Format dates
            last_login = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'
            created_date = user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else ''
            
            row = [
                user.name,
                user.email or '',
                user.phone_number,
                user.role.replace('_', ' ').title(),
                'Active' if user.is_active else 'Inactive',
                org_name,
                ', '.join(group_names),
                last_login,
                created_date,
                age,
                emergency_contact,
                specialization,
                experience_years
            ]
            writer.writerow(row)
        
        # Create response
        output.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'users_export_{timestamp}.csv'
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Export users error: {str(e)}")
        flash('Error exporting users. Please try again.', 'error')
    return redirect(url_for('web.users'))

@web_bp.route('/export_organizations')
@login_required
@role_required(['super_admin'])
def export_organizations():
    """Export organizations to CSV"""
    import csv
    import io
    from flask import make_response
    from datetime import datetime
    
    try:
        # Get filter parameters from request args
        search = request.args.get('search', '')
        status_filter = request.args.get('status', '')
        activity_filter = request.args.get('activity', '')
        
        # Build query
        query = {}
        
        # Apply filters
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'admin_name': {'$regex': search, '$options': 'i'}},
                {'admin_email': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}}
            ]
        
        if status_filter:
            if status_filter == 'active':
                query['subscription_status'] = 'active'
            elif status_filter == 'inactive':
                query['subscription_status'] = 'inactive'
            elif status_filter == 'trial':
                query['subscription_status'] = 'trial'
            elif status_filter == 'expired':
                query['subscription_status'] = 'expired'
        
        if activity_filter:
            query['activities'] = activity_filter
        
        # Get all organizations (no pagination for export)
        organizations_cursor = mongo.db.organizations.find(query).sort('created_at', -1)
        organizations = list(organizations_cursor)
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            'Organization Name', 'Description', 'Admin Name', 'Admin Email', 'Admin Phone',
            'WhatsApp Number', 'Street Address', 'City', 'State', 'ZIP Code', 'Country',
            'Activities Offered', 'User Count', 'Centers Count', 'Subscription Status',
            'Subscription Expires', 'Created Date', 'Status'
        ]
        writer.writerow(headers)
        
        # Write organization data
        for org_data in organizations:
            # Get user count for this organization
            user_count = mongo.db.users.count_documents({'organization_id': org_data['_id']})
            
            # Get centers count (if centers collection exists)
            centers_count = 0
            try:
                centers_count = mongo.db.centers.count_documents({'organization_id': org_data['_id']})
            except:
                pass
            
            # Get address data
            address = org_data.get('address', {})
            street = address.get('street', '') if address else ''
            city = address.get('city', '') if address else ''
            state = address.get('state', '') if address else ''
            zipcode = address.get('zipcode', '') if address else ''
            country = address.get('country', '') if address else ''
            
            # Get activities
            activities = ', '.join(org_data.get('activities', []))
            
            # Format dates
            created_date = org_data.get('created_at', '')
            if created_date:
                created_date = created_date.strftime('%Y-%m-%d %H:%M') if hasattr(created_date, 'strftime') else str(created_date)
            
            subscription_expires = org_data.get('subscription_expires_at', '')
            if subscription_expires:
                subscription_expires = subscription_expires.strftime('%Y-%m-%d') if hasattr(subscription_expires, 'strftime') else str(subscription_expires)
            
            row = [
                org_data.get('name', ''),
                org_data.get('description', ''),
                org_data.get('admin_name', ''),
                org_data.get('admin_email', ''),
                org_data.get('admin_phone', ''),
                org_data.get('whatsapp_number', ''),
                street,
                city,
                state,
                zipcode,
                country,
                activities,
                user_count,
                centers_count,
                org_data.get('subscription_status', '').title(),
                subscription_expires,
                created_date,
                'Active' if org_data.get('is_active', True) else 'Inactive'
            ]
            writer.writerow(row)
        
        # Create response
        output.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'organizations_export_{timestamp}.csv'
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Export organizations error: {str(e)}")
        flash('Error exporting organizations. Please try again.', 'error')
        return redirect(url_for('web.organizations'))

@web_bp.route('/export_classes')
@login_required
@role_required(['org_admin', 'coach_admin'])
def export_classes():
    """Export classes to CSV"""
    flash('Export functionality coming soon!', 'info')
    return redirect(url_for('web.classes'))

@web_bp.route('/export_payments')
@login_required
@role_required(['org_admin', 'coach_admin'])
def export_payments():
    """Export payments to CSV"""
    flash('Export functionality coming soon!', 'info')
    return redirect(url_for('web.payments'))

# Detail and edit routes (placeholders)
@web_bp.route('/api/users/<user_id>')
@jwt_or_session_required()
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def api_get_user(user_id):
    """API endpoint to get user data for editing"""
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        print(user)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get current user info from either JWT or session
        user_info = get_current_user_info()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
            
        current_role = user_info['role']
        
        # Check permissions
        if current_role in ['org_admin', 'coach_admin']:
            current_org_id = user_info['organization_id']
            if str(user.get('organization_id')) != current_org_id:
                return jsonify({'error': 'Permission denied'}), 403
        
        # Convert ObjectId to string
        user['_id'] = str(user['_id'])
        if user.get('organization_id'):
            user['organization_id'] = str(user['organization_id'])

        if user.get('subscription_ids'):
            user['subscription_ids'] = [str(subscription_id) for subscription_id in user['subscription_ids']]
        
        return jsonify(user), 200
    
    except Exception as e:
        current_app.logger.error(f"API get user error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/users/<user_id>/edit', methods=['POST'])
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def edit_user(user_id):
    """Update user"""
    try:
        from datetime import datetime

        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        role = request.form.get('role', '').strip()
        is_active = request.form.get('is_active') == 'true'
        
        # Role-specific fields
        age = request.form.get('age')
        emergency_contact = request.form.get('emergency_contact', '').strip()
        specialization = request.form.get('specialization', '').strip()
        experience_years = request.form.get('experience_years')
        billing_start_date = request.form.get('billing_start_date')
        
        # Basic validation
        if not all([name, email, phone_number, role]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('web.users'))
        
        # Validate email
        is_valid_email, email_message = User.validate_email(email)
        if not is_valid_email:
            flash(f'Email validation failed: {email_message}', 'error')
            return redirect(url_for('web.users'))
        
        # Validate phone number
        if not User.validate_phone_number(phone_number):
            flash('Please enter a valid phone number.', 'error')
            return redirect(url_for('web.users'))
        
        # Get current user data
        current_user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not current_user:
            flash('User not found.', 'error')
            return redirect(url_for('web.users'))
        
        # Check permissions
        current_role = session.get('role')
        if current_role in ['org_admin', 'coach_admin']:
            current_org_id = session.get('organization_id')
            if str(current_user.get('organization_id')) != current_org_id:
                flash('You do not have permission to edit this user.', 'error')
                return redirect(url_for('web.users'))
        
        # Check for duplicate email (excluding current user)
        existing_email = mongo.db.users.find_one({
            'email': email,
            '_id': {'$ne': ObjectId(user_id)}
        })
        if existing_email:
            flash('A user with this email already exists.', 'error')
            return redirect(url_for('web.users'))
        
        # Check for duplicate phone (excluding current user)
        normalized_phone = User(phone_number, 'temp')._normalize_phone_number(phone_number)
        existing_phone = mongo.db.users.find_one({
            'phone_number': normalized_phone,
            '_id': {'$ne': ObjectId(user_id)}
        })
        if existing_phone:
            flash('A user with this phone number already exists.', 'error')
            return redirect(url_for('web.users'))
        
        # Prepare update data
        update_data = {
            'name': name,
            'email': email,
            'phone_number': normalized_phone,
            'role': role,
            'is_active': is_active,
            'updated_at': datetime.utcnow()
        }
        
        # Handle role-specific profile data
        profile_data = current_user.get('profile_data', {})
        
        if role == 'student':
            if age and age.isdigit():
                profile_data['age'] = int(age)
            if emergency_contact:
                profile_data['emergency_contact'] = emergency_contact
        elif role in ['coach', 'coach_admin']:
            if specialization:
                profile_data['specialization'] = specialization
            if experience_years and experience_years.isdigit():
                profile_data['experience_years'] = int(experience_years)
        
        update_data['profile_data'] = profile_data

        
        # Handle billing start date
        if billing_start_date:
            try:
                billing_date = datetime.strptime(billing_start_date, '%Y-%m-%d')
                update_data['billing_start_date'] = billing_date
            except ValueError:
                # Invalid date format, skip
                print(f"Invalid date format: {billing_start_date}")
                pass
        
        # Update user
        result = mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            flash(f'User "{name}" has been successfully updated.', 'success')
        else:
            flash('No changes were made to the user.', 'info')
        
    except Exception as e:
        current_app.logger.error(f"Edit user error: {str(e)}")
        flash('An unexpected error occurred while updating the user.', 'error')
    
    return redirect(url_for('web.users'))

@web_bp.route('/users/<user_id>/delete', methods=['DELETE'])
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def delete_user(user_id):
    """Delete user"""
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        mongo.db.users.delete_one({'_id': ObjectId(user_id)})   
        flash(f'User "{user.get("name", "Unknown")}" has been successfully deleted.', 'success')
        return jsonify({'success': True, 'message': f'User "{user.get("name", "Unknown")}" has been successfully deleted.'}), 200
    except Exception as e:
        current_app.logger.error(f"Delete user error: {str(e)}")
        flash('An unexpected error occurred while deleting the user.', 'error')

    return redirect(url_for('web.users'))

@web_bp.route('/classes/<class_id>/edit')
@login_required
def edit_class(class_id):
    """Edit class page"""
    flash('Class editing coming soon!', 'info')
    return redirect(url_for('web.classes'))

@web_bp.route('/classes/<class_id>/attendance')
@login_required
@role_required(['coach', 'coach_admin'])
def class_attendance(class_id):
    """Class attendance page"""
    flash('Attendance marking coming soon!', 'info')
    return redirect(url_for('web.classes'))

@web_bp.route('/payments/<payment_id>')
@login_required
def payment_detail(payment_id):
    """Payment detail page"""
    flash('Payment details coming soon!', 'info')
    return redirect(url_for('web.payments'))

@web_bp.route('/equipment/<equipment_id>/edit')
@login_required
@role_required(['org_admin', 'coach_admin'])
def edit_equipment(equipment_id):
    """Edit equipment page"""
    flash('Equipment editing coming soon!', 'info')
    return redirect(url_for('web.equipment'))

# Create routes (placeholders)
@web_bp.route('/users/create', methods=['POST'])
@login_required
@role_required(['super_admin', 'org_admin', 'coach_admin'])
def create_user():
    """Create new user"""
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student').strip()
        
        # Student-specific fields
        age = request.form.get('age')
        emergency_contact = request.form.get('emergency_contact', '').strip()
        
        # Coach-specific fields
        specialization = request.form.get('specialization', '').strip()
        experience_years = request.form.get('experience_years')
        
        # Billing date
        billing_start_date = request.form.get('billing_start_date')
        
        # Basic validation
        if not all([name, email, phone_number, password, role]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('web.users'))
        
        # Validate email
        is_valid_email, email_message = User.validate_email(email)
        if not is_valid_email:
            flash(f'Email validation failed: {email_message}', 'error')
            return redirect(url_for('web.users'))
        
        # Validate password
        is_valid_password, password_message = User.validate_password(password)
        if not is_valid_password:
            flash(f'Password validation failed: {password_message}', 'error')
            return redirect(url_for('web.users'))
        
        # Validate phone number
        if not User.validate_phone_number(phone_number):
            flash('Please enter a valid phone number.', 'error')
            return redirect(url_for('web.users'))
        
        # Role validation based on current user's permissions
        current_user_role = session.get('user_role')
        current_user_id = session.get('user_id')
    
        
        # Get organization ID
        org_id = session.get('organization_id')
        if not org_id and current_user_role != 'super_admin':
            flash('Organization not found. Please contact support.', 'error')
            return redirect(url_for('web.users'))
        
        # Create user using AuthService
        result, status_code = AuthService.register_user(
            phone_number=phone_number,
            name=name,
            password=password,
            role=role,
            organization_id=ObjectId(org_id),
            created_by=current_user_id,
            email=email,
            billing_start_date=billing_start_date
        )
        
        if status_code == 201:
            # Add role-specific profile data
            user_id = result['user_id']
            profile_data = {}
            
            if role == 'student' and age:
                profile_data['age'] = int(age) if age.isdigit() else None
                if emergency_contact:
                    profile_data['emergency_contact'] = emergency_contact
            
            elif role in ['coach', 'coach_admin']:
                if specialization:
                    profile_data['specialization'] = specialization
                if experience_years and experience_years.isdigit():
                    profile_data['experience_years'] = int(experience_years)
            
            # Prepare additional updates
            update_data = {'updated_at': datetime.utcnow()}
            
            # Add profile data if any
            if profile_data:
                update_data['profile_data'] = profile_data
            
            # Add billing start date if provided
            if billing_start_date:
                try:
                    billing_date = datetime.strptime(billing_start_date, '%Y-%m-%d')
                    update_data['billing_start_date'] = billing_date
                except ValueError:
                    # Invalid date format, skip
                    pass
            
            # Update user with additional data
            if len(update_data) > 1:  # More than just updated_at
                mongo.db.users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$set': update_data}
                )
            
            flash(f'User "{name}" has been successfully created with role "{role.replace("_", " ").title()}".', 'success')
        else:
            error_message = result.get('error', 'Unknown error occurred')
            flash(f'Failed to create user: {error_message}', 'error')
            
    except Exception as e:
        current_app.logger.error(f"Error creating user: {str(e)}")
        flash('An unexpected error occurred while creating the user. Please try again.', 'error')
    
    return redirect(url_for('web.users'))

# Removed - replaced with new create_payment route above

@web_bp.route('/equipment/create', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def create_equipment():
    """Create new equipment"""
    flash('Equipment creation coming soon!', 'info')
    return redirect(url_for('web.equipment')) 

# Schedule Management Routes
@web_bp.route('/centers/<center_id>/schedule')
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def center_schedule(center_id):
    """Center schedule management page"""
    try:
        # Validate center_id format
        try:
            ObjectId(center_id)
        except:
            current_app.logger.error(f"Invalid center ID format: {center_id}")
            flash('Invalid center ID format.', 'error')
            return redirect(url_for('web.centers'))
        
        user_role = session.get('role')
        org_id = session.get('organization_id')
        
        current_app.logger.info(f"Loading schedule for center {center_id}, user role: {user_role}, org: {org_id}")
        
        # Debug: Check if MongoDB is accessible
        try:
            center_count = mongo.db.centers.count_documents({})
            current_app.logger.info(f"Total centers in database: {center_count}")
        except Exception as db_error:
            current_app.logger.error(f"Database connection error: {db_error}")
            flash('Database connection error. Please try again later.', 'error')
            return redirect(url_for('web.centers'))
        
        # Get center data
        center = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        current_app.logger.info(f"Center found: {center is not None}")
        if center:
            current_app.logger.info(f"Center name: {center.get('name')}, org_id: {center.get('organization_id')}")
        
        if not center:
            flash('Center not found.', 'error')
            return redirect(url_for('web.centers'))
        
        # Check permissions
        current_app.logger.info(f"Permission check - User role: {user_role}, Center org_id: {center.get('organization_id')}, User org_id: {org_id}")
        
        if user_role in ['org_admin', 'coach_admin']:
            if str(center.get('organization_id')) != org_id:
                current_app.logger.warning(f"Permission denied: Center org {center.get('organization_id')} != User org {org_id}")
                flash('You do not have permission to access this center.', 'error')
                return redirect(url_for('web.centers'))
        elif user_role == 'coach':
            # Check if coach is assigned to this center
            user_id = ObjectId(session.get('user_id'))
            center_coaches = center.get('coaches', [])
            current_app.logger.info(f"Coach permission check - User ID: {user_id}, Center coaches: {center_coaches}")
            if user_id not in center_coaches:
                current_app.logger.warning(f"Permission denied: Coach {user_id} not in center coaches {center_coaches}")
                flash('You do not have permission to access this center.', 'error')
                return redirect(url_for('web.centers'))
        else:
            current_app.logger.warning(f"Unknown user role: {user_role}")
            flash('Invalid user role.', 'error')
            return redirect(url_for('web.centers'))
        
        # Get time slots for this center
        time_slots = list(mongo.db.time_slots.find({'center_id': ObjectId(center_id)}).sort('start_time', 1))
        
        # Get schedule data
        schedule = list(mongo.db.schedules.find({'center_id': ObjectId(center_id)}))
        
        # Get available activities for this organization
        activities = list(mongo.db.activities.find({'organization_id': ObjectId(org_id)}))
        
        # Get coaches assigned to this center
        coaches = list(mongo.db.users.find({
            'organization_id': ObjectId(org_id),
            'role': {'$in': ['coach', 'coach_admin']}
        }))

        students = list(mongo.db.users.find({'organization_id': ObjectId(org_id), 'role': 'student'}))
        
        # Convert ObjectIds to strings for template serialization
        center['_id'] = str(center['_id'])
        if center.get('organization_id'):
            center['organization_id'] = str(center['organization_id'])
        
        for slot in time_slots:
            slot['_id'] = str(slot['_id'])
            slot['center_id'] = str(slot['center_id'])
            if slot.get('created_by'):
                slot['created_by'] = str(slot['created_by'])
        
        for item in schedule:
            item['_id'] = str(item['_id'])
            item['center_id'] = str(item['center_id'])
            if item.get('activity_id'):
                item['activity_id'] = str(item['activity_id'])
            if item.get('coach_id'):
                item['coach_id'] = str(item['coach_id'])
            if item.get('time_slot_id'):
                item['time_slot_id'] = str(item['time_slot_id'])
        
        for activity in activities:
            activity['_id'] = str(activity['_id'])
            activity['organization_id'] = str(activity['organization_id'])
            if activity.get('created_by'):
                activity['created_by'] = str(activity['created_by'])
            if activity.get('default_coach_id'):
                activity['default_coach_id'] = str(activity['default_coach_id'])
        
        for coach in coaches:
            coach['_id'] = str(coach['_id'])
            if coach.get('organization_id'):
                coach['organization_id'] = str(coach['organization_id'])
            if 'organization_ids' in coach:
                coach['organization_ids'] = [str(org_id) for org_id in coach['organization_ids']]


        if 'created_by' in center:
            center['created_by'] = str(center['created_by'])

        for student in students:
            for key, value in student.items():
                if '_ids' in key:
                    student[key] = [str(org_id) for org_id in value]
                elif '_id' in key:
                    student[key] = str(value)
            if student.get('subscription_ids'):
                student['subscription_ids'] = [str(sid) for sid in student['subscription_ids']]
            print(student)
            print('--------')
            
        current_app.logger.info(f"Successfully loaded schedule page data for center: {center['name']}")
        

        return render_template('schedule.html', 
                             center=center, 
                             time_slots=time_slots,
                             schedule=schedule,
                             activities=activities,
                             coaches=coaches,
                             students=students)
    
    except Exception as e:
        current_app.logger.error(f"Schedule page error: {str(e)}")
        current_app.logger.error(f"Center ID: {center_id}, User ID: {session.get('user_id')}, Org ID: {session.get('organization_id')}")
        flash('Error loading schedule page. Please check if the center exists and you have permission to access it.', 'error')
        return redirect(url_for('web.centers'))

# Temporary diagnostic route
@web_bp.route('/debug/session')
@login_required
def debug_session():
    """Debug route to check session and available centers"""
    try:
        user_id = session.get('user_id')
        org_id = session.get('organization_id')
        role = session.get('role')
        
        # Get user details
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)}) if user_id else None
        
        # Get available centers
        centers = list(mongo.db.centers.find({'organization_id': ObjectId(org_id)}) if org_id else [])
        
        debug_info = {
            'session': {
                'user_id': user_id,
                'organization_id': org_id,
                'role': role
            },
            'user': {
                'name': user.get('name') if user else None,
                'role': user.get('role') if user else None,
                'organization_id': str(user.get('organization_id')) if user and user.get('organization_id') else None
            },
            'centers_count': len(centers),
            'centers': [{'_id': str(c['_id']), 'name': c.get('name'), 'organization_id': str(c.get('organization_id'))} for c in centers[:5]]
        }
        
        return f"<pre>{str(debug_info)}</pre>"
    except Exception as e:
        return f"Debug error: {str(e)}"

# API Routes for Schedule Management
@web_bp.route('/api/centers/<center_id>/schedule', methods=['GET'])
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def api_get_schedule(center_id):
    """Get schedule data for a center"""
    try:
        # Validate center_id format
        try:
            ObjectId(center_id)
        except:
            current_app.logger.error(f"Invalid center ID format in API: {center_id}")
            return jsonify({'error': 'Invalid center ID format'}), 400
        
        current_app.logger.info(f"API: Loading schedule for center {center_id}")
        
        # Get schedule data and populate assigned_students
        schedule = list(mongo.db.schedules.find({'center_id': ObjectId(center_id)}))
        for item in schedule:
            if item.get('assigned_students'):
                assigned_students = []
                for studentId in item.get('assigned_students', []):
                    student = mongo.db.users.find_one({'_id': studentId})
                    if student:
                        assigned_students.append(student)
                item['assigned_students'] = assigned_students
            else:
                item['assigned_students'] = []
        
        # Convert ObjectIds and other non-serializable types
        schedule = serialize_for_json(schedule)
        
        current_app.logger.info(f"API: Returning {len(schedule)} schedule items")
        return jsonify({'schedule': schedule}), 200
    
    except Exception as e:
        current_app.logger.error(f"API get schedule error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/schedule', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def api_create_schedule_item(center_id):
    """Create a new schedule item"""
    try:
        # ... existing validation code ...

        data = request.get_json()

        # Validate required fields
        required_fields = ['time_slot_id', 'activity_id']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if time slot exists
        time_slot = mongo.db.time_slots.find_one({'_id': ObjectId(data['time_slot_id'])})
        if not time_slot:
            return jsonify({'error': 'Time slot not found'}), 404
        
        # Check if activity exists
        activity = mongo.db.activities.find_one({'_id': ObjectId(data['activity_id'])})
        if not activity:
            return jsonify({'error': 'Activity not found'}), 404
        
        # Check for conflicts
        existing = mongo.db.schedules.find_one({
            'center_id': ObjectId(center_id),
            'day_of_week': data['day_of_week'],
            'time_slot_id': ObjectId(data['time_slot_id'])
        })
        if existing:
            return jsonify({'error': 'Time slot already occupied'}), 409
        
        

        # Get activity to check for default coach
        activity = mongo.db.activities.find_one({'_id': ObjectId(data['activity_id'])})
        
        # Use provided coach_id if available, otherwise use activity's default_coach_id
        coach_id = data.get('default_coach_id')
        if not coach_id and activity.get('default_coach_id'):
            coach_id = str(activity['default_coach_id'])
        
        # Create schedule item
        schedule_item = {
            'center_id': ObjectId(center_id),
            'day_of_week': int(data['day_of_week']),  # Ensure it's stored as integer
            'time_slot_id': ObjectId(data['time_slot_id']),
            'activity_id': ObjectId(data['activity_id']),
            'coach_id': ObjectId(coach_id) if coach_id else None,
            'max_participants': data.get('max_participants'),
            'notes': data.get('notes', ''),
            'created_at': datetime.utcnow(),
            'created_by': ObjectId(session.get('user_id'))
        }

        center = mongo.db.centers.find_one({"_id": ObjectId(center_id)})
        
        result = mongo.db.schedules.insert_one(schedule_item)
        schedule_item['_id'] = result.inserted_id
        
        # Create classes for the next 14 days
        creator = DailyClassCreator()
        try:
            start_date = datetime.utcnow().date()
            days_ahead = 14
            created_classes = []
            
            for day_offset in range(days_ahead):
                target_date = start_date + timedelta(days=day_offset)
                # Compare numeric day of week (0=Monday, 6=Sunday)
                if target_date.weekday() == schedule_item['day_of_week']:
                    class_id = creator.create_class_from_schedule(
                        str(center['organization_id']), 
                        center, 
                        schedule_item, 
                        target_date
                    )
                    if class_id:
                        created_classes.append(str(class_id))
            
            # Convert ObjectIds to strings for response
            response_item = {
                '_id': str(schedule_item['_id']),
                'center_id': str(schedule_item['center_id']),
                'time_slot_id': str(schedule_item['time_slot_id']),
                'activity_id': str(schedule_item['activity_id']),
                'coach_id': str(schedule_item['coach_id']) if schedule_item.get('coach_id') else None,
                'day_of_week': schedule_item['day_of_week'],
                'max_participants': schedule_item['max_participants'],
                'notes': schedule_item['notes'],
                'created_classes': created_classes
            }
            
            return jsonify({
                'schedule_item': response_item,
                'created_classes': len(created_classes)
            }), 201
        finally:
            creator.close()
            
    except Exception as e:
        current_app.logger.error(f"API create schedule error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/schedule/<schedule_id>', methods=['PUT'])
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def api_update_schedule_item(center_id, schedule_id):
    """Update a schedule item"""
    try:
        data = request.get_json()
        
        # Get existing schedule item
        schedule_item = mongo.db.schedules.find_one({'_id': ObjectId(schedule_id)})
        if not schedule_item:
            return jsonify({'error': 'Schedule item not found'}), 404
        
        # Prepare update data
        update_data = {
            'updated_at': datetime.utcnow(),
            'updated_by': ObjectId(session.get('user_id'))
        }
        
        # Update allowed fields
        allowed_fields = ['activity_id', 'coach_id', 'max_participants', 'notes', 'assigned_students']
        for field in allowed_fields:
            if field in data:
                if field in ['activity_id', 'coach_id'] and data[field]:
                    update_data[field] = ObjectId(data[field])
                elif field == 'assigned_students':
                    update_data[field] = [ObjectId(student_id) for student_id in data[field] if student_id != '']
                else:
                    update_data[field] = data[field]
        
        # Update schedule item
        result = mongo.db.schedules.update_one(
            {'_id': ObjectId(schedule_id)},
            {'$set': update_data}
        )

        if result.modified_count > 0:
            print("Updating classes from schedule")
            # Create an instance of DailyClassCreator and update affected classes
            from daily_class_creator import DailyClassCreator
            creator = DailyClassCreator()
            try:
                # Extract the relevant data for class updates
                updated_classes = creator.update_class_from_schedule(
                    schedule_id,
                    coach_id=data.get('coach_id'),
                    student_ids=data.get('assigned_students', []),
                    group_ids=data.get('assigned_groups', [])
                )
                print("Updated classes: ", updated_classes)
                return jsonify({
                    'message': 'Schedule item updated successfully',
                    'updated_classes': updated_classes
                }), 200
            finally:
                creator.close()
        else:
            print("No changes made")
            return jsonify({'message': 'No changes made'}), 200
    
    except Exception as e:
        current_app.logger.error(f"API update schedule error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/schedule/<schedule_id>', methods=['DELETE'])
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def api_delete_schedule_item(center_id, schedule_id):
    """Delete a schedule item and optionally its associated future classes"""
    try:
        # Get JSON data, with a default empty dict if no data sent
        data = request.get_json() or {}
        delete_classes = data.get('delete_classes', False)
        
        # Get existing schedule item
        schedule_item = mongo.db.schedules.find_one({'_id': ObjectId(schedule_id)})
        if not schedule_item:
            return jsonify({'error': 'Schedule item not found'}), 404

        # Delete the schedule item
        mongo.db.schedules.delete_one({'_id': ObjectId(schedule_id)})
        
        if delete_classes:
            # Delete all future classes
            result = mongo.db.classes.delete_many({
                'schedule_item_id': ObjectId(schedule_id),
                'scheduled_at': {'$gte': datetime.utcnow()},
                'status': {'$in': ['scheduled', 'ongoing']}
            })
            
            return jsonify({
                'message': 'Schedule item and future classes deleted successfully',
                'affected_classes': result.deleted_count
            }), 200
        else:
            # Just remove schedule_item_id reference from future classes
            result = mongo.db.classes.update_many(
                {
                    'schedule_item_id': ObjectId(schedule_id),
                    'scheduled_at': {'$gte': datetime.utcnow()},
                    'status': {'$in': ['scheduled', 'ongoing']}
                },
                {
                    '$unset': {'schedule_item_id': ""},
                    '$set': {
                        'updated_at': datetime.utcnow(),
                        'notes': 'Original schedule item deleted'
                    }
                }
            )
            
            return jsonify({
                'message': 'Schedule item deleted. Classes preserved as independent sessions.',
                'affected_classes': result.modified_count
            }), 200

    except Exception as e:
        current_app.logger.error(f"API delete schedule error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/schedule/<schedule_id>/affected-classes', methods=['GET'])
@login_required
@role_required(['org_admin', 'coach_admin', 'coach'])
def api_get_affected_classes(center_id, schedule_id):
    """Get list of classes that would be affected by schedule deletion"""
    try:
        # Find all future classes for this schedule
        future_classes = list(mongo.db.classes.find({
            'schedule_item_id': ObjectId(schedule_id),
            'scheduled_at': {'$gte': datetime.utcnow()},
            'status': {'$in': ['scheduled', 'ongoing']}
        }).sort('scheduled_at', 1))  # Sort by date ascending
        
        # Get additional info for each class
        classes_info = []
        for class_obj in future_classes:
            # Get coach name if exists
            coach_name = "No coach assigned"
            if class_obj.get('coach_id'):
                coach = mongo.db.users.find_one({'_id': class_obj['coach_id']})
                if coach:
                    coach_name = coach.get('name', 'Unknown Coach')
            
            # Format class info
            classes_info.append({
                'id': str(class_obj['_id']),
                'title': class_obj['title'],
                'scheduled_at': class_obj['scheduled_at'].strftime('%Y-%m-%d %H:%M'),
                'coach_name': coach_name,
                'student_count': len(class_obj.get('student_ids', [])),
                'group_count': len(class_obj.get('group_ids', []))
            })
        
        return jsonify({
            'classes': classes_info,
            'total_count': len(classes_info)
        }), 200

    except Exception as e:
        current_app.logger.error(f"API get affected classes error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Time Slots Management
@web_bp.route('/api/centers/<center_id>/time-slots', methods=['GET'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_get_time_slots(center_id):
    """Get time slots for a center"""
    try:
        time_slots = list(mongo.db.time_slots.find({'center_id': ObjectId(center_id)}).sort('start_time', 1))
        
        # Convert ObjectIds and other non-serializable types
        time_slots = serialize_for_json(time_slots)
        
        return jsonify({'time_slots': time_slots}), 200
    
    except Exception as e:
        current_app.logger.error(f"API get time slots error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/time-slots', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_create_time_slot(center_id):
    """Create a new time slot"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['start_time', 'duration_minutes']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check for time slot conflicts
        start_time = data['start_time']
        duration_minutes = int(data['duration_minutes'])
        
        # Convert start time to minutes for easier comparison
        start_hours, start_mins = map(int, start_time.split(':'))
        new_start_minutes = start_hours * 60 + start_mins
        new_end_minutes = new_start_minutes + duration_minutes
        
        # Get existing time slots for this center
        existing_slots = list(mongo.db.time_slots.find({'center_id': ObjectId(center_id)}))
        
        # Check for conflicts
        for existing_slot in existing_slots:
            existing_start_time = existing_slot['start_time']
            existing_duration = existing_slot.get('duration_minutes', 60)
            
            # Convert existing slot to minutes
            existing_hours, existing_mins = map(int, existing_start_time.split(':'))
            existing_start_minutes = existing_hours * 60 + existing_mins
            existing_end_minutes = existing_start_minutes + existing_duration
            
            # Check for overlap: (StartA < EndB) and (EndA > StartB)
            if new_start_minutes < existing_end_minutes and new_end_minutes > existing_start_minutes:
                return jsonify({
                    'error': f'Time slot conflicts with existing slot: {existing_start_time} ({existing_duration} min)'
                }), 400
        
        # Create time slot
        time_slot = {
            'center_id': ObjectId(center_id),
            'start_time': data['start_time'],
            'duration_minutes': int(data['duration_minutes']),
            'break_minutes': int(data.get('break_minutes', 0)),
            'name': data.get('name', f"{data['start_time']} ({data['duration_minutes']} min)"),
            'created_at': datetime.utcnow(),
            'created_by': ObjectId(session.get('user_id'))
        }
        
        result = mongo.db.time_slots.insert_one(time_slot)
        
        # Convert ObjectIds to strings for JSON serialization
        time_slot['_id'] = str(result.inserted_id)
        time_slot['center_id'] = str(time_slot['center_id'])
        time_slot['created_by'] = str(time_slot['created_by'])
        
        return jsonify({'time_slot': time_slot}), 201
    
    except Exception as e:
        current_app.logger.error(f"API create time slot error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>/time-slots/<slot_id>', methods=['DELETE'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_delete_time_slot(center_id, slot_id):
    """Delete a time slot"""
    try:
        # Check if time slot is being used in schedule
        schedule_count = mongo.db.schedules.count_documents({'time_slot_id': ObjectId(slot_id)})
        if schedule_count > 0:
            return jsonify({'error': f'Cannot delete time slot. It is being used in {schedule_count} schedule items.'}), 400
        
        result = mongo.db.time_slots.delete_one({'_id': ObjectId(slot_id)})
        
        if result.deleted_count > 0:
            return jsonify({'message': 'Time slot deleted successfully'}), 200
        else:
            return jsonify({'error': 'Time slot not found'}), 404
    
    except Exception as e:
        current_app.logger.error(f"API delete time slot error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Activities Management
@web_bp.route('/api/organizations/<org_id>/activities', methods=['GET'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_get_activities(org_id):
    """Get activities for an organization"""
    try:
        activities = list(mongo.db.activities.find({'organization_id': ObjectId(org_id)}))
        
        # Convert ObjectIds to strings
        for activity in activities:
            activity['_id'] = str(activity['_id'])
            activity['organization_id'] = str(activity['organization_id'])
            activity['created_by'] = str(activity['created_by'])
            activity['default_coach_id'] = str(activity['default_coach_id'])

        print(activities)
        
        return jsonify({'activities': activities}), 200
    
    except Exception as e:
        current_app.logger.error(f"API get activities error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/organizations/<org_id>/activities', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_create_activity(org_id):
    """Create a new activity"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        print(data)
        # Create activity
        activity = {
            'organization_id': ObjectId(org_id),
            'name': data['name'],
            'default_coach_id': ObjectId(data['default_coach_id']) if data.get('default_coach_id') else None,
            'description': data.get('description', ''),
            'duration_minutes': int(data.get('duration_minutes', 60)),
            'max_participants': int(data.get('max_participants', 20)),
            'required_equipment': data.get('required_equipment', []),
            'skill_level': data.get('skill_level', 'beginner'),
            'color': data.get('color', '#3B82F6'),
            'is_active': data.get('is_active', True),
            'created_at': datetime.utcnow(),
            'created_by': ObjectId(session.get('user_id')),
            'price': float(data.get('price', 0)),
            'feedback_metrics': data.get('feedback_metrics', [])

        }
        
        result = mongo.db.activities.insert_one(activity)
        
        # Convert ObjectIds to strings for JSON serialization
        activity['_id'] = str(result.inserted_id)
        activity['organization_id'] = str(activity['organization_id'])
        activity['created_by'] = str(activity['created_by'])
        activity['price'] = str(activity['price'])
        activity['default_coach_id'] = str(activity['default_coach_id'])
        
        return jsonify({'activity': activity}), 201
    
    except Exception as e:
        current_app.logger.error(f"API create activity error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/organizations/<org_id>/activities/<activity_id>', methods=['PUT'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_update_activity(org_id, activity_id):
    """Update an existing activity"""
    try:
        # Check permissions
        user_org_id = session.get('organization_id')
        if str(user_org_id) != org_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Activity name is required'}), 400
        
        # Build update document
        update_data = {
            'name': data['name'],
            'description': data.get('description', ''),
            'duration_minutes': int(data.get('duration_minutes', 60)),
            'max_participants': int(data.get('max_participants', 20)),
            'required_equipment': data.get('required_equipment', []),
            'skill_level': data.get('skill_level', 'beginner'),
            'color': data.get('color', '#3B82F6'),
            'is_active': data.get('is_active', True),
            'price': float(data.get('price', 0)),
            'feedback_metrics': data.get('feedback_metrics', []),
            'updated_at': datetime.utcnow()
        }
        
        # Update default_coach_id if provided
        if data.get('default_coach_id'):
            update_data['default_coach_id'] = ObjectId(data['default_coach_id'])
        
        # Update activity
        result = mongo.db.activities.update_one(
            {
                '_id': ObjectId(activity_id),
                'organization_id': ObjectId(org_id)
            },
            {'$set': update_data}
        )
        
        if result.matched_count > 0:
            # Fetch updated activity
            activity = mongo.db.activities.find_one({
                '_id': ObjectId(activity_id),
                'organization_id': ObjectId(org_id)
            })
            
            # Convert ObjectIds to strings for JSON serialization
            activity['_id'] = str(activity['_id'])
            activity['organization_id'] = str(activity['organization_id'])
            if activity.get('created_by'):
                activity['created_by'] = str(activity['created_by'])
            if activity.get('default_coach_id'):
                activity['default_coach_id'] = str(activity['default_coach_id'])
            
            return jsonify({'activity': activity, 'message': 'Activity updated successfully'}), 200
        else:
            return jsonify({'error': 'Activity not found'}), 404
    
    except Exception as e:
        current_app.logger.error(f"Update activity error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/organizations/<org_id>/activities/<activity_id>', methods=['DELETE'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_delete_activity(org_id, activity_id):
    """Delete activity"""
    try:
        # Check permissions
        user_org_id = session.get('organization_id')
        if str(user_org_id) != org_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if activity is used in any schedules
        schedules_using_activity = mongo.db.schedules.count_documents({'activity_id': ObjectId(activity_id)})
        if schedules_using_activity > 0:
            return jsonify({'error': f'Cannot delete activity. It is currently used in {schedules_using_activity} schedule(s). Please remove it from all schedules first.'}), 400
        
        # Delete activity
        result = mongo.db.activities.delete_one({
            '_id': ObjectId(activity_id),
            'organization_id': ObjectId(org_id)
        })
        
        if result.deleted_count > 0:
            return jsonify({'success': True, 'message': 'Activity deleted successfully'}), 200
        else:
            return jsonify({'error': 'Activity not found or already deleted'}), 404
    
    except Exception as e:
        current_app.logger.error(f"Delete activity error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Centers CRUD Operations
@web_bp.route('/centers/create', methods=['POST'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def create_center():
    """Create new center"""
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        street = request.form.get('street', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        facilities_str = request.form.get('facilities', '').strip()
        activities_str = request.form.get('activities', '').strip()
        
        # Basic validation
        if not name:
            flash('Center name is required.', 'error')
            return redirect(url_for('web.centers'))
        
        # Parse facilities
        facilities = [f.strip() for f in facilities_str.split(',') if f.strip()] if facilities_str else []
        
        # Get organization ID
        org_id = session.get('organization_id')
        if not org_id:
            flash('Organization not found.', 'error')
            return redirect(url_for('web.centers'))
        
        # Create center
        center_data = {
            'name': name,
            'organization_id': ObjectId(org_id),
            'contact_info': {
                'phone': contact_phone,
                'email': contact_email
            },
            'address': {
                'street': street,
                'city': city,
                'state': state
            },
            'facilities': facilities,
            'coaches': [],
            'is_active': True,
            'created_at': datetime.utcnow(),
            'created_by': ObjectId(session.get('user_id'))
        }
        
        result = mongo.db.centers.insert_one(center_data)
        
        flash(f'Center "{name}" created successfully!', 'success')
        return redirect(url_for('web.centers'))
    
    except Exception as e:
        current_app.logger.error(f"Create center error: {str(e)}")
        flash('An error occurred while creating the center.', 'error')
        return redirect(url_for('web.centers'))

@web_bp.route('/api/centers/<center_id>')
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_get_center(center_id):
    """API endpoint to get center data for editing"""
    try:
        center = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center:
            return jsonify({'error': 'Center not found'}), 404
        
        # Check permissions
        user_role = session.get('role')
        if user_role in ['org_admin', 'coach_admin']:
            org_id = session.get('organization_id')
            if str(center.get('organization_id')) != org_id:
                return jsonify({'error': 'Permission denied'}), 403
        
        # Convert ObjectId to string
        center['_id'] = str(center['_id'])
        center['organization_id'] = str(center['organization_id'])
        center['created_by'] = str(center['created_by'])
        center['updated_by'] = str(center['updated_by'])
        
        # Get coach count and class count
        center['coach_count'] = len(center.get('coaches', []))
        center['class_count'] = 0  # Placeholder for now

        print(center)
        
        return jsonify(center), 200
    
    except Exception as e:
        current_app.logger.error(f"API get center error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>', methods=['PUT'])
@login_required
@role_required(['org_admin', 'coach_admin'])
def api_update_center(center_id):
    """Update center details"""
    try:
        data = request.get_json()
        
        # Basic validation
        if not data.get('name'):
            return jsonify({'error': 'Center name is required'}), 400
        
        # Get current center to verify ownership
        center = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center:
            return jsonify({'error': 'Center not found'}), 404
        
        # Check permissions
        org_id = session.get('organization_id')
        if str(center.get('organization_id')) != org_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update data
        update_data = {
            'name': data['name'].strip(),
            'contact_info': {
                'phone': data.get('contact_phone', '').strip(),
                'email': data.get('contact_email', '').strip()
            },
            'address': {
                'street': data.get('street', '').strip(),
                'city': data.get('city', '').strip(),
                'state': data.get('state', '').strip()
            },
            'facilities': [f.strip() for f in data.get('facilities', '').split(',') if f.strip()] if data.get('facilities') else [],
            'updated_at': datetime.utcnow(),
            'updated_by': ObjectId(session.get('user_id'))
        }
        
        # Update center
        result = mongo.db.centers.update_one(
            {'_id': ObjectId(center_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': 'Center updated successfully'}), 200
        else:
            return jsonify({'error': 'No changes made'}), 400
    
    except Exception as e:
        current_app.logger.error(f"Update center error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@web_bp.route('/api/centers/<center_id>', methods=['DELETE'])
@login_required
@role_required(['org_admin'])
def api_delete_center(center_id):
    """Delete center"""
    try:
        # Get center to verify ownership
        center = mongo.db.centers.find_one({'_id': ObjectId(center_id)})
        if not center:
            return jsonify({'error': 'Center not found'}), 404
        
        # Check permissions
        org_id = session.get('organization_id')
        if str(center.get('organization_id')) != org_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if center has active schedules
        active_schedules = mongo.db.schedules.count_documents({'center_id': ObjectId(center_id)})
        if active_schedules > 0:
            return jsonify({'error': 'Cannot delete center with active schedules. Please remove all schedules first.'}), 400
        
        # Delete center
        result = mongo.db.centers.delete_one({'_id': ObjectId(center_id)})
        
        if result.deleted_count > 0:
            # Also clean up any related time slots
            mongo.db.time_slots.delete_many({'center_id': ObjectId(center_id)})
            
            return jsonify({'success': True, 'message': 'Center deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete center'}), 400
    
    except Exception as e:
        current_app.logger.error(f"Delete center error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@web_bp.route('/create_holiday', methods=['POST'])
@login_required
@role_required(['org_admin'])
def create_holiday():
    """Create a holiday"""
    data = request.form
    print(data)
    data = dict(data)
    data['date_observed'] = datetime.strptime(data['start_date'], '%Y-%m-%d')
    # Use same logic as class_cancellation.py
    schema = HolidaySchema()
    schema.name = data['name']
    schema.date_observed = data['date_observed']
    schema.description = data['description']
    schema.affects_scheduling = True

    
    # Import auth utilities
    from app.utils.auth import get_current_user_info
    user_info = get_current_user_info()
    
    if not user_info:
        return jsonify({'error': 'Authentication required'}), 401
        
    organization_id = user_info.get('organization_id')
    current_user_id = user_info.get('user_id')

    print(organization_id)
    print(current_user_id)
    
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

    print(result)

    result['master_holiday']['_id'] = str(result['master_holiday']['_id'])
    if result['org_holiday']:

        result['org_holiday']['_id'] = str(result['org_holiday']['_id'])
        if result['org_holiday']:
            if 'holiday_id' in result['org_holiday']:
                result['org_holiday']['holiday_id'] = str(result['org_holiday']['holiday_id'])
        if 'organization_id' in result['org_holiday']:
            result['org_holiday']['organization_id'] = str(result['org_holiday']['organization_id'])
        if 'created_by' in result['org_holiday']:
            result['org_holiday']['created_by'] = str(result['org_holiday']['created_by'])
        if 'updated_by' in result['org_holiday']:
            result['org_holiday']['updated_by'] = str(result['org_holiday']['updated_by'])
        if 'holiday_id' in result['org_holiday']:
            result['org_holiday']['holiday_id'] = str(result['org_holiday']['holiday_id'])
        if 'holiday_name' in result['org_holiday']:
            result['org_holiday']['holiday_name'] = str(result['org_holiday']['holiday_name'])
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': 'Holiday created successfully',
            'holiday': result['master_holiday'],
            'org_holiday': result['org_holiday']
        }), 201
    else:
        return jsonify({'error': result['error']}), 400


@web_bp.route('/signup-classes/<link_token>')
def signup_classes(link_token):
    try:
        # Get the activity link from the database
        sign_up_link = mongo.db.activity_links.find_one({'link_token': link_token})
        if not sign_up_link:
            flash('Invalid or expired link', 'error')
            return redirect(url_for('web.classes'))
        
        # Get the class IDs from the activity link (stored as list of ObjectIds)
        schedule_item_ids = sign_up_link.get('schedule_item_ids', [])
        if not schedule_item_ids:
            flash('No classes found in this link', 'error')
            return redirect(url_for('web.classes'))
        
        # Convert ObjectIds to strings and get class info
        classes = []
        class_id_strings = []
        
        for schedule_item_id in schedule_item_ids:
            class_id_str = str(schedule_item_id)
            class_id_strings.append(class_id_str)
            class_info = get_class_info(class_id_str)
            if class_info:
                classes.append(class_info)
        
        if not classes:
            flash('No valid classes found', 'error')
            return redirect(url_for('web.classes'))
        
        # Convert list to comma-separated string for form submission
        class_ids = ','.join(class_id_strings)
        print(f"DEBUG: Passing class_ids to template: {class_ids}")
        
        return render_template('signup_classes.html', 
                             classes=classes,
                             class_ids=class_ids,
                             link_token=link_token)
    
    except Exception as e:
        flash('Error loading class information', 'error')
        return redirect(url_for('web.classes'))

@web_bp.route('/signup-classes/<link_token>/submit', methods=['POST'])
def signup_classes_submit(link_token):
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        class_ids = request.form.get('class_ids')
        
        print(f"DEBUG: Received form data - name: {name}, phone: {phone}, class_ids: {class_ids}")
        
        # Validate class_ids
        if not class_ids:
            flash('No classes selected', 'error')
            return redirect(url_for('web.classes'))
        
        # Validate the link token
        sign_up_link = mongo.db.activity_links.find_one({'link_token': link_token})
        if not sign_up_link:
            flash('Invalid or expired link', 'error')
            return redirect(url_for('web.classes'))
        
        # Validate required fields
        if not name or not phone:
            flash('Name and phone number are required', 'error')
            return redirect(url_for('web.signup_classes', link_token=link_token))
        
        import re
        # Validate phone number (10 digits)
        phone = re.sub(r'\D', '', phone)  # Remove non-digits
        if not re.match(r'^\d{10}$', phone):
            flash('Phone number must be 10 digits', 'error')
            return redirect(url_for('web.signup_classes', link_token=link_token))
        
        # Validate email format if provided
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Invalid email format', 'error')
            return redirect(url_for('web.signup_classes', link_token=link_token))
        
        # Check if user already exists by phone number
        existing_user = mongo.db.users.find_one({'phone_number': phone})
        
        if existing_user:
            # User exists, use existing account
            user = existing_user
            print(user)
            user_id = user['_id']
            
            # Update name and email if provided and different
            update_fields = {}
            if name and user.get('name') != name:
                update_fields['name'] = name
            if email and user.get('email') != email:
                update_fields['email'] = email
            
            if update_fields:
                mongo.db.users.update_one(
                    {'_id': user_id},
                    {'$set': update_fields}
                )
        else:
            # Create new user
            auth_service = AuthService()
            # Generate a random password for the user
            import random
            import string
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            
        
            user = auth_service.register_user(phone, name, random_password, 'student', ObjectId(sign_up_link['organization_id']), None, email)
            
            if not user:
                flash('Failed to create user account', 'error')
                return redirect(url_for('web.signup_classes', link_token=link_token))
            
            user = user[0]['user']
            print(user)
            user_id = user['_id']
        
        # Convert user_id to ObjectId if it's not already
        if not isinstance(user_id, ObjectId):
            user_id = ObjectId(user_id)
        
        schedule_item_ids = sign_up_link['schedule_item_ids']

        schedule_item = mongo.db.schedules.find_one({'_id': ObjectId(schedule_item_ids[0])})
        center_id = schedule_item['center_id']

        center_doc = mongo.db.centers.find_one({'_id': ObjectId(center_id)})

        # Add user to classes
        class_id_list = class_ids.split(',')
        enrolled_count = 0

        class_names = ''
        
        for class_id in class_id_list:
            try:
                class_doc = mongo.db.schedules.find_one({'_id': ObjectId(class_id)})
                print('class_doc1', class_doc)
                if not class_doc:
                    continue

                activity_id = class_doc.get('activity_id')
                activity_doc = mongo.db.activities.find_one({'_id': activity_id})
                activity_name = activity_doc.get('name')
                
                # Check if user is already enrolled
                if user_id in class_doc.get('assigned_students', []):
                    enrolled_count += 1
                    continue
                
                # Check class capacity
                current_students = len(class_doc.get('assigned_students', []))
                max_students = class_doc.get('max_participants')
                if max_students and current_students >= max_students:
                    
                    flash(f'Class {activity_name} is full', 'warning')
                    continue
                
                # Add user to organization if not already a member
                if 'organization_id' in class_doc:
                    org_id = class_doc['organization_id']
                    org = mongo.db.organizations.find_one({'_id': org_id})
                    if org and str(user_id) not in [str(uid) for uid in org.get('members', [])]:
                        mongo.db.organizations.update_one(
                            {'_id': org_id},
                            {'$addToSet': {'members': user_id}}
                        )
                
                # Add user to class
                mongo.db.schedules.update_one(
                    {'_id': ObjectId(class_id)},
                    {'$addToSet': {'assigned_students': user_id}}
                )
                print('class_doc', class_doc)
                class_names += activity_name + ', '
                enrolled_count += 1

    
                
            except Exception as e:
                traceback.print_exc()
                print(f'Error enrolling in class {class_id}: {str(e)}')
                return redirect(url_for('web.signup_classes', link_token=link_token))

        class_names = class_names[:-2]

        # enhanced_whatsapp_service = EnhancedWhatsAppService()
        # try:
        #     enhanced_whatsapp_service.send_added_to_class_message(phone, name, class_names, center_doc['name'])
        # except Exception as e:
        #     print(f'Error sending added to class message: {str(e)}')
        
        # Redirect to download app page
        return redirect(url_for('web.download_app', phone=phone))
        
    except Exception as e:
        traceback.print_exc()
        flash('Error processing registration: ' + str(e), 'error')
        return redirect(url_for('web.signup_classes', link_token=link_token))

@web_bp.route('/download-app')
def download_app():
    """Display download app page after successful registration"""
    phone = request.args.get('phone', '')
    return render_template('download_app.html', user_phone=phone)
    
@web_bp.route('/generate-activity-link', methods=['POST'])
@login_required
def generate_activity_link():
    try:
        schedule_item_ids = request.json.get('schedule_item_ids', [])
        if not schedule_item_ids:
            return jsonify({'error': 'No schedule items selected'}), 400

        # Get current user and organization
        user_info = get_user_info_from_session_or_claims()
        if not user_info:
            return jsonify({'error': 'Authentication required'}), 401
        
        organization_id = user_info.get('organization_id')
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400

        # Generate unique token
        link_token = secrets.token_urlsafe(16)

        schedule_item_object_ids = []
        for schedule_item_id in schedule_item_ids:
            schedule_item_object_ids.append(ObjectId(schedule_item_id))
        
        # Create activity link
        activity_link = ActivityLink(
            _id=ObjectId(),
            schedule_item_ids=schedule_item_object_ids,
            organization_id=ObjectId(organization_id),
            created_by=ObjectId(user_info['user_id']),
            link_token=link_token,
            status='active'
        )
        
        # Save to database
        mongo.db.activity_links.insert_one(activity_link.to_dict())
        
        # Generate full URL
        signup_url = f"{request.host_url.rstrip('/')}/signup-activities/{link_token}"
        
        return jsonify({
            'link': signup_url,
            'link_token': link_token
        }), 201
        
    except Exception as e:
        print(e)
        return jsonify({'error': 'Failed to generate link'}), 500

@web_bp.route('/signup-activities/<link_token>', methods=['GET'])
def signup_activities(link_token):
    activity_link = mongo.db.activity_links.find_one({'link_token': link_token})
    if not activity_link:
        return jsonify({'error': 'Invalid link'}), 400

    schedule_items = mongo.db.schedules.find({'_id': {'$in': activity_link['schedule_item_ids']}})
    classes = []
    for schedule_item in schedule_items:
        schedule_item['activity'] = mongo.db.activities.find_one({'_id': schedule_item['activity_id']}) 
        classes.append(schedule_item)

    class_ids = [str(class_id) for class_id in activity_link['schedule_item_ids']]
    class_ids = ','.join(class_ids)
    
   
    return render_template('signup_classes.html', activity_link=activity_link, classes=classes, class_ids=class_ids, link_token=link_token)