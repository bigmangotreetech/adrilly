# API Endpoints Summary

## ✅ Fixed Issues

### 1. **Double Prefix Problem RESOLVED**
- **Issue**: Blueprints had `/api/auth`, `/api/users`, etc. but were being registered with additional `/api` prefix
- **Result**: Routes were incorrectly `/api/api/auth/login` instead of `/api/auth/login`
- **Fix**: Removed duplicate `/api` prefix from blueprint registration in `app.py`

### 2. **Enhanced Login Functionality**
- Added proper error handling and logging
- Added request validation
- Added debug mode support
- Added masked logging for security

## 📱 Mobile App Integration

The API endpoints now correctly match the mobile app constants in `constants.dart`:

```dart
// From mobile app constants.dart
static const String baseUrl = 'http://192.168.29.50:5000';
static const String requestOtpEndpoint = '/api/auth/request-otp';
static const String verifyOtpEndpoint = '/api/auth/verify-otp';
static const String loginEndpoint = '/api/auth/login';
static const String refreshTokenEndpoint = '/api/auth/refresh';
static const String profileEndpoint = '/api/auth/profile';
static const String logoutEndpoint = '/api/auth/logout';
```

## 🔐 Authentication Endpoints

### Base URL: `http://192.168.29.50:5000`

| Endpoint | Method | Route | Description |
|----------|--------|-------|-------------|
| Request OTP | POST | `/api/auth/request-otp` | Send OTP to phone number |
| Verify OTP | POST | `/api/auth/verify-otp` | Verify OTP and get tokens |
| Login | POST | `/api/auth/login` | Login with phone + password |
| Refresh Token | POST | `/api/auth/refresh` | Refresh access token |
| Get Profile | GET | `/api/auth/profile` | Get user profile |
| Update Profile | PUT | `/api/auth/profile` | Update user profile |
| Logout | POST | `/api/auth/logout` | Logout user |
| Change Password | POST | `/api/auth/change-password` | Change user password |

### Admin-only Endpoints:
| Endpoint | Method | Route | Description |
|----------|--------|-------|-------------|
| Register User | POST | `/api/auth/register-user` | Create new user (admin only) |
| Create Organization | POST | `/api/auth/create-organization` | Create org (super admin only) |
| Get Organizations | GET | `/api/auth/organizations` | List accessible organizations |
| Switch Organization | POST | `/api/auth/switch-organization/<org_id>` | Switch org context |

## 📊 Other API Endpoints

### Users
- Base Route: `/api/users`
- GET `/api/users` - List users
- GET `/api/users/groups` - List user groups
- POST `/api/users/groups` - Create group

### Classes
- Base Route: `/api/classes`
- GET, POST, PUT, DELETE operations for class management

### Attendance
- Base Route: `/api/attendance`
- Mark attendance, view records, reports

### Progress
- Base Route: `/api/progress`
- Student progress tracking and rubrics

### Payments
- Base Route: `/api/payments`
- Payment tracking and management

### Equipment
- Base Route: `/api/equipment`
- Equipment inventory management

### Webhooks
- Base Route: `/api/webhooks`
- WhatsApp webhook handling

## 🔑 Login Methods

### 1. OTP-based Login (Primary)
```bash
# Step 1: Request OTP
POST /api/auth/request-otp
{
  "phone_number": "1234567890"
}

# Step 2: Verify OTP
POST /api/auth/verify-otp
{
  "phone_number": "1234567890",
  "otp": "123456",
  "name": "User Name" # optional for new users
}
```

### 2. Password-based Login
```bash
POST /api/auth/login
{
  "phone_number": "1234567890",
  "password": "userpassword"
}
```

### 3. Token Refresh
```bash
POST /api/auth/refresh
# Requires refresh token in Authorization header
```

## 🔧 Enhanced Features

### Security Improvements:
- ✅ Request validation for all auth endpoints
- ✅ Masked logging (phone numbers partially hidden)
- ✅ Proper error messages
- ✅ Debug mode awareness
- ✅ JWT token management

### Error Handling:
- ✅ Validation errors with details
- ✅ Internal server errors with conditional details
- ✅ Authentication/authorization errors
- ✅ User-friendly error messages

### Logging:
- ✅ Login attempts (success/failure)
- ✅ OTP requests and verifications
- ✅ Error logging with context
- ✅ Privacy-conscious logging (masked sensitive data)

## 🧪 Testing

Run the endpoint test script:
```bash
cd "adrilly web"
python test_endpoints.py
```

This will verify:
- Health endpoint accessibility
- Authentication endpoint structure
- Proper error responses
- Endpoint availability

## 🏗️ Architecture

### Multi-tenant Support:
- Organizations as separate tenants
- Role-based access control
- Organization-scoped data access

### Roles Hierarchy:
1. `super_admin` - System-wide access
2. `org_admin` - Organization administration
3. `coach_admin` - Coach management within org
4. `coach` - Basic coaching functions
5. `student` - Student access

### JWT Claims:
- `user_id` - User identifier
- `phone_number` - User phone
- `role` - User role
- `organization_id` - Current organization context
- `permissions` - User permissions array

## ⚡ Quick Start

1. Ensure Flask app is running on `http://192.168.29.50:5000`
2. Mobile app should now connect successfully
3. Use OTP-based login for new users
4. Use password login for existing users
5. All endpoints properly prefixed with `/api`

## 🔍 Troubleshooting

### Common Issues:
1. **Connection Refused**: Check if Flask app is running on correct host/port
2. **404 on /api routes**: Ensure app.py blueprint registration is correct
3. **Double /api in URLs**: Fixed - blueprints no longer double-registered
4. **Authentication Failures**: Check JWT token validity and claims

### Debug Mode:
Set `FLASK_ENV=development` for detailed error messages in API responses. 