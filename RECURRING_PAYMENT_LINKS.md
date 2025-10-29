# Recurring Payment Links Feature

## Overview
This feature allows administrators to generate recurring payment links for users using Razorpay's Subscriptions API. Users can subscribe to recurring plans and make automatic payments based on the subscription cycle (weekly, monthly, quarterly, or yearly).

## Features

### 1. Generate Recurring Payment Links
- **Location**: Users management page (Edit User Modal)
- **Access**: Org Admins and Coach Admins only
- **Functionality**: Creates a Razorpay subscription with a shareable payment link

### 2. Automatic Plan Creation
- The system automatically creates or reuses Razorpay subscription plans
- Plans are stored in the `razorpay_plans` collection to avoid duplicates
- Each plan is linked to your subscription and cycle type

### 3. Customer Management
- Automatically creates Razorpay customer profiles when email is available
- Links subscriptions to customer accounts for better tracking
- Stores customer IDs for future reference

## How It Works

### Frontend (users.html)
1. User clicks "Generate Recurring Link" button in the Edit User modal
2. JavaScript function `generateRecurringPaymentLink()` is called
3. Makes POST request to `/api/generate-recurring-payment-link`
4. Displays the generated subscription link in a modal

### Backend (web.py)

#### API Endpoint: `/api/generate-recurring-payment-link`
**Method**: POST  
**Auth Required**: Yes (org_admin, coach_admin)

**Request Body**:
```json
{
  "user_id": "user_object_id",
  "subscription_id": "subscription_object_id"
}
```

**Response**:
```json
{
  "subscription_link": "https://rzp.io/i/xxxxx",
  "razorpay_subscription_id": "sub_xxxxx",
  "razorpay_plan_id": "plan_xxxxx",
  "status": "created"
}
```

**Process**:
1. Validates user and subscription
2. Determines billing period and interval from cycle_type
3. Creates or retrieves Razorpay plan
4. Creates Razorpay customer (if email exists)
5. Creates Razorpay subscription
6. Stores subscription link in database
7. Returns shareable subscription link

#### Callback Endpoint: `/razorpay/subscription-callback`
**Methods**: GET, POST  
**Auth Required**: No

Handles Razorpay subscription payment callbacks:
1. Receives subscription ID and payment ID
2. Fetches subscription details from Razorpay
3. Updates subscription status in database
4. Creates/updates user subscription record
5. Updates user's subscription status
6. Redirects to dashboard with success message

## Database Collections

### 1. `razorpay_plans`
Stores Razorpay plan information to avoid duplicate creation:
```javascript
{
  razorpay_plan_id: "plan_xxxxx",
  subscription_id: ObjectId,
  cycle_type: "monthly|weekly|quarterly|yearly",
  created_at: DateTime,
  created_by: ObjectId
}
```

### 2. `recurring_payment_links`
Stores generated subscription links:
```javascript
{
  razorpay_subscription_id: "sub_xxxxx",
  razorpay_plan_id: "plan_xxxxx",
  razorpay_customer_id: "cust_xxxxx",
  user_id: ObjectId,
  subscription_id: ObjectId,
  amount: Number,
  status: "created|active|paused|cancelled",
  link_url: "https://rzp.io/i/xxxxx",
  created_at: DateTime,
  created_by: ObjectId,
  activated_at: DateTime,
  last_updated: DateTime
}
```

### 3. `user_subscriptions`
Tracks active user subscriptions:
```javascript
{
  user_id: ObjectId,
  subscription_id: ObjectId,
  razorpay_subscription_id: "sub_xxxxx",
  razorpay_plan_id: "plan_xxxxx",
  razorpay_payment_id: "pay_xxxxx",
  status: "active|paused|cancelled",
  start_date: DateTime,
  created_at: DateTime
}
```

## Billing Cycle Mapping

| Cycle Type | Razorpay Period | Interval |
|------------|-----------------|----------|
| monthly    | monthly         | 1        |
| weekly     | weekly          | 1        |
| quarterly  | monthly         | 3        |
| yearly     | yearly          | 1        |

## UI Components

### Button
```html
<button type="button" class="btn btn-outline-success btn-sm" 
        onclick="generateRecurringPaymentLink()">
    <i class="bi bi-arrow-repeat me-1"></i>Generate Recurring Link
</button>
```

### JavaScript Function
```javascript
async function generateRecurringPaymentLink() {
    // Validates subscription selection
    // Shows loading state
    // Makes API call
    // Displays link in modal
    // Handles errors
}
```

## Configuration

### Environment Variables Required
```bash
RAZORPAY_API_KEY=rzp_test_xxxxx
RAZORPAY_API_SECRET=xxxxx
```

### Razorpay Client Initialization
```python
import razorpay
from os import environ

razorpay_client = razorpay.Client(
    auth=(environ.get('RAZORPAY_API_KEY'), environ.get('RAZORPAY_API_SECRET'))
)
```

## Usage Instructions

### For Administrators

1. **Navigate to Users Page**
   - Click on "Users" in the navigation menu

2. **Edit User**
   - Click the edit icon for the user you want to set up a subscription for

3. **Select Subscription Plan**
   - In the edit modal, select a subscription plan from the dropdown

4. **Generate Recurring Link**
   - Click the "Generate Recurring Link" button
   - Wait for the link to be generated

5. **Share Link**
   - Copy the generated link from the modal
   - Share it with the user via WhatsApp, email, SMS, etc.

### For Users

1. **Receive Link**
   - Get the subscription link from your administrator

2. **Open Link**
   - Click or open the Razorpay subscription link

3. **Complete Payment**
   - Fill in payment details on Razorpay's secure page
   - Complete the subscription payment

4. **Confirmation**
   - Receive confirmation from Razorpay
   - Get redirected back to the dashboard
   - Subscription is now active

## Differences from One-Time Payment

| Feature | One-Time Payment | Recurring Subscription |
|---------|------------------|------------------------|
| Payment Type | Single payment | Auto-recurring |
| Razorpay API | Orders API | Subscriptions API |
| Link Expiry | 24 hours | No expiry (until cancelled) |
| Billing Cycle | N/A | Weekly/Monthly/Quarterly/Yearly |
| Auto-renewal | No | Yes |
| Customer Profile | Optional | Recommended |
| Razorpay Plan | Not required | Required |

## Error Handling

### Common Errors

1. **No Subscription Selected**
   - Error: "Please select a subscription plan first"
   - Solution: Select a plan before generating link

2. **Invalid User or Subscription**
   - Error: "Invalid user or subscription"
   - Solution: Verify user and subscription exist

3. **Razorpay Plan Creation Failed**
   - Error: "Failed to create subscription plan"
   - Solution: Check Razorpay credentials and API limits

4. **Subscription Creation Failed**
   - Error: "Failed to create subscription link"
   - Solution: Check Razorpay account status and limits

## Webhook Support

For production environments, it's recommended to set up Razorpay webhooks to handle subscription events:

### Supported Events
- `subscription.activated` - Subscription becomes active
- `subscription.charged` - Recurring payment successful
- `subscription.cancelled` - Subscription cancelled
- `subscription.paused` - Subscription paused
- `subscription.resumed` - Subscription resumed
- `subscription.pending` - Payment pending
- `subscription.halted` - Payment failed

### Webhook Endpoint
The existing `/razorpay-webhook` endpoint can be extended to handle subscription events.

## Testing

### Test Mode
1. Use Razorpay test mode credentials
2. Generate test subscription links
3. Use Razorpay test cards for payment
4. Verify webhook callbacks

### Test Cards
Razorpay provides test cards for subscription testing:
- Success: 4111 1111 1111 1111
- Failure: 4111 1111 1111 1234

## Security Considerations

1. **Authentication Required**: Only authenticated admins can generate links
2. **Role-Based Access**: Limited to org_admin and coach_admin roles
3. **Signature Verification**: Razorpay callbacks should verify signatures
4. **HTTPS Required**: Production must use HTTPS for callbacks
5. **Database Security**: Store sensitive data securely

## Monitoring

### Key Metrics to Track
1. Number of subscription links generated
2. Subscription activation rate
3. Failed subscription attempts
4. Active vs inactive subscriptions
5. Revenue from recurring subscriptions

### Database Queries

**Active Subscriptions**:
```javascript
db.user_subscriptions.find({ status: "active" })
```

**Pending Subscriptions**:
```javascript
db.recurring_payment_links.find({ status: "created" })
```

**Subscriptions by Plan**:
```javascript
db.user_subscriptions.aggregate([
  { $group: { _id: "$subscription_id", count: { $sum: 1 } } }
])
```

## Future Enhancements

1. **Subscription Management Dashboard**
   - View all active subscriptions
   - Pause/resume subscriptions
   - Cancel subscriptions
   - View payment history

2. **Automated Notifications**
   - Email notifications for successful payments
   - SMS reminders before payment due
   - Alerts for failed payments

3. **Analytics Dashboard**
   - Subscription growth metrics
   - Churn rate analysis
   - Revenue forecasting

4. **Bulk Operations**
   - Generate links for multiple users
   - Bulk subscription updates
   - Export subscription data

## Support

For issues or questions:
1. Check Razorpay API documentation
2. Review application logs
3. Verify environment variables
4. Test in Razorpay test mode first
5. Contact Razorpay support for API issues

## API Documentation References

- [Razorpay Plans API](https://razorpay.com/docs/api/plans/)
- [Razorpay Subscriptions API](https://razorpay.com/docs/api/subscriptions/)
- [Razorpay Webhooks](https://razorpay.com/docs/webhooks/)
- [Razorpay Test Mode](https://razorpay.com/docs/payments/test-mode/)

