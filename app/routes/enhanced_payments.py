from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.payments import Payment
from app.models.user import User
from app.services.enhanced_payment_service import EnhancedPaymentService
from app.routes.auth import require_role
from app.routes.web import login_required, role_required
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, date
from bson import ObjectId
import json

enhanced_payments_bp = Blueprint('enhanced_payments', __name__, url_prefix='/api/enhanced-payments')

# Enhanced schemas
class CreateEnhancedPaymentSchema(Schema):
    student_id = fields.Str(required=True)
    amount = fields.Float(required=True, validate=lambda x: x > 0)
    description = fields.Str(required=True)
    due_date = fields.Date(required=True)
    payment_type = fields.Str(required=False, missing='monthly')
    payment_category = fields.Str(required=False, missing='tuition')
    tax_amount = fields.Float(required=False, missing=0.0)
    gateway = fields.Str(required=False, missing='razorpay')
    group_id = fields.Str(required=False)
    payment_instructions = fields.Str(required=False)

class ProcessManualPaymentSchema(Schema):
    amount = fields.Float(required=True, validate=lambda x: x > 0)
    payment_method = fields.Str(required=True)
    reference = fields.Str(required=True)
    notes = fields.Str(required=False)

class CreatePaymentPlanSchema(Schema):
    student_id = fields.Str(required=True)
    plan_name = fields.Str(required=True)
    amount_per_cycle = fields.Float(required=True, validate=lambda x: x > 0)
    cycle_type = fields.Str(required=False, missing='monthly')
    start_date = fields.Date(required=False)
    end_date = fields.Date(required=False)
    gateway = fields.Str(required=False, missing='razorpay')

class BulkPaymentSchema(Schema):
    payments = fields.List(fields.Nested(CreateEnhancedPaymentSchema), required=True, validate=lambda x: len(x) > 0)

@enhanced_payments_bp.route('/create', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def create_enhanced_payment():
    """Create enhanced payment with gateway integration"""
    try:
        schema = CreateEnhancedPaymentSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_id = get_jwt_identity()
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        payment_service = EnhancedPaymentService()
        
        success, message, payment = payment_service.create_payment_with_gateway(
            student_id=data['student_id'],
            organization_id=organization_id,
            amount=data['amount'],
            description=data['description'],
            due_date=data['due_date'],
            payment_type=data['payment_type'],
            gateway=data['gateway'],
            payment_category=data['payment_category'],
            tax_amount=data['tax_amount'],
            payment_instructions=data.get('payment_instructions'),
            created_by=user_id
        )
        
        if success:
            return jsonify({
                'message': message,
                'payment': payment.to_dict(),
                'payment_link': payment.payment_link
            }), 201
        else:
            return jsonify({'error': message}), 400
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/bulk-create', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def create_bulk_payments():
    """Create multiple payments in bulk"""
    try:
        schema = BulkPaymentSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_id = get_jwt_identity()
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        payment_service = EnhancedPaymentService()
        
        success, message, results = payment_service.create_bulk_payments(
            organization_id=organization_id,
            payment_data=data['payments'],
            created_by=user_id
        )
        
        if success:
            return jsonify({
                'message': message,
                'results': results
            }), 201
        else:
            return jsonify({'error': message, 'results': results}), 400
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/<payment_id>/process-manual', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin', 'coach'])
def process_manual_payment(payment_id):
    """Process payment manually (cash/bank transfer)"""
    try:
        schema = ProcessManualPaymentSchema()
        data = schema.load(request.json)
        
        user_id = get_jwt_identity()
        
        payment_service = EnhancedPaymentService()
        
        success, message = payment_service.process_payment_manually(
            payment_id=payment_id,
            amount=data['amount'],
            payment_method=data['payment_method'],
            reference=data['reference'],
            marked_by=user_id,
            notes=data.get('notes')
        )
        
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/payment-plans', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def create_payment_plan():
    """Create recurring payment plan"""
    try:
        schema = CreatePaymentPlanSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        payment_service = EnhancedPaymentService()
        
        success, message, payment_plan = payment_service.setup_recurring_payment_plan(
            student_id=data['student_id'],
            organization_id=organization_id,
            plan_data=data
        )
        
        if success:
            return jsonify({
                'message': message,
                'payment_plan': payment_plan.to_dict()
            }), 201
        else:
            return jsonify({'error': message}), 400
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/reports/<report_type>', methods=['GET'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def generate_payment_report(report_type):
    """Generate payment reports"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str or not end_date_str:
            # Default to last 30 days
            from datetime import timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        payment_service = EnhancedPaymentService()
        
        report_data = payment_service.generate_payment_reports(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            report_type=report_type
        )
        
        return jsonify({
            'report_type': report_type,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data': report_data
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/analytics', methods=['GET'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def get_payment_analytics():
    """Get payment analytics for organization"""
    try:
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        days = request.args.get('days', 30, type=int)
        
        payment_service = EnhancedPaymentService()
        analytics = payment_service.generate_payment_analytics(organization_id, days)
        
        return jsonify(analytics), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/webhooks/<gateway>', methods=['POST'])
def payment_webhook(gateway):
    """Handle payment gateway webhooks"""
    try:
        payload = request.json
        signature = request.headers.get('X-Razorpay-Signature') or request.headers.get('Stripe-Signature', '')
        
        payment_service = EnhancedPaymentService()
        
        success, message = payment_service.process_gateway_webhook(
            gateway=gateway,
            payload=payload,
            signature=signature
        )
        
        if success:
            return jsonify({'status': 'success', 'message': message}), 200
        else:
            return jsonify({'status': 'error', 'message': message}), 400
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@enhanced_payments_bp.route('/<payment_id>/refund', methods=['POST'])
@jwt_required()
@require_role(['org_admin'])
def process_refund(payment_id):
    """Process payment refund"""
    try:
        data = request.json
        refund_amount = data.get('amount')
        reason = data.get('reason')
        refund_method = data.get('method')
        
        if not refund_amount or not reason:
            return jsonify({'error': 'Refund amount and reason are required'}), 400
        
        user_id = get_jwt_identity()
        
        # Get payment
        payment_data = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
        if not payment_data:
            return jsonify({'error': 'Payment not found'}), 404
        
        payment = Payment.from_dict(payment_data)
        
        # Process refund
        success = payment.process_refund(
            refund_amount=refund_amount,
            reason=reason,
            refund_method=refund_method,
            processed_by=user_id
        )
        
        if success:
            # Update in database
            mongo.db.payments.update_one(
                {'_id': payment._id},
                {'$set': payment.to_dict()}
            )
            
            return jsonify({
                'message': 'Refund processed successfully',
                'refund_amount': refund_amount,
                'new_status': payment.status
            }), 200
        else:
            return jsonify({'error': 'Cannot process refund for this payment'}), 400
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@enhanced_payments_bp.route('/<payment_id>/installments', methods=['POST'])
@jwt_required()
@require_role(['org_admin', 'center_admin'])
def create_installment_plan(payment_id):
    """Create installment plan for payment"""
    try:
        data = request.json
        installment_count = data.get('installment_count')
        start_date_str = data.get('start_date')
        
        if not installment_count or installment_count < 2:
            return jsonify({'error': 'Installment count must be at least 2'}), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        
        # Get payment
        payment_data = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
        if not payment_data:
            return jsonify({'error': 'Payment not found'}), 404
        
        payment = Payment.from_dict(payment_data)
        
        # Create installment plan
        installments = payment.create_installment_plan(installment_count, start_date)
        
        # Update in database
        mongo.db.payments.update_one(
            {'_id': payment._id},
            {'$set': payment.to_dict()}
        )
        
        return jsonify({
            'message': 'Installment plan created successfully',
            'installments': installments
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# Public payment page route (no JWT required)
@enhanced_payments_bp.route('/pay/<payment_id>', methods=['GET'])
def public_payment_page(payment_id):
    """Public payment page for students"""
    try:
        # Find payment by payment_id (not MongoDB _id)
        payment_data = mongo.db.payments.find_one({'payment_id': payment_id})
        if not payment_data:
            return "Payment not found", 404
        
        payment = Payment.from_dict(payment_data)
        
        # Get student details
        student_data = mongo.db.users.find_one({'_id': payment.student_id})
        if not student_data:
            return "Student not found", 404
        
        student = User.from_dict(student_data)
        
        # Get organization details
        org_data = mongo.db.organizations.find_one({'_id': payment.organization_id})
        org_name = org_data.get('name', 'Organization') if org_data else 'Organization'
        
        return render_template('payment_page.html', 
                             payment=payment, 
                             student=student, 
                             organization_name=org_name)
    
    except Exception as e:
        return f"Error loading payment page: {str(e)}", 500

# Web routes for payment management UI
payment_web_bp = Blueprint('payment_web', __name__)

@payment_web_bp.route('/payment-management')
@login_required
@role_required(['org_admin', 'center_admin'])
def payment_management():
    """Payment management dashboard"""
    try:
        organization_id = session.get('organization_id')
        
        # Get recent payments
        recent_payments = list(mongo.db.payments.find({
            'organization_id': ObjectId(organization_id)
        }).sort('created_at', -1).limit(10))
        
        # Add student names
        for payment in recent_payments:
            if payment.get('student_id'):
                student = mongo.db.users.find_one(
                    {'_id': ObjectId(payment['student_id'])},
                    {'name': 1}
                )
                payment['student_name'] = student.get('name') if student else 'Unknown'
        
        # Get payment statistics
        stats_pipeline = [
            {'$match': {'organization_id': ObjectId(organization_id)}},
            {
                '$group': {
                    '_id': '$status',
                    'count': {'$sum': 1},
                    'total_amount': {'$sum': '$amount'}
                }
            }
        ]
        
        payment_stats = list(mongo.db.payments.aggregate(stats_pipeline))
        
        return render_template('payment_management.html',
                             recent_payments=recent_payments,
                             payment_stats=payment_stats)
    
    except Exception as e:
        flash(f'Error loading payment management: {str(e)}', 'error')
        return redirect(url_for('web.dashboard'))

@payment_web_bp.route('/payment-reports')
@login_required
@role_required(['org_admin', 'center_admin'])
def payment_reports():
    """Payment reports page"""
    return render_template('payment_reports.html')

# Register both blueprints
def register_payment_blueprints(app):
    app.register_blueprint(enhanced_payments_bp)
    app.register_blueprint(payment_web_bp)
