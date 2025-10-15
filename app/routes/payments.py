from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.payments import Payment
from app.routes.auth import require_role
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, date
from bson import ObjectId

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

# Request schemas
class CreatePaymentSchema(Schema):
    student_id = fields.Str(required=True)
    amount = fields.Float(required=True)
    description = fields.Str(required=True)
    due_date = fields.Date(required=True)
    payment_type = fields.Str(required=False, missing='monthly')
    group_id = fields.Str(required=False)

class UpdatePaymentSchema(Schema):
    status = fields.Str(required=False, validate=lambda x: x in ['pending', 'paid', 'overdue', 'cancelled'])
    paid_amount = fields.Float(required=False)
    payment_method = fields.Str(required=False)
    payment_reference = fields.Str(required=False)
    notes = fields.Str(required=False)

@payments_bp.route('', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def create_payment():
    """Create a new payment record"""
    try:
        schema = CreatePaymentSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        organization_id = claims.get('organization_id')
        user_id = get_jwt_identity()
        
        if not organization_id:
            return jsonify({'error': 'User must be associated with an organization'}), 400
        
        # Create new payment
        new_payment = Payment(
            student_id=data['student_id'],
            organization_id=organization_id,
            amount=data['amount'],
            description=data['description'],
            due_date=data['due_date'],
            payment_type=data.get('payment_type', 'monthly'),
            group_id=data.get('group_id')
        )
        new_payment.created_by = ObjectId(user_id)
        
        result = mongo.db.payments.insert_one(new_payment.to_dict())
        new_payment._id = result.inserted_id
        
        return jsonify({
            'message': 'Payment created successfully',
            'payment': new_payment.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('', methods=['GET'])
@jwt_required()
def get_payments():
    """Get payments (filtered by user role)"""
    try:
        claims = get_jwt()
        user_role = claims.get('role')
        user_id = get_jwt_identity()
        organization_id = claims.get('organization_id')
        
        query = {}
        
        if organization_id:
            query['organization_id'] = ObjectId(organization_id)
        
        if user_role == 'student':
            # Students can only see their own payments
            query['student_id'] = ObjectId(user_id)
        
        # Get query parameters
        status = request.args.get('status')
        student_id = request.args.get('student_id')
        
        if status:
            query['status'] = status
        
        if student_id and user_role in ['admin', 'coach']:
            query['student_id'] = ObjectId(student_id)
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        # Execute query
        payments_cursor = mongo.db.payments.find(query).sort('due_date', -1).skip(skip).limit(per_page)
        payments = [Payment.from_dict(payment_data).to_dict() for payment_data in payments_cursor]
        
        # Get total count
        total = mongo.db.payments.count_documents(query)
        
        return jsonify({
            'payments': payments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('/<payment_id>/mark-paid', methods=['POST'])
@jwt_required()
@require_role(['admin', 'coach'])
def mark_payment_paid(payment_id):
    """Mark a payment as paid"""
    try:
        data = request.json or {}
        
        payment_data = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
        if not payment_data:
            return jsonify({'error': 'Payment not found'}), 404
        
        payment = Payment.from_dict(payment_data)
        user_id = get_jwt_identity()
        
        payment.mark_paid(
            amount=data.get('amount'),
            payment_method=data.get('payment_method'),
            reference=data.get('reference'),
            marked_by=user_id,
            notes=data.get('notes')
        )
        
        mongo.db.payments.update_one(
            {'_id': ObjectId(payment_id)},
            {'$set': payment.to_dict()}
        )
        
        return jsonify({
            'message': 'Payment marked as paid',
            'payment': payment.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 