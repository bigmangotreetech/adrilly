from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from app.extensions import mongo
from app.models.payments import Payment, PaymentPlan
from app.models.user import User
from app.models.organization import Organization
from bson import ObjectId
import requests
import hashlib
import hmac
import os
from flask import current_app
import json

class EnhancedPaymentService:
    """Enhanced payment service with gateway integration and comprehensive features"""
    
    def __init__(self):
        # Gateway configurations
        self.razorpay_enabled = bool(os.getenv('RAZORPAY_KEY_ID'))
        self.stripe_enabled = bool(os.getenv('STRIPE_PUBLISHABLE_KEY'))
        
        # Initialize gateways if configured
        if self.razorpay_enabled:
            import razorpay
            self.razorpay_client = razorpay.Client(
                auth=(os.getenv('RAZORPAY_KEY_ID'), os.getenv('RAZORPAY_KEY_SECRET'))
            )
        
        if self.stripe_enabled:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            self.stripe = stripe
    
    def create_payment_with_gateway(self, student_id: ObjectId, organization_id: ObjectId, amount: float,
                                   description: str, due_date: date, payment_type: str = 'monthly',
                                   gateway: str = 'razorpay', **kwargs) -> Tuple[bool, str, Optional[Payment]]:
        """Create payment record with gateway integration"""
        try:
            # Create payment record
            payment = Payment(
                student_id=student_id,
                organization_id=organization_id,
                amount=amount,
                description=description,
                due_date=due_date,
                payment_type=payment_type
            )
            
            # Set additional fields
            payment.payment_category = kwargs.get('payment_category', 'tuition')
            payment.tax_amount = kwargs.get('tax_amount', 0.0)
            payment.payment_instructions = kwargs.get('payment_instructions')
            
            # Convert organization_id to ObjectId if it's a string
            org_id_obj = ObjectId(organization_id) if isinstance(organization_id, str) else organization_id
            
            # Generate invoice number
            org_data = mongo.db.organizations.find_one({'_id': org_id_obj})
            org_prefix = org_data.get('invoice_prefix', 'INV') if org_data else 'INV'
            payment.generate_invoice_number(org_prefix)
            
            # Create gateway order if online payment
            if gateway and gateway != 'cash':
                gateway_success, gateway_result = self._create_gateway_order(payment, gateway)
                if not gateway_success:
                    return False, f"Gateway error: {gateway_result}", None
                
                payment.gateway_payment_id = gateway_result.get('id')
                payment.gateway_status = 'created'
            
            # Save payment
            result = mongo.db.payments.insert_one(payment.to_dict())
            payment._id = result.inserted_id
            
            # Generate payment link
            base_url = os.getenv('BASE_URL', 'https://adrilly.com')
            payment.generate_payment_link(base_url)
            
            # Update payment with link
            mongo.db.payments.update_one(
                {'_id': payment._id},
                {'$set': {'payment_link': payment.payment_link}}
            )
            
            payment.add_audit_entry('payment_created', {
                'gateway': gateway,
                'amount': amount,
                'created_by': kwargs.get('created_by')
            })
            
            return True, f"Payment created successfully", payment
            
        except Exception as e:
            current_app.logger.error(f"Error creating payment: {str(e)}")
            return False, str(e), None
    
    def process_gateway_webhook(self, gateway: str, payload: Dict, signature: str) -> Tuple[bool, str]:
        """Process payment gateway webhook"""
        try:
            if gateway == 'razorpay':
                return self._process_razorpay_webhook(payload, signature)
            elif gateway == 'stripe':
                return self._process_stripe_webhook(payload, signature)
            else:
                return False, "Unsupported gateway"
                
        except Exception as e:
            current_app.logger.error(f"Error processing {gateway} webhook: {str(e)}")
            return False, str(e)
    
    def generate_payment_reports(self, organization_id: str, start_date: date, 
                               end_date: date, report_type: str = 'summary') -> Dict:
        """Generate comprehensive payment reports"""
        try:
            match_query = {
                'organization_id': ObjectId(organization_id),
                'created_at': {
                    '$gte': datetime.combine(start_date, datetime.min.time()),
                    '$lte': datetime.combine(end_date, datetime.max.time())
                }
            }
            
            if report_type == 'summary':
                return self._generate_summary_report(match_query)
            elif report_type == 'detailed':
                return self._generate_detailed_report(match_query)
            elif report_type == 'analytics':
                return self._generate_analytics_report(match_query)
            else:
                return {'error': 'Invalid report type'}
                
        except Exception as e:
            current_app.logger.error(f"Error generating payment report: {str(e)}")
            return {'error': str(e)}
    
    def create_bulk_payments(self, organization_id: str, payment_data: List[Dict],
                           created_by: str) -> Tuple[bool, str, Dict]:
        """Create multiple payments in bulk"""
        try:
            results = {
                'successful': [],
                'failed': [],
                'total': len(payment_data)
            }
            
            for data in payment_data:
                try:
                    success, message, payment = self.create_payment_with_gateway(
                        student_id=data['student_id'],
                        organization_id=organization_id,
                        amount=data['amount'],
                        description=data['description'],
                        due_date=data['due_date'],
                        payment_type=data.get('payment_type', 'monthly'),
                        gateway=data.get('gateway', 'cash'),
                        created_by=created_by
                    )
                    
                    if success:
                        results['successful'].append({
                            'student_id': data['student_id'],
                            'payment_id': payment.payment_id,
                            'amount': payment.amount
                        })
                    else:
                        results['failed'].append({
                            'student_id': data['student_id'],
                            'error': message
                        })
                        
                except Exception as e:
                    results['failed'].append({
                        'student_id': data.get('student_id', 'unknown'),
                        'error': str(e)
                    })
            
            success_count = len(results['successful'])
            total_count = results['total']
            
            return True, f"Created {success_count}/{total_count} payments", results
            
        except Exception as e:
            current_app.logger.error(f"Error creating bulk payments: {str(e)}")
            return False, str(e), {}
    
    def setup_recurring_payment_plan(self, student_id: str, organization_id: str,
                                   plan_data: Dict) -> Tuple[bool, str, Optional[PaymentPlan]]:
        """Set up recurring payment plan"""
        try:
            payment_plan = PaymentPlan(
                student_id=student_id,
                organization_id=organization_id,
                plan_name=plan_data['plan_name'],
                amount_per_cycle=plan_data['amount_per_cycle'],
                cycle_type=plan_data.get('cycle_type', 'monthly'),
                start_date=plan_data.get('start_date'),
                end_date=plan_data.get('end_date')
            )
            
            # Save payment plan
            result = mongo.db.payment_plans.insert_one(payment_plan.to_dict())
            payment_plan._id = result.inserted_id
            
            # Generate first payment if needed
            if plan_data.get('create_first_payment', True):
                first_payment_success, first_payment_message, first_payment = self.create_payment_with_gateway(
                    student_id=student_id,
                    organization_id=organization_id,
                    amount=payment_plan.amount_per_cycle,
                    description=f"{plan_data['plan_name']} - First Payment",
                    due_date=payment_plan.start_date,
                    payment_type='recurring',
                    gateway=plan_data.get('gateway', 'razorpay')
                )
                
                if first_payment_success:
                    first_payment.recurring_payment_id = str(payment_plan._id)
                    mongo.db.payments.update_one(
                        {'_id': first_payment._id},
                        {'$set': {'recurring_payment_id': str(payment_plan._id)}}
                    )
            
            return True, f"Payment plan created successfully", payment_plan
            
        except Exception as e:
            current_app.logger.error(f"Error creating payment plan: {str(e)}")
            return False, str(e), None
    
    def process_payment_manually(self, payment_id: str, amount: float, payment_method: str,
                               reference: str, marked_by: str, notes: str = None) -> Tuple[bool, str]:
        """Process payment manually (for cash/bank transfers)"""
        try:
            payment_data = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
            if not payment_data:
                return False, "Payment not found"
            
            payment = Payment.from_dict(payment_data)
            
            # Mark as paid
            payment.mark_paid(
                amount=amount,
                payment_method=payment_method,
                reference=reference,
                marked_by=marked_by,
                notes=notes
            )
            
            payment.add_audit_entry('manual_payment_processed', {
                'amount': amount,
                'method': payment_method,
                'reference': reference,
                'marked_by': marked_by
            })
            
            # Update in database
            mongo.db.payments.update_one(
                {'_id': payment._id},
                {'$set': payment.to_dict()}
            )
            
            return True, f"Payment marked as paid"
            
        except Exception as e:
            current_app.logger.error(f"Error processing manual payment: {str(e)}")
            return False, str(e)
    
    def generate_payment_analytics(self, organization_id: str, days: int = 30) -> Dict:
        """Generate payment analytics for organization"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Payment status distribution
            status_pipeline = [
                {
                    '$match': {
                        'organization_id': ObjectId(organization_id),
                        'created_at': {'$gte': start_date}
                    }
                },
                {
                    '$group': {
                        '_id': '$status',
                        'count': {'$sum': 1},
                        'total_amount': {'$sum': '$amount'}
                    }
                }
            ]
            
            status_stats = list(mongo.db.payments.aggregate(status_pipeline))
            
            # Payment method distribution
            method_pipeline = [
                {
                    '$match': {
                        'organization_id': ObjectId(organization_id),
                        'status': 'paid',
                        'paid_date': {'$gte': start_date}
                    }
                },
                {
                    '$group': {
                        '_id': '$payment_method',
                        'count': {'$sum': 1},
                        'total_amount': {'$sum': '$paid_amount'}
                    }
                }
            ]
            
            method_stats = list(mongo.db.payments.aggregate(method_pipeline))
            
            # Monthly trends
            monthly_pipeline = [
                {
                    '$match': {
                        'organization_id': ObjectId(organization_id),
                        'created_at': {'$gte': start_date - timedelta(days=365)}  # Last year
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'year': {'$year': '$created_at'},
                            'month': {'$month': '$created_at'}
                        },
                        'total_amount': {'$sum': '$amount'},
                        'paid_amount': {'$sum': '$paid_amount'},
                        'payment_count': {'$sum': 1}
                    }
                },
                {'$sort': {'_id.year': 1, '_id.month': 1}}
            ]
            
            monthly_trends = list(mongo.db.payments.aggregate(monthly_pipeline))
            
            # Overdue analysis
            overdue_pipeline = [
                {
                    '$match': {
                        'organization_id': ObjectId(organization_id),
                        'status': {'$in': ['pending', 'overdue']},
                        'due_date': {'$lt': datetime.utcnow().date()}
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'count': {'$sum': 1},
                        'total_amount': {'$sum': '$amount'},
                        'total_late_fees': {'$sum': '$late_fee'}
                    }
                }
            ]
            
            overdue_stats = list(mongo.db.payments.aggregate(overdue_pipeline))
            
            return {
                'period_days': days,
                'status_distribution': status_stats,
                'payment_methods': method_stats,
                'monthly_trends': monthly_trends,
                'overdue_analysis': overdue_stats[0] if overdue_stats else {},
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating payment analytics: {str(e)}")
            return {'error': str(e)}
    
    def _create_gateway_order(self, payment: Payment, gateway: str) -> Tuple[bool, Dict]:
        """Create order with payment gateway"""
        try:
            if gateway == 'razorpay' and self.razorpay_enabled:
                order_data = {
                    'amount': int(payment.get_total_amount() * 100),  # Razorpay expects paise
                    'currency': payment.currency,
                    'receipt': payment.payment_id,
                    'notes': {
                        'payment_id': payment.payment_id,
                        'description': payment.description
                    }
                }
                
                order = self.razorpay_client.order.create(order_data)
                return True, order
                
            elif gateway == 'stripe' and self.stripe_enabled:
                intent = self.stripe.PaymentIntent.create(
                    amount=int(payment.get_total_amount() * 100),  # Stripe expects cents
                    currency=payment.currency.lower(),
                    metadata={
                        'payment_id': payment.payment_id,
                        'description': payment.description
                    }
                )
                return True, {'id': intent.id, 'client_secret': intent.client_secret}
            
            else:
                return False, {'error': 'Gateway not configured'}
                
        except Exception as e:
            return False, {'error': str(e)}
    
    def _process_razorpay_webhook(self, payload: Dict, signature: str) -> Tuple[bool, str]:
        """Process Razorpay webhook"""
        try:
            # Verify signature
            webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET')
            if webhook_secret:
                expected_signature = hmac.new(
                    webhook_secret.encode(),
                    json.dumps(payload).encode(),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(signature, expected_signature):
                    return False, "Invalid signature"
            
            event = payload.get('event')
            payment_data = payload.get('payload', {}).get('payment', {}).get('entity', {})
            
            if event == 'payment.captured':
                return self._handle_payment_success(payment_data, 'razorpay')
            elif event == 'payment.failed':
                return self._handle_payment_failed(payment_data, 'razorpay')
            
            return True, f"Event {event} processed"
            
        except Exception as e:
            return False, str(e)
    
    def _process_stripe_webhook(self, payload: Dict, signature: str) -> Tuple[bool, str]:
        """Process Stripe webhook"""
        try:
            # Verify signature
            webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
            if webhook_secret:
                # Stripe signature verification would go here
                pass
            
            event_type = payload.get('type')
            payment_intent = payload.get('data', {}).get('object', {})
            
            if event_type == 'payment_intent.succeeded':
                return self._handle_payment_success(payment_intent, 'stripe')
            elif event_type == 'payment_intent.payment_failed':
                return self._handle_payment_failed(payment_intent, 'stripe')
            
            return True, f"Event {event_type} processed"
            
        except Exception as e:
            return False, str(e)
    
    def _handle_payment_success(self, gateway_payment: Dict, gateway: str) -> Tuple[bool, str]:
        """Handle successful payment from gateway"""
        try:
            # Find payment by gateway ID or metadata
            if gateway == 'razorpay':
                payment_id = gateway_payment.get('notes', {}).get('payment_id')
                gateway_id = gateway_payment.get('id')
            elif gateway == 'stripe':
                payment_id = gateway_payment.get('metadata', {}).get('payment_id')
                gateway_id = gateway_payment.get('id')
            
            if not payment_id:
                return False, "Payment ID not found in gateway data"
            
            payment_data = mongo.db.payments.find_one({'payment_id': payment_id})
            if not payment_data:
                return False, f"Payment {payment_id} not found"
            
            payment = Payment.from_dict(payment_data)
            
            # Process gateway response
            payment.process_gateway_response(
                gateway_id=gateway_id,
                status='success',
                response_data={
                    'amount': gateway_payment.get('amount', 0) / 100,  # Convert back to main currency
                    'method': gateway_payment.get('method', gateway),
                    'fee': gateway_payment.get('fee', 0) / 100 if gateway_payment.get('fee') else 0
                }
            )
            
            # Update in database
            mongo.db.payments.update_one(
                {'_id': payment._id},
                {'$set': payment.to_dict()}
            )
            
            return True, f"Payment {payment_id} marked as successful"
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment success: {str(e)}")
            return False, str(e)
    
    def _handle_payment_failed(self, gateway_payment: Dict, gateway: str) -> Tuple[bool, str]:
        """Handle failed payment from gateway"""
        try:
            # Similar to success handler but for failures
            if gateway == 'razorpay':
                payment_id = gateway_payment.get('notes', {}).get('payment_id')
                gateway_id = gateway_payment.get('id')
            elif gateway == 'stripe':
                payment_id = gateway_payment.get('metadata', {}).get('payment_id')
                gateway_id = gateway_payment.get('id')
            
            if not payment_id:
                return False, "Payment ID not found in gateway data"
            
            payment_data = mongo.db.payments.find_one({'payment_id': payment_id})
            if not payment_data:
                return False, f"Payment {payment_id} not found"
            
            payment = Payment.from_dict(payment_data)
            
            # Process failed response
            payment.process_gateway_response(
                gateway_id=gateway_id,
                status='failed',
                response_data={
                    'error_code': gateway_payment.get('error_code'),
                    'error_description': gateway_payment.get('error_description')
                }
            )
            
            # Update in database
            mongo.db.payments.update_one(
                {'_id': payment._id},
                {'$set': payment.to_dict()}
            )
            
            return True, f"Payment {payment_id} marked as failed"
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment failure: {str(e)}")
            return False, str(e)
    
    def _generate_summary_report(self, match_query: Dict) -> Dict:
        """Generate summary payment report"""
        pipeline = [
            {'$match': match_query},
            {
                '$group': {
                    '_id': None,
                    'total_payments': {'$sum': 1},
                    'total_amount': {'$sum': '$amount'},
                    'total_paid': {'$sum': '$paid_amount'},
                    'total_pending': {
                        '$sum': {
                            '$cond': [{'$eq': ['$status', 'pending']}, '$amount', 0]
                        }
                    },
                    'total_overdue': {
                        '$sum': {
                            '$cond': [{'$eq': ['$status', 'overdue']}, '$amount', 0]
                        }
                    },
                    'total_late_fees': {'$sum': '$late_fee'},
                    'total_discounts': {'$sum': '$discount'}
                }
            }
        ]
        
        results = list(mongo.db.payments.aggregate(pipeline))
        return results[0] if results else {}
    
    def _generate_detailed_report(self, match_query: Dict) -> Dict:
        """Generate detailed payment report"""
        payments = list(mongo.db.payments.find(match_query).sort('created_at', -1))
        
        # Add student names
        for payment in payments:
            if payment.get('student_id'):
                student = mongo.db.users.find_one(
                    {'_id': ObjectId(payment['student_id'])},
                    {'name': 1, 'phone_number': 1}
                )
                payment['student_name'] = student.get('name') if student else 'Unknown'
                payment['student_phone'] = student.get('phone_number') if student else None
        
        return {
            'payments': payments,
            'total_count': len(payments)
        }
    
    def _generate_analytics_report(self, match_query: Dict) -> Dict:
        """Generate analytics payment report"""
        # This would include various analytics aggregations
        return self.generate_payment_analytics(
            str(match_query['organization_id']), 
            days=30
        )
