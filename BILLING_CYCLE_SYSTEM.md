# Billing Cycle System Documentation

## Overview
This system automatically processes recurring billing cycles for users with subscription plans. Instead of generating recurring payment links, the system uses scheduled jobs to check billing dates and update payment statuses automatically.

## How It Works

### 1. **Subscription Assignment**
When a subscription plan is assigned to a user in the Edit User modal:
- The subscription details are stored in the user document
- Billing cycle information is calculated and stored
- Next billing date is automatically set based on the billing start date and cycle type

### 2. **Automatic Billing Processing**
A scheduled job runs daily at 00:01 AM to:
- Check all users with active subscriptions
- Identify users whose billing date has arrived
- Mark their payment status as `fee_due`
- Create payment records for tracking
- Calculate and update the next billing date

### 3. **Overdue Payment Tracking**
Another scheduled job runs daily at 00:30 AM to:
- Find all pending payments past their due date
- Mark them as `overdue`
- Update user payment status to `overdue`

## Database Schema

### User Document Fields
When a subscription is assigned, the following fields are stored in the `users` collection:

```javascript
{
  _id: ObjectId,
  name: String,
  email: String,
  phone_number: String,
  organization_id: ObjectId,
  
  // Subscription fields
  subscription_ids: [ObjectId],           // Array of subscription plan IDs
  subscription_cycle_type: String,        // "weekly", "monthly", "quarterly", "yearly"
  subscription_amount: Number,            // Subscription price
  billing_start_date: Date,               // When billing started
  next_billing_date: Date,                // Next date to charge
  last_billing_date: Date,                // Last date charged
  payment_status: String,                 // "active", "fee_due", "overdue"
  fee_due_date: Date,                     // Date when fee became due
  
  // Other fields...
  updated_at: Date
}
```

### Payment Records
When a billing cycle triggers, a payment record is created:

```javascript
{
  _id: ObjectId,
  user_id: ObjectId,
  organization_id: ObjectId,
  subscription_id: ObjectId,
  amount: Number,
  cycle_type: String,
  due_date: Date,
  status: String,                         // "pending", "paid", "overdue", "cancelled"
  payment_type: String,                   // "subscription"
  description: String,                    // e.g., "Monthly Subscription - January 2025"
  created_at: Date,
  created_by_system: Boolean,             // true for auto-generated
  
  // Updated when payment is made
  paid_at: Date,
  razorpay_payment_id: String,
  payment_method: String
}
```

## Billing Cycle Types

### 1. Weekly
- Billing occurs every 7 days
- Next billing date = Current date + 1 week

### 2. Monthly
- Billing occurs on the same day each month
- **Edge Case Handling**: If the billing day doesn't exist in the next month (e.g., Jan 31 → Feb 28/29)
  - Uses the last day of that month
  - Examples:
    - Jan 31 → Feb 28 (or Feb 29 in leap years)
    - Jan 30 → Feb 28 (or Feb 29 in leap years)
    - Jan 29 → Feb 28 (non-leap) or Feb 29 (leap)

### 3. Quarterly
- Billing occurs every 3 months on the same day
- Same edge case handling as monthly

### 4. Yearly
- Billing occurs once per year on the same date
- **Leap Year Handling**: Feb 29 → Feb 28 in non-leap years

## Date Edge Case Examples

### Example 1: Monthly Billing Starting Jan 31
```
Jan 31, 2025 → Feb 28, 2025 (Feb has 28 days)
Feb 28, 2025 → Mar 31, 2025 (Mar has 31 days, use billing day 31)
Mar 31, 2025 → Apr 30, 2025 (Apr has 30 days)
Apr 30, 2025 → May 31, 2025 (May has 31 days, use billing day 31)
```

### Example 2: Yearly Billing Starting Feb 29, 2024 (Leap Year)
```
Feb 29, 2024 → Feb 28, 2025 (2025 is not a leap year)
Feb 28, 2025 → Feb 28, 2026 (2026 is not a leap year)
Feb 28, 2026 → Feb 28, 2027 (2027 is not a leap year)
Feb 28, 2027 → Feb 29, 2028 (2028 is a leap year)
```

## Scheduled Jobs

### Job 1: Process Billing Cycles
**File**: `app/tasks/billing_cycle_tasks.py`  
**Function**: `process_billing_cycles()`  
**Schedule**: Daily at 00:01 AM  
**Purpose**: Process all billing cycles and mark fees as due

**What it does**:
1. Queries all users with active subscriptions and upcoming billing dates
2. For each user whose `next_billing_date` is today or past:
   - Updates `payment_status` to `fee_due`
   - Sets `fee_due_date` to today
   - Creates a payment record with status `pending`
   - Calculates new `next_billing_date` based on cycle type
   - Updates `last_billing_date`

### Job 2: Mark Overdue Payments
**File**: `app/tasks/billing_cycle_tasks.py`  
**Function**: `mark_overdue_payments()`  
**Schedule**: Daily at 00:30 AM  
**Purpose**: Mark pending payments as overdue

**What it does**:
1. Finds all payments with status `pending` and due date in the past
2. Updates their status to `overdue`
3. Updates corresponding user's `payment_status` to `overdue`

## Usage

### For Administrators

#### Assigning a Subscription Plan

1. **Navigate to Users Page**
   - Click "Users" in the navigation menu

2. **Edit User**
   - Click the edit icon for the user

3. **Set Billing Information**
   - Select a **Billing Start Date** (when billing should begin)
   - Select a **Subscription Plan** from the dropdown
   - The system will automatically:
     - Store the subscription details
     - Calculate the billing cycle
     - Set the next billing date

4. **Save**
   - Click "Update User"
   - The user is now enrolled in automatic billing

#### Generating One-Time Payment Links

- For one-time payments or initial setup fees:
  - Select the subscription plan
  - Click "Generate Payment Link"
  - Share the link with the user

### For Users

#### Payment Status States

- **active**: Subscription is active, no payments due
- **fee_due**: A payment is due, waiting for payment
- **overdue**: Payment is past due date

#### Making Payments

When marked as `fee_due`:
1. Admin can generate a payment link for the pending payment
2. User pays through the link
3. System updates:
   - Payment record status to `paid`
   - User `payment_status` back to `active`

## Payment Workflow

### Complete Flow

```
Day 1: User Enrolled
├─ Subscription assigned
├─ billing_start_date = Today
├─ next_billing_date = Today + 1 cycle
└─ payment_status = "active"

Day 30: Billing Cycle Hits (Monthly)
├─ Scheduled job runs at 00:01 AM
├─ Detects next_billing_date <= Today
├─ Creates payment record (status: pending)
├─ Updates user:
│  ├─ payment_status = "fee_due"
│  ├─ fee_due_date = Today
│  ├─ last_billing_date = Day 30
│  └─ next_billing_date = Day 60
└─ Admin notified

Day 30-35: Payment Period
├─ Admin generates payment link
├─ User receives link
└─ User pays through Razorpay

Day 30-35: Payment Completed
├─ Payment record updated:
│  ├─ status = "paid"
│  ├─ paid_at = Payment timestamp
│  └─ razorpay_payment_id = ID
└─ User updated:
    └─ payment_status = "active"

Day 38: If Not Paid (8 days overdue)
├─ Scheduled job runs at 00:30 AM
├─ Detects pending payment past due date
├─ Updates payment: status = "overdue"
└─ Updates user: payment_status = "overdue"

Day 60: Next Billing Cycle
└─ Process repeats...
```

## Configuration

### Celery Setup

The scheduled jobs require Celery Beat to be running:

```bash
# Start Celery Worker (processes tasks)
celery -A celery_worker worker --loglevel=info

# Start Celery Beat (schedules periodic tasks)
celery -A celery_worker beat --loglevel=info
```

Or use the combined command:
```bash
celery -A celery_worker worker --beat --loglevel=info
```

### Cron Schedule Configuration

Schedules are defined in `app/tasks/billing_cycle_tasks.py`:

```python
@celery.on_after_configure.connect
def setup_billing_periodic_tasks(sender, **kwargs):
    # Process billing cycles daily at 00:01 AM
    sender.add_periodic_task(
        crontab(hour=0, minute=1),
        process_billing_cycles.s(),
        name='process-daily-billing-cycles'
    )
    
    # Mark overdue payments daily at 00:30 AM
    sender.add_periodic_task(
        crontab(hour=0, minute=30),
        mark_overdue_payments.s(),
        name='mark-overdue-payments'
    )
```

### Customizing Schedules

To change when billing is processed, modify the `crontab` parameters:

```python
# Process at 2:00 AM instead
crontab(hour=2, minute=0)

# Process twice daily (00:01 and 12:01)
crontab(hour='0,12', minute=1)

# Process every hour
crontab(minute=0)

# Process on specific days
crontab(hour=0, minute=1, day_of_week='mon,wed,fri')
```

## API Reference

### Helper Functions

#### `_calculate_next_billing_date(current_date, cycle_type)`

Calculates the next billing date based on the cycle type.

**Parameters:**
- `current_date` (date|datetime): The current billing date
- `cycle_type` (str): One of "weekly", "monthly", "quarterly", "yearly"

**Returns:**
- `date`: The next billing date

**Edge Cases Handled:**
- Monthly: Days 29, 30, 31 adjust to last day of month when needed
- Yearly: Feb 29 adjusts to Feb 28 in non-leap years

**Example:**
```python
from datetime import date
from app.routes.web import _calculate_next_billing_date

current = date(2025, 1, 31)
next_date = _calculate_next_billing_date(current, 'monthly')
# Returns: date(2025, 2, 28)
```

## Monitoring

### Database Queries for Monitoring

**Check users with fees due:**
```javascript
db.users.find({ payment_status: "fee_due" })
```

**Check overdue payments:**
```javascript
db.payments.find({ status: "overdue" })
```

**Check upcoming billings (next 7 days):**
```javascript
db.users.find({
  next_billing_date: {
    $gte: new Date(),
    $lte: new Date(Date.now() + 7*24*60*60*1000)
  }
})
```

**Revenue report for a month:**
```javascript
db.payments.aggregate([
  {
    $match: {
      status: "paid",
      paid_at: {
        $gte: new Date("2025-01-01"),
        $lt: new Date("2025-02-01")
      }
    }
  },
  {
    $group: {
      _id: null,
      total: { $sum: "$amount" },
      count: { $sum: 1 }
    }
  }
])
```

### Log Files

Check Celery logs for task execution:
```bash
# View Celery worker logs
tail -f celery_worker.log

# Check for billing task logs
grep "process_billing_cycles" celery_worker.log
grep "fee_due" celery_worker.log
```

## Testing

### Manual Testing

#### Test Billing Cycle Processing

```python
# In Python shell or script
from app.tasks.billing_cycle_tasks import process_billing_cycles
from app.app import create_app

app, celery = create_app()
with app.app_context():
    result = process_billing_cycles()
    print(result)
```

#### Test Date Calculation

```python
from datetime import date
from app.tasks.billing_cycle_tasks import _calculate_next_billing

# Test edge case: Jan 31 -> Feb
start = date(2025, 1, 31)
next_date = _calculate_next_billing(start, 'monthly')
assert next_date == date(2025, 2, 28)

# Test leap year: Feb 29 -> next year
start = date(2024, 2, 29)
next_date = _calculate_next_billing(start, 'yearly')
assert next_date == date(2025, 2, 28)
```

### Test Scenarios

1. **New Subscription Enrollment**
   - Assign subscription with billing start date = today
   - Verify next_billing_date is calculated correctly

2. **Billing Date Arrives**
   - Set user's next_billing_date to yesterday
   - Run `process_billing_cycles()`
   - Verify payment_status = "fee_due"
   - Verify payment record created

3. **Payment Made**
   - Generate payment link for fee_due user
   - Complete payment
   - Verify payment_status returns to "active"

4. **Overdue Payment**
   - Create payment with due_date in past, status "pending"
   - Run `mark_overdue_payments()`
   - Verify status changed to "overdue"

## Troubleshooting

### Issue: Billing cycles not processing

**Check:**
1. Is Celery Beat running?
   ```bash
   ps aux | grep celery
   ```

2. Check Celery logs for errors

3. Verify task is registered:
   ```python
   from app.extensions import celery
   print(celery.tasks.keys())
   # Should include 'app.tasks.billing_cycle_tasks.process_billing_cycles'
   ```

### Issue: Dates not calculating correctly

**Check:**
1. Verify `dateutil` is installed:
   ```bash
   pip install python-dateutil
   ```

2. Check user's `subscription_cycle_type` value
3. Verify `billing_start_date` is set

### Issue: Duplicate payments created

**Check:**
- The system checks for existing payments on the same due_date
- If duplicates occur, check for multiple Celery workers running

## Migration Guide

### Migrating Existing Users

If you have existing users with subscriptions, run this migration:

```python
from app.extensions import mongo
from datetime import datetime
from app.tasks.billing_cycle_tasks import _calculate_next_billing

# Find users with subscription_ids but no billing info
users = mongo.db.users.find({
    'subscription_ids': {'$exists': True, '$ne': []},
    'next_billing_date': {'$exists': False}
})

for user in users:
    subscription_id = user['subscription_ids'][0]
    subscription = mongo.db.subscriptions.find_one({'_id': subscription_id})
    
    if subscription:
        billing_start = user.get('billing_start_date') or datetime.utcnow()
        cycle_type = subscription.get('cycle_type', 'monthly')
        next_billing = _calculate_next_billing(billing_start, cycle_type)
        
        mongo.db.users.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'subscription_cycle_type': cycle_type,
                    'subscription_amount': subscription.get('price', 0),
                    'next_billing_date': next_billing,
                    'payment_status': 'active'
                }
            }
        )
        print(f"Migrated user: {user['name']}")
```

## Benefits of This Approach

1. **Fully Automated**: No manual link generation for recurring payments
2. **Predictable**: Billing happens at a consistent time every day
3. **Trackable**: All payments are recorded in the database
4. **Flexible**: Supports multiple billing cycles
5. **Reliable**: Handles edge cases like month-end dates
6. **Transparent**: Clear audit trail of all billing events
7. **Scalable**: Can handle thousands of users with subscriptions

## Future Enhancements

Possible improvements:
1. **Email Notifications**: Send emails when fees become due
2. **SMS Reminders**: WhatsApp/SMS reminders for overdue payments
3. **Grace Period**: Configurable grace period before marking overdue
4. **Auto-suspend**: Automatically suspend access for overdue accounts
5. **Payment Retry**: Automatic retry of failed payments
6. **Billing Dashboard**: Visual dashboard for billing analytics
7. **Custom Billing Days**: Allow users to choose their billing day
8. **Prorated Billing**: Handle mid-cycle subscription changes

## Support

For issues or questions:
1. Check Celery logs
2. Verify database records
3. Test date calculations manually
4. Review configuration settings

## Related Files

- **Backend Logic**: `app/routes/web.py` (edit_user function)
- **Scheduled Tasks**: `app/tasks/billing_cycle_tasks.py`
- **UI**: `templates/users.html`
- **Extensions**: `app/extensions.py` (Celery configuration)
- **Models**: `app/models/subscription.py`, `app/models/payments.py`

