from datetime import datetime, timedelta, date
from bson import ObjectId
import uuid
from typing import Dict, List, Optional
import json

class Payment:
    """Enhanced payment model for comprehensive fee tracking and gateway integration"""
    
    def __init__(self, student_id, organization_id, amount, description,
                 due_date, payment_type='monthly', group_id=None):
        self.student_id = ObjectId(student_id) if student_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.group_id = ObjectId(group_id) if group_id else None
        self.amount = float(amount)
        self.description = description
        self.due_date = due_date
        self.payment_type = payment_type  # 'monthly', 'weekly', 'session', 'one_time', 'registration', 'equipment'
        self.status = 'pending'  # 'pending', 'paid', 'overdue', 'cancelled', 'refunded', 'partially_paid'
        self.paid_amount = 0.0
        self.paid_date = None
        self.payment_method = None  # 'cash', 'card', 'upi', 'bank_transfer', 'online', 'razorpay', 'stripe'
        self.payment_reference = None  # Transaction ID or reference
        self.notes = None
        self.late_fee = 0.0
        self.discount = 0.0
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.created_by = None  # Admin who created the payment record
        self.marked_by = None  # Who marked it as paid
        
        # Enhanced payment tracking
        self.payment_id = str(uuid.uuid4())  # Unique payment identifier
        self.invoice_number = None  # Auto-generated invoice number
        self.recurring_payment_id = None  # Link to recurring payment plan
        self.parent_payment_id = None  # For partial payments or refunds
        
        # Gateway integration fields
        self.gateway_payment_id = None  # Payment gateway transaction ID
        self.gateway_status = None  # Gateway-specific status
        self.gateway_response = None  # Full gateway response (JSON)
        self.gateway_fee = 0.0  # Fee charged by payment gateway
        
        # Advanced features
        self.installments = []  # For installment payments
        self.auto_retry_count = 0  # Number of automatic retry attempts
        self.reminder_history = []  # History of reminders sent
        self.refund_history = []  # History of refunds
        self.audit_trail = []  # Complete audit trail of changes
        
        # Analytics and reporting
        self.payment_category = None  # For reporting: 'tuition', 'equipment', 'events', etc.
        self.tax_amount = 0.0  # Tax component if applicable
        self.currency = 'INR'  # Currency code
        
        # Student experience
        self.payment_link = None  # Unique payment link for online payments
        self.qr_code_data = None  # UPI QR code data
        self.payment_instructions = None  # Custom payment instructions
    
    def to_dict(self):
        """Convert payment to dictionary"""
        data = {
            'student_id': str(self.student_id) if self.student_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'group_id': str(self.group_id) if self.group_id else None,
            'amount': self.amount,
            'description': self.description,
            'due_date': datetime.combine(self.due_date, datetime.min.time()) if isinstance(self.due_date, date) else self.due_date,
            'payment_type': self.payment_type,
            'status': self.status,
            'paid_amount': self.paid_amount,
            'paid_date': datetime.combine(self.paid_date, datetime.min.time()) if isinstance(self.paid_date, date) else self.paid_date,
            'payment_method': self.payment_method,
            'payment_reference': self.payment_reference,
            'notes': self.notes,
            'late_fee': self.late_fee,
            'discount': self.discount,
            'total_amount': self.get_total_amount(),
            'days_overdue': self.get_days_overdue(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': str(self.created_by) if self.created_by else None,
            'marked_by': str(self.marked_by) if self.marked_by else None,
            
            # Enhanced fields
            'payment_id': self.payment_id,
            'invoice_number': self.invoice_number,
            'recurring_payment_id': self.recurring_payment_id,
            'parent_payment_id': self.parent_payment_id,
            'gateway_payment_id': self.gateway_payment_id,
            'gateway_status': self.gateway_status,
            'gateway_response': self.gateway_response,
            'gateway_fee': self.gateway_fee,
            'installments': self.installments,
            'auto_retry_count': self.auto_retry_count,
            'reminder_history': self.reminder_history,
            'refund_history': self.refund_history,
            'audit_trail': self.audit_trail,
            'payment_category': self.payment_category,
            'tax_amount': self.tax_amount,
            'currency': self.currency,
            'payment_link': self.payment_link,
            'qr_code_data': self.qr_code_data,
            'payment_instructions': self.payment_instructions
        }
        
        # Only include _id if it exists and is not None
        if hasattr(self, '_id') and self._id is not None:
            data['_id'] = str(self._id)
            
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Create payment from dictionary"""
        payment = cls(
            student_id=data.get('student_id'),
            organization_id=data.get('organization_id'),
            amount=data['amount'],
            description=data['description'],
            due_date=data['due_date'],
            payment_type=data.get('payment_type', 'monthly'),
            group_id=data.get('group_id')
        )
        
        # Set additional attributes
        if '_id' in data:
            payment._id = data['_id']
        if 'status' in data:
            payment.status = data['status']
        if 'paid_amount' in data:
            payment.paid_amount = data['paid_amount']
        if 'paid_date' in data:
            payment.paid_date = data['paid_date']
        if 'payment_method' in data:
            payment.payment_method = data['payment_method']
        if 'payment_reference' in data:
            payment.payment_reference = data['payment_reference']
        if 'notes' in data:
            payment.notes = data['notes']
        if 'late_fee' in data:
            payment.late_fee = data['late_fee']
        if 'discount' in data:
            payment.discount = data['discount']
        if 'created_at' in data:
            payment.created_at = data['created_at']
        if 'updated_at' in data:
            payment.updated_at = data['updated_at']
        if 'created_by' in data:
            payment.created_by = ObjectId(data['created_by']) if data['created_by'] else None
        if 'marked_by' in data:
            payment.marked_by = ObjectId(data['marked_by']) if data['marked_by'] else None
        
        return payment
    
    def get_total_amount(self):
        """Calculate total amount including late fees and discounts"""
        return self.amount + self.late_fee - self.discount
    
    def get_days_overdue(self):
        """Get number of days overdue"""
        if self.status == 'paid' or self.due_date >= datetime.utcnow().date():
            return 0
        return (datetime.utcnow().date() - self.due_date).days
    
    def mark_paid(self, amount=None, payment_method=None, reference=None, 
                  marked_by=None, notes=None):
        """Mark payment as paid"""
        self.status = 'paid'
        self.paid_amount = amount or self.get_total_amount()
        self.paid_date = datetime.utcnow()
        self.payment_method = payment_method
        self.payment_reference = reference
        self.marked_by = ObjectId(marked_by) if marked_by else None
        if notes:
            self.notes = notes
        self.updated_at = datetime.utcnow()
    
    def mark_overdue(self, late_fee=0.0):
        """Mark payment as overdue and add late fee"""
        if self.status == 'pending' and self.due_date < datetime.utcnow().date():
            self.status = 'overdue'
            self.late_fee += late_fee
            self.updated_at = datetime.utcnow()
    
    def apply_discount(self, discount_amount, reason=None):
        """Apply discount to payment"""
        self.discount = discount_amount
        if reason and self.notes:
            self.notes += f" | Discount: {reason}"
        elif reason:
            self.notes = f"Discount: {reason}"
        self.updated_at = datetime.utcnow()
        
        # Add to audit trail
        self.add_audit_entry('discount_applied', {
            'discount_amount': discount_amount,
            'reason': reason,
            'previous_total': self.amount + self.late_fee,
            'new_total': self.get_total_amount()
        })
    
    def generate_invoice_number(self, organization_prefix: str = "INV") -> str:
        """Generate unique invoice number"""
        if not self.invoice_number:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            self.invoice_number = f"{organization_prefix}-{timestamp}-{self.payment_id[:8]}"
        return self.invoice_number
    
    def generate_payment_link(self, base_url: str) -> str:
        """Generate secure payment link"""
        if not self.payment_link:
            self.payment_link = f"{base_url}/pay/{self.payment_id}"
        return self.payment_link
    
    def add_audit_entry(self, action: str, details: Dict, user_id: str = None):
        """Add entry to audit trail"""
        audit_entry = {
            'action': action,
            'details': details,
            'timestamp': datetime.utcnow(),
            'user_id': user_id
        }
        self.audit_trail.append(audit_entry)
        self.updated_at = datetime.utcnow()
    
    def add_reminder_entry(self, reminder_type: str, message_id: str = None):
        """Add reminder to history"""
        reminder_entry = {
            'type': reminder_type,
            'sent_at': datetime.utcnow(),
            'message_id': message_id
        }
        self.reminder_history.append(reminder_entry)
        self.updated_at = datetime.utcnow()
    
    def process_gateway_response(self, gateway_id: str, status: str, response_data: Dict):
        """Process payment gateway response"""
        self.gateway_payment_id = gateway_id
        self.gateway_status = status
        self.gateway_response = json.dumps(response_data) if response_data else None
        
        # Update payment status based on gateway status
        if status in ['success', 'captured', 'paid']:
            self.status = 'paid'
            self.paid_date = datetime.utcnow()
            self.paid_amount = response_data.get('amount', self.get_total_amount())
            self.payment_method = response_data.get('method', 'online')
            self.payment_reference = gateway_id
            
            # Extract gateway fee if available
            self.gateway_fee = response_data.get('fee', 0.0)
        
        elif status in ['failed', 'cancelled']:
            self.status = 'pending'  # Keep as pending for retry
            self.auto_retry_count += 1
        
        self.add_audit_entry('gateway_response', {
            'gateway_id': gateway_id,
            'status': status,
            'amount': response_data.get('amount'),
            'method': response_data.get('method')
        })
        
        self.updated_at = datetime.utcnow()
    
    def create_installment_plan(self, installment_count: int, start_date: date = None) -> List[Dict]:
        """Create installment plan for the payment"""
        if installment_count <= 1:
            return []
        
        start_date = start_date or datetime.utcnow().date()
        installment_amount = self.get_total_amount() / installment_count
        
        installments = []
        for i in range(installment_count):
            installment_date = start_date + timedelta(days=30 * i)  # Monthly installments
            installment = {
                'number': i + 1,
                'amount': round(installment_amount, 2),
                'due_date': installment_date,
                'status': 'pending',
                'paid_amount': 0.0,
                'paid_date': None
            }
            installments.append(installment)
        
        self.installments = installments
        self.add_audit_entry('installment_plan_created', {
            'installment_count': installment_count,
            'installment_amount': installment_amount
        })
        
        return installments
    
    def process_refund(self, refund_amount: float, reason: str, refund_method: str = None, 
                      processed_by: str = None) -> bool:
        """Process a refund for this payment"""
        if self.status != 'paid':
            return False
        
        if refund_amount > self.paid_amount:
            return False
        
        refund_entry = {
            'amount': refund_amount,
            'reason': reason,
            'method': refund_method or self.payment_method,
            'processed_at': datetime.utcnow(),
            'processed_by': processed_by,
            'refund_id': str(uuid.uuid4())
        }
        
        self.refund_history.append(refund_entry)
        
        # Update payment status
        if refund_amount >= self.paid_amount:
            self.status = 'refunded'
        else:
            self.status = 'partially_paid'
            self.paid_amount -= refund_amount
        
        self.add_audit_entry('refund_processed', refund_entry)
        self.updated_at = datetime.utcnow()
        
        return True
    
    def get_payment_summary(self) -> Dict:
        """Get comprehensive payment summary"""
        return {
            'payment_id': self.payment_id,
            'invoice_number': self.invoice_number,
            'amount': self.amount,
            'total_amount': self.get_total_amount(),
            'paid_amount': self.paid_amount,
            'status': self.status,
            'due_date': self.due_date,
            'days_overdue': self.get_days_overdue(),
            'payment_method': self.payment_method,
            'gateway_fee': self.gateway_fee,
            'total_refunded': sum(r['amount'] for r in self.refund_history),
            'reminder_count': len(self.reminder_history),
            'has_installments': bool(self.installments),
            'currency': self.currency
        }
    
    def can_be_refunded(self) -> bool:
        """Check if payment can be refunded"""
        return self.status in ['paid', 'partially_paid'] and self.paid_amount > 0
    
    def can_retry_payment(self) -> bool:
        """Check if payment can be retried"""
        return (self.status in ['pending', 'overdue'] and 
                self.auto_retry_count < 3 and 
                self.get_days_overdue() < 30)

class PaymentPlan:
    """Payment plan model for recurring payments"""
    
    def __init__(self, student_id, organization_id, plan_name, amount_per_cycle,
                 cycle_type='monthly', start_date=None, end_date=None, group_id=None):
        self.student_id = ObjectId(student_id) if student_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.group_id = ObjectId(group_id) if group_id else None
        self.plan_name = plan_name
        self.amount_per_cycle = float(amount_per_cycle)
        self.cycle_type = cycle_type  # 'weekly', 'monthly', 'quarterly'
        self.start_date = start_date or datetime.utcnow().date()
        self.end_date = end_date
        self.is_active = True
        self.auto_generate = True  # Auto-generate payment records
        self.next_payment_date = self._calculate_next_payment_date()
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def _calculate_next_payment_date(self):
        """Calculate next payment due date"""
        if self.cycle_type == 'weekly':
            return self.start_date + timedelta(weeks=1)
        elif self.cycle_type == 'monthly':
            # Add one month (approximate)
            next_month = self.start_date.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=self.start_date.day)
        elif self.cycle_type == 'quarterly':
            # Add three months (approximate)
            next_quarter = self.start_date.replace(day=1) + timedelta(days=92)
            return next_quarter.replace(day=self.start_date.day)
        return self.start_date
    
    def to_dict(self):
        """Convert payment plan to dictionary"""
        return {
            '_id': str(self._id) if hasattr(self, '_id') else None,
            'student_id': str(self.student_id) if self.student_id else None,
            'organization_id': str(self.organization_id) if self.organization_id else None,
            'group_id': str(self.group_id) if self.group_id else None,
            'plan_name': self.plan_name,
            'amount_per_cycle': self.amount_per_cycle,
            'cycle_type': self.cycle_type,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'is_active': self.is_active,
            'auto_generate': self.auto_generate,
            'next_payment_date': self.next_payment_date,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create payment plan from dictionary"""
        plan = cls(
            student_id=data.get('student_id'),
            organization_id=data.get('organization_id'),
            plan_name=data['plan_name'],
            amount_per_cycle=data['amount_per_cycle'],
            cycle_type=data.get('cycle_type', 'monthly'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            group_id=data.get('group_id')
        )
        
        # Set additional attributes
        if '_id' in data:
            plan._id = data['_id']
        if 'is_active' in data:
            plan.is_active = data['is_active']
        if 'auto_generate' in data:
            plan.auto_generate = data['auto_generate']
        if 'next_payment_date' in data:
            plan.next_payment_date = data['next_payment_date']
        if 'created_at' in data:
            plan.created_at = data['created_at']
        if 'updated_at' in data:
            plan.updated_at = data['updated_at']
        
        return plan 