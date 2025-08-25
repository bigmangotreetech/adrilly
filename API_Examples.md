# API Examples and Testing Guide

This document provides comprehensive examples for testing the Sports Coaching Management System API.

## 📋 Postman Collection

### Base URL
```
http://localhost:5000
```

### Environment Variables
Create these variables in your Postman environment:
- `base_url`: `http://localhost:5000`
- `access_token`: (will be set after authentication)
- `organization_id`: (will be set after authentication)

## 🔐 Authentication Flow

### 1. Phone-based OTP Authentication

#### Request OTP
```http
POST {{base_url}}/api/auth/request-otp
Content-Type: application/json

{
  "phone_number": "+1234567890"
}
```

**Response:**
```json
{
  "message": "OTP sent successfully"
}
```

#### Verify OTP (First time - Registration)
```http
POST {{base_url}}/api/auth/verify-otp
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "otp": "123456",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "_id": "user_id_here",
    "phone_number": "+1234567890",
    "name": "John Doe",
    "role": "student",
    "organization_id": null,
    "is_active": true,
    "verification_status": "verified"
  }
}
```

#### Password-based Login (After setting password)
```http
POST {{base_url}}/api/auth/login
Content-Type: application/json

{
  "phone_number": "+1234567890",
  "password": "your_password"
}
```

#### Get Profile
```http
GET {{base_url}}/api/auth/profile
Authorization: Bearer {{access_token}}
```

#### Update Profile
```http
PUT {{base_url}}/api/auth/profile
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "John Smith",
  "profile_data": {
    "age": 25,
    "emergency_contact": "+1234567891",
    "medical_info": "No allergies"
  }
}
```

## 👥 User & Organization Management

### Create Group (Admin/Coach only)
```http
POST {{base_url}}/api/users/groups
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "Advanced Football Group",
  "coach_id": "coach_id_here",
  "sport": "football",
  "level": "advanced",
  "description": "For experienced players",
  "max_students": 15
}
```

### Get All Groups
```http
GET {{base_url}}/api/users/groups
Authorization: Bearer {{access_token}}
```

### Get Users in Organization
```http
GET {{base_url}}/api/users?role=student
Authorization: Bearer {{access_token}}
```

## 🗓 Class Management

### Create Class
```http
POST {{base_url}}/api/classes
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "title": "Football Skills Training",
  "coach_id": "60a7c9b4e4b0f83d123456789",
  "scheduled_at": "2024-02-15T16:00:00Z",
  "duration_minutes": 90,
  "location": {
    "name": "Main Field",
    "address": "123 Sports Complex, City"
  },
  "group_ids": ["60a7c9b4e4b0f83d123456790"],
  "student_ids": ["60a7c9b4e4b0f83d123456791"],
  "sport": "football",
  "level": "intermediate",
  "notes": "Focus on passing and ball control",
  "max_students": 20
}
```

### Get Classes with Filters
```http
GET {{base_url}}/api/classes?start_date=2024-02-01T00:00:00Z&end_date=2024-02-29T23:59:59Z&status=scheduled&sport=football&page=1&per_page=10
Authorization: Bearer {{access_token}}
```

### Get Specific Class
```http
GET {{base_url}}/api/classes/60a7c9b4e4b0f83d123456792
Authorization: Bearer {{access_token}}
```

### Update Class
```http
PUT {{base_url}}/api/classes/60a7c9b4e4b0f83d123456792
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "title": "Advanced Football Training",
  "scheduled_at": "2024-02-15T17:00:00Z",
  "notes": "Updated training focus on defense tactics",
  "status": "scheduled"
}
```

### Get Class Students
```http
GET {{base_url}}/api/classes/60a7c9b4e4b0f83d123456792/students
Authorization: Bearer {{access_token}}
```

### Send Class Reminder
```http
POST {{base_url}}/api/classes/60a7c9b4e4b0f83d123456792/send-reminder
Authorization: Bearer {{access_token}}
```

## ✅ Attendance Management

### Get Class Attendance
```http
GET {{base_url}}/api/attendance/class/60a7c9b4e4b0f83d123456792
Authorization: Bearer {{access_token}}
```

**Response:**
```json
{
  "class": {
    "_id": "60a7c9b4e4b0f83d123456792",
    "title": "Football Skills Training",
    "scheduled_at": "2024-02-15T16:00:00Z"
  },
  "attendance": [
    {
      "student": {
        "id": "60a7c9b4e4b0f83d123456791",
        "name": "Student Name",
        "phone_number": "+1234567890"
      },
      "attendance": {
        "id": "60a7c9b4e4b0f83d123456793",
        "status": "present",
        "rsvp_response": "yes",
        "check_in_time": "2024-02-15T15:55:00Z",
        "notes": null,
        "marked_by": "coach_id_here"
      }
    }
  ],
  "summary": {
    "total_students": 10,
    "present": 8,
    "absent": 1,
    "late": 1,
    "excused": 0,
    "pending": 0
  }
}
```

### Mark Attendance
```http
POST {{base_url}}/api/attendance/class/60a7c9b4e4b0f83d123456792/mark
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "student_id": "60a7c9b4e4b0f83d123456791",
  "status": "present",
  "notes": "Excellent participation",
  "check_in_time": "2024-02-15T15:55:00Z"
}
```

### Update Attendance
```http
PUT {{base_url}}/api/attendance/60a7c9b4e4b0f83d123456793
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "status": "late",
  "notes": "Arrived 10 minutes late",
  "check_in_time": "2024-02-15T16:10:00Z"
}
```

### Get Student Attendance Summary
```http
GET {{base_url}}/api/attendance/student/60a7c9b4e4b0f83d123456791/summary?start_date=2024-01-01&end_date=2024-02-29
Authorization: Bearer {{access_token}}
```

**Response:**
```json
{
  "summary": {
    "student_id": "60a7c9b4e4b0f83d123456791",
    "period_start": "2024-01-01",
    "period_end": "2024-02-29",
    "total_classes": 20,
    "present_count": 18,
    "absent_count": 1,
    "late_count": 1,
    "excused_count": 0,
    "attendance_rate": 90.0
  },
  "details": {
    "student": {
      "id": "60a7c9b4e4b0f83d123456791",
      "name": "Student Name"
    },
    "period": {
      "start_date": "2024-01-01",
      "end_date": "2024-02-29"
    }
  }
}
```

### RSVP Update (Public endpoint for WhatsApp)
```http
POST {{base_url}}/api/attendance/rsvp/60a7c9b4e4b0f83d123456793
Content-Type: application/json

{
  "response": "yes",
  "message_id": "whatsapp_message_id_here"
}
```

## 📊 Progress Tracking

### Create Rubric
```http
POST {{base_url}}/api/progress/rubrics
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "Football Technical Skills",
  "sport": "football",
  "description": "Assessment for football technical abilities",
  "criteria": [
    {
      "name": "Ball Control",
      "weight": 25,
      "description": "Ability to control and manipulate the ball"
    },
    {
      "name": "Passing Accuracy",
      "weight": 20,
      "description": "Precision in short and long passes"
    },
    {
      "name": "Shooting",
      "weight": 20,
      "description": "Goal scoring ability and shot accuracy"
    },
    {
      "name": "Defending",
      "weight": 15,
      "description": "Defensive positioning and tackling"
    },
    {
      "name": "Physical Fitness",
      "weight": 20,
      "description": "Stamina, speed, and agility"
    }
  ],
  "scoring_scale": {
    "min": 1,
    "max": 10
  }
}
```

### Get Rubrics
```http
GET {{base_url}}/api/progress/rubrics?sport=football
Authorization: Bearer {{access_token}}
```

### Create Progress Assessment
```http
POST {{base_url}}/api/progress
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "student_id": "60a7c9b4e4b0f83d123456791",
  "rubric_id": "60a7c9b4e4b0f83d123456794",
  "scores": {
    "Ball Control": 8,
    "Passing Accuracy": 7,
    "Shooting": 6,
    "Defending": 7,
    "Physical Fitness": 9
  },
  "notes": "Great improvement in ball control and fitness. Need to work on shooting accuracy.",
  "assessment_date": "2024-02-15T18:00:00Z"
}
```

### Get Student Progress
```http
GET {{base_url}}/api/progress/student/60a7c9b4e4b0f83d123456791?rubric_id=60a7c9b4e4b0f83d123456794
Authorization: Bearer {{access_token}}
```

## 💳 Payment Management

### Create Payment
```http
POST {{base_url}}/api/payments
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "student_id": "60a7c9b4e4b0f83d123456791",
  "amount": 150.00,
  "description": "Monthly Training Fee - March 2024",
  "due_date": "2024-03-01",
  "payment_type": "monthly",
  "group_id": "60a7c9b4e4b0f83d123456790"
}
```

### Get Payments
```http
GET {{base_url}}/api/payments?status=pending&student_id=60a7c9b4e4b0f83d123456791&page=1&per_page=20
Authorization: Bearer {{access_token}}
```

### Mark Payment as Paid
```http
POST {{base_url}}/api/payments/60a7c9b4e4b0f83d123456795/mark-paid
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "amount": 150.00,
  "payment_method": "bank_transfer",
  "reference": "TXN123456789",
  "notes": "Paid via online banking"
}
```

## 🛒 Equipment Marketplace

### Create Equipment Listing
```http
POST {{base_url}}/api/equipment
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "title": "Nike Football Boots - Size 9",
  "description": "Professional football boots in excellent condition. Used for only one season. Suitable for artificial grass and natural turf.",
  "price": 75.00,
  "category": "footwear",
  "condition": "excellent",
  "images": [
    "https://example.com/boot1.jpg",
    "https://example.com/boot2.jpg"
  ],
  "contact_info": {
    "phone": "+1234567890",
    "email": "seller@example.com",
    "preferred_contact": "phone"
  },
  "location": "Sports City Center",
  "negotiable": true
}
```

### Search Equipment
```http
GET {{base_url}}/api/equipment?category=footwear&condition=excellent&search=nike&page=1&per_page=10
```

**Response:**
```json
{
  "equipment": [
    {
      "_id": "60a7c9b4e4b0f83d123456796",
      "title": "Nike Football Boots - Size 9",
      "description": "Professional football boots...",
      "price": 75.0,
      "owner_id": "60a7c9b4e4b0f83d123456791",
      "category": "footwear",
      "condition": "excellent",
      "images": ["https://example.com/boot1.jpg"],
      "contact_info": {
        "phone": "+1234567890"
      },
      "status": "available",
      "location": "Sports City Center",
      "views_count": 15,
      "created_at": "2024-02-01T10:00:00Z",
      "negotiable": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 1,
    "pages": 1
  }
}
```

## 📩 WhatsApp Integration

### WhatsApp Webhook (Simulated)
```http
POST {{base_url}}/api/webhooks/whatsapp
Content-Type: application/json

{
  "From": "whatsapp:+1234567890",
  "Body": "YES",
  "MessageSid": "SM1234567890abcdef1234567890abcdef",
  "ProfileName": "Student Name",
  "WaId": "1234567890"
}
```

### Test Webhook
```http
POST {{base_url}}/api/webhooks/test
Content-Type: application/json

{
  "test": "data",
  "message": "Testing webhook endpoint"
}
```

## 🔄 Background Task Testing

### Trigger Class Reminders (Development)
You can manually trigger background tasks in development:

```python
# In Python console
from app.tasks.reminder_tasks import send_class_reminders
result = send_class_reminders.delay(hours_before=2)
print(result.get())
```

## 📊 Health Check

### System Health
```http
GET {{base_url}}/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Sports Coaching Management API",
  "version": "1.0.0"
}
```

## 🧪 Testing Scenarios

### Complete User Journey

1. **Registration**: Request OTP → Verify OTP → Set up profile
2. **Class Enrollment**: Admin creates class → Student gets assigned
3. **Reminder Flow**: System sends WhatsApp reminder → Student responds
4. **Attendance**: Coach marks attendance → System tracks
5. **Progress**: Coach assesses student → Records improvement
6. **Payment**: Admin creates payment → Student pays → Admin marks paid
7. **Marketplace**: User lists equipment → Others browse and contact

### Error Testing

#### Invalid Authentication
```http
GET {{base_url}}/api/classes
Authorization: Bearer invalid_token
```

**Response:**
```json
{
  "error": "Invalid token"
}
```

#### Insufficient Permissions
```http
POST {{base_url}}/api/classes
Authorization: Bearer student_token
Content-Type: application/json

{
  "title": "Test Class"
}
```

**Response:**
```json
{
  "error": "Insufficient permissions"
}
```

#### Validation Errors
```http
POST {{base_url}}/api/classes
Authorization: Bearer admin_token
Content-Type: application/json

{
  "title": "",
  "scheduled_at": "invalid_date"
}
```

**Response:**
```json
{
  "error": "Validation error",
  "details": {
    "title": ["Field may not be blank."],
    "scheduled_at": ["Not a valid datetime."]
  }
}
```

## 📋 Postman Collection JSON

Save this as a Postman collection file:

```json
{
  "info": {
    "name": "Sports Coaching API",
    "description": "Complete API collection for Sports Coaching Management System",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:5000"
    },
    {
      "key": "access_token",
      "value": ""
    }
  ],
  "item": [
    {
      "name": "Authentication",
      "item": [
        {
          "name": "Request OTP",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"phone_number\": \"+1234567890\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/api/auth/request-otp",
              "host": ["{{base_url}}"],
              "path": ["api", "auth", "request-otp"]
            }
          }
        }
      ]
    }
  ]
}
```

This comprehensive API guide should help you test all aspects of the Sports Coaching Management System! 