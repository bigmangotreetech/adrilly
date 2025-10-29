# Botle Coins API Implementation

## Overview
Complete implementation of the Botle Coins earning system with transaction logging. Users can now earn coins for various activities and view their transaction history.

## Features Implemented

### 1. **Coin Transaction Model** (`app/models/coin_transaction.py`)
- Tracks all coin earnings and redemptions
- Stores complete audit trail with:
  - Transaction type (earned, redeemed, awarded, deducted)
  - Reason codes for different activities
  - Balance before and after each transaction
  - Reference to related objects (class_id, booking_id, etc.)
  - Timestamps and metadata

### 2. **Coin Service** (`app/services/coin_service.py`)
Comprehensive service for managing coins:
- `award_coins()` - Award coins to users
- `redeem_coins()` - Deduct coins from users
- `check_weekly_attendance_reward()` - Auto-check and award weekly bonus
- `get_user_transactions()` - Retrieve transaction history
- `get_user_balance()` - Get current balance

### 3. **Automatic Coin Rewards**

#### Class Booking (`/mobile-api/classes/<class_id>/book`)
✅ **Self Booking: +5 coins**
- Awarded when user books a class for themselves
- Logged with reason: `REASON_SELF_BOOKING`

✅ **Booking for Others: +15 coins**
- Awarded when user books a class for someone else (friend_id present)
- Logged with reason: `REASON_OTHER_BOOKING`

#### Attendance Marking (`/mobile-api/attendance/mark`)
✅ **Weekly Attendance: +10 coins**
- Automatically checks after marking attendance
- Awards bonus when user has attended 4 classes in past 7 days
- Only awards once per week (prevents duplicate rewards)
- Returns coin reward info in response if earned
- Logged with reason: `REASON_WEEKLY_ATTENDANCE`

## New API Endpoints

### 1. Get Coin Transactions
**GET** `/mobile-api/coins/transactions`

Get paginated transaction history for the current user.

**Query Parameters:**
- `page` (optional, default: 1) - Page number
- `limit` (optional, default: 50) - Items per page

**Response:**
```json
{
  "success": true,
  "transactions": [
    {
      "_id": "...",
      "user_id": "...",
      "amount": 5,
      "transaction_type": "earned",
      "reason": "self_booking",
      "description": "Booked a class (+5 coins)",
      "balance_before": 0,
      "balance_after": 5,
      "reference_id": "class_id_here",
      "reference_type": "class",
      "created_at": "2025-10-16T10:30:00Z"
    }
  ],
  "currentBalance": 35,
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 7,
    "hasMore": false
  }
}
```

### 2. Get Coin Balance
**GET** `/mobile-api/coins/balance`

Get current coin balance for the user.

**Response:**
```json
{
  "success": true,
  "balance": 35
}
```

## Database Schema

### Collection: `coin_transactions`
```javascript
{
  _id: ObjectId,
  user_id: ObjectId,              // User who owns the coins
  amount: Number,                 // Positive for earn, negative for spend
  transaction_type: String,       // 'earned', 'redeemed', 'awarded', 'deducted'
  reason: String,                 // Reason code
  description: String,            // Human-readable description
  reference_id: ObjectId,         // Related object (class_id, etc.)
  reference_type: String,         // Type of reference
  balance_before: Number,         // Balance before transaction
  balance_after: Number,          // Balance after transaction
  created_by: ObjectId,           // For manual awards (optional)
  created_at: Date
}
```

**Indexes:**
- `user_id` (for fast user lookups)
- `created_at` (for sorting)
- `reason` (for analytics)

## Coin Earning Summary

| Activity | Coins | Frequency | Reason Code |
|----------|-------|-----------|-------------|
| Book class for self | +5 | Per booking | `REASON_SELF_BOOKING` |
| Book class for friend | +15 | Per booking | `REASON_OTHER_BOOKING` |
| Attend 4 classes in a week | +10 | Once per week | `REASON_WEEKLY_ATTENDANCE` |

## Testing

### 1. Test Class Booking Coins

**Book for Self:**
```bash
POST /mobile-api/classes/{class_id}/book
Authorization: Bearer {token}

# Response includes updated class
# Check user's botle_coins increased by 5
```

**Book for Friend:**
```bash
POST /mobile-api/classes/{class_id}/book
Authorization: Bearer {token}
Content-Type: application/json

{
  "friend_id": "friend_user_id_here"
}

# User who booked gets +15 coins
```

### 2. Test Attendance Coins

```bash
POST /mobile-api/attendance/mark
Authorization: Bearer {token}
Content-Type: application/json

{
  "qrCode": "valid_qr_token_here"
}

# After 4th class in a week, response includes:
{
  "success": true,
  "classId": "...",
  "className": "...",
  "message": "Attendance marked successfully",
  "coinsEarned": 10,
  "coinMessage": "Earned 10 coins for weekly attendance!"
}
```

### 3. Test Transaction History

```bash
GET /mobile-api/coins/transactions?page=1&limit=20
Authorization: Bearer {token}

# Returns paginated list of all coin transactions
```

### 4. Test Balance Check

```bash
GET /mobile-api/coins/balance
Authorization: Bearer {token}

# Returns current balance
```

## Implementation Notes

### Weekly Attendance Logic
- Counts classes attended in **last 7 days** (rolling window)
- Only marks attendance with status 'present' are counted
- Checks for existing weekly reward to prevent duplicates
- Awards automatically when 4th class is attended
- Award is tied to the week, not a specific 7-day period

### Error Handling
- Coin operations never block the main operation (booking/attendance)
- If coin awarding fails, logs error but continues
- Attendance marking succeeds even if coin check fails
- All operations are logged for debugging

### Security
- All endpoints require JWT authentication
- Users can only view their own transactions
- Coin balance updates are atomic
- Transaction history is immutable (append-only)

### Performance
- Transactions are indexed for fast retrieval
- Balance is stored on user document for quick access
- Weekly attendance check is optimized with date range queries
- Duplicate reward prevention uses indexed queries

## Future Enhancements

### Planned Features
1. **Coin Redemption**
   - Use coins to book premium classes
   - Discount on membership fees
   - Redeem for merchandise

2. **Admin Controls**
   - Manual coin awards
   - Bulk coin operations
   - Transaction reversal

3. **Analytics**
   - Leaderboards
   - Coin earning trends
   - Reward effectiveness metrics

4. **Notifications**
   - Push notification when coins are earned
   - Weekly coin summary
   - Balance low alerts

### API Endpoints to Add
```python
# Redeem coins for class booking
POST /mobile-api/coins/redeem
{
  "amount": 50,
  "class_id": "..."
}

# Get coin leaderboard
GET /mobile-api/coins/leaderboard?period=week

# Admin: Award coins manually
POST /admin-api/coins/award
{
  "user_id": "...",
  "amount": 100,
  "reason": "Special achievement"
}
```

## Monitoring & Maintenance

### Database Maintenance
```javascript
// Create indexes for performance
db.coin_transactions.createIndex({ user_id: 1, created_at: -1 })
db.coin_transactions.createIndex({ reason: 1, created_at: -1 })

// Analytics query: Total coins earned by reason
db.coin_transactions.aggregate([
  { $match: { transaction_type: "earned" } },
  { $group: { _id: "$reason", total: { $sum: "$amount" }, count: { $sum: 1 } } }
])

// Check for users with negative balances (should never happen)
db.users.find({ botle_coins: { $lt: 0 } })
```

### Logs to Monitor
- Coin awarding failures
- Negative balance attempts
- Duplicate weekly rewards
- Transaction creation errors

## Migration

Run the migration script to add `botle_coins` to existing users:
```bash
cd "adrilly web"
python migrate_add_botle_coins.py
```

## Files Modified/Created

### Created Files
1. `app/models/coin_transaction.py` - Transaction model
2. `app/services/coin_service.py` - Coin management service
3. `BOTLE_COINS_API_IMPLEMENTATION.md` - This file

### Modified Files
1. `app/routes/mobile_api.py`
   - Added coin service imports
   - Updated class booking endpoint (+5/+15 coins)
   - Updated attendance marking endpoint (+10 coins)
   - Added coin transaction history endpoints
2. `app/models/user.py` - Already has `botle_coins` field
3. Flutter app - Already has coin display

---

**Implementation Date:** October 16, 2025  
**Status:** ✅ Complete and Production Ready  
**Version:** 1.0

