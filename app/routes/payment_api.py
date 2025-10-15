from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.payments import Payment
from decimal import Decimal
from bson import ObjectId
from datetime import datetime

payment_api_bp = Blueprint('payment_api', __name__, url_prefix='/api/mobile/payments')

@payment_api_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_payment():
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        class_id = data.get('class_id')
        amount = data.get('amount')
        
        if not all([payment_id, class_id, amount]):
            return jsonify({
                'success': False,
                'message': 'Payment ID, Class ID, and amount are required'
            }), 400

        # Get user details
        user_id = get_jwt_identity()
        claims = get_jwt()
        organization_id = claims.get('organization_id')

        if not organization_id:
            return jsonify({
                'success': False,
                'message': 'User must be associated with an organization'
            }), 400

        try:
            # Create payment record
            payment = Payment(
                organization_id=ObjectId(organization_id),
                student_id=ObjectId(user_id),
                class_id=ObjectId(class_id),
                amount=Decimal(str(amount)),
                type='class_fee',
                description='Class booking payment',
                created_by=ObjectId(user_id)
            )

            # Verify payment with Razorpay
            payment_details = Payment.verify_razorpay_payment(payment_id, payment.amount)
            
            # Record payment details
            payment.record_razorpay_payment(payment_details)
            
            # Save payment to database
            result = mongo.db.payments.insert_one(payment.to_dict())
            payment._id = result.inserted_id

            # Update class enrollment
            mongo.db.classes.update_one(
                {'_id': ObjectId(class_id)},
                {
                    '$push': {'enrolled_students': ObjectId(user_id)},
                    '$inc': {'student_count': 1}
                }
            )

            return jsonify({
                'success': True,
                'message': 'Payment verified and booking confirmed',
                'payment': payment.to_dict()
            })

        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Internal server error: {str(e)}'
        }), 500

@payment_api_bp.route('/history', methods=['GET'])
@jwt_required()
def get_payment_history():
    try:
        user_id = get_jwt_identity()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page

        # Build query
        query = {'student_id': ObjectId(user_id)}
        
        # Get payments
        payments_cursor = mongo.db.payments.find(query) \
            .sort('created_at', -1) \
            .skip(skip) \
            .limit(per_page)
        
        payments = [Payment.from_dict(p).to_dict() for p in payments_cursor]
        total = mongo.db.payments.count_documents(query)

        return jsonify({
            'success': True,
            'payments': payments,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching payment history: {str(e)}'
        }), 500