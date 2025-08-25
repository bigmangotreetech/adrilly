# Sports Coaching Management System

A comprehensive **multi-tenant** Flask application for managing student scheduling, attendance, progress tracking, WhatsApp reminders, and payments for sports and fitness coaching centers.

## 🏢 Multi-Tenant Architecture

This system supports **multiple organizations** with complete data isolation:

- **Super Admin**: Platform administrator who can create and manage organizations
- **Organization Admin**: Manages their coaching center, users, and operations
- **Coach Admin**: Senior coaches with user management capabilities
- **Coach**: Regular coaches who manage classes and students
- **Student**: Trainees who can view their data and RSVP for classes

### 📱 Phone Number Authentication

- **Primary Authentication**: Phone number-based login system
- **Dual Login Methods**: Password-based and OTP-based authentication
- **International Support**: Automatic phone number normalization (E.164 format)
- **Security**: JWT tokens with role-based claims and permissions

## ✨ Features

### 🔐 Authentication & Authorization
- Phone number registration/login with OTP verification
- Password-based authentication for registered users
- JWT tokens with role-based access control (RBAC)
- Hierarchical permission system
- Organization-level data isolation
- Multi-factor authentication support

### 🏗️ Multi-Tenant Organization Management
- Super admin can create new organizations
- Each organization has its own admin, coaches, and students
- Complete data isolation between organizations
- Organization-specific settings and branding
- Flexible sports and activity configuration

### 👥 User Management
- Role hierarchy: Super Admin → Org Admin → Coach Admin → Coach → Student
- User creation with automatic role assignment
- Group-based student organization
- Profile management with custom fields
- User deactivation and role updates

### 🗓️ Class Scheduling
- Flexible class creation with groups or individual assignment
- Multi-sport support with level categorization
- Location and notes management
- Class status tracking (scheduled, completed, cancelled)
- Coach assignment and override capabilities

### 📩 WhatsApp Integration
- Automated class reminders (2 hours before class)
- Interactive RSVP with YES/NO/MAYBE responses
- Dual provider support (Twilio & Interakt)
- Webhook handling for real-time updates
- Fallback messaging for development

### ✅ Attendance Management
- Auto-marking via WhatsApp RSVP
- Manual override by coaches
- Comprehensive status tracking
- Attendance summaries and reports
- Class participation analytics

### 📊 Progress Tracking
- Custom rubrics per sport/organization
- Pre-defined criteria for popular sports
- Flexible scoring scales (1-5, 1-10, A-F)
- Progress history and trend analysis
- Coach evaluations and notes

### 💳 Payment Management
- Flexible payment types (monthly, weekly, session-based)
- Automated recurring payment generation
- Late fee and discount support
- Payment status tracking
- Manual payment marking (gateway-ready)

### 🛒 Equipment Marketplace
- Secondhand equipment listings
- Rich metadata (images, condition, contact)
- Search and filtering capabilities
- Negotiation and view tracking
- Organization-based listings

### 🔄 Background Tasks
- Automated class and payment reminders
- Recurring payment generation
- Class status updates
- OTP cleanup tasks
- WhatsApp message queuing

## 🧰 Tech Stack

- **Backend**: Flask (Python 3.10+)
- **Database**: MongoDB Atlas (with PyMongo)
- **Authentication**: Flask-JWT-Extended with phone-based auth
- **Background Tasks**: Celery + Redis
- **WhatsApp**: Twilio or Interakt API integration
- **Validation**: Marshmallow schemas
- **API Structure**: Flask Blueprints with RESTful design
- **Security**: Werkzeug password hashing, JWT tokens

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- MongoDB Atlas account
- Redis server
- WhatsApp API credentials (Twilio or Interakt)

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd adrilly-web

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file:

```env
# Database
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/adrilly?retryWrites=true&w=majority

# Security
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# WhatsApp API (Choose one)
# Twilio
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Interakt (Alternative)
INTERAKT_API_KEY=your-interakt-api-key
INTERAKT_PHONE_NUMBER=+1234567890

# App Configuration
FLASK_ENV=development
APP_HOST=0.0.0.0
APP_PORT=5000
```

### 3. Initialize Database

```bash
# Initialize database and collections (run this first)
python init_database.py

# Create sample multi-tenant data (optional)
python seed_data.py
```

### 4. Start Services

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Flask app
python run.py

# Terminal 3: Start Celery worker
python celery_worker.py
```

### 5. Test Authentication

```bash
# Run authentication tests
python test_auth.py
```

## 👤 Default Login Credentials

### Super Administrator
- **Phone**: `+1000000000`
- **Password**: `superadmin123`
- **Capabilities**: Create organizations, manage everything

### Elite Sports Academy
- **Org Admin**: `+1234567890` / `admin123`
- **Coach Admin**: `+1234567891` / `coach123`
- **Coaches**: `+123456789X` / `coach123-125`
- **Students**: `+12345678XX` (12 students)

### Champions Training Center
- **Org Admin**: `+1987654321` / `admin456`
- **Coach Admin**: `+1987654322` / `coach789`
- **Coaches**: `+19876543XX` / `coach456-457`
- **Students**: `+19876543XX` (8 students)

## 🔌 API Documentation

### Authentication Endpoints

#### Password Login
```bash
POST /api/auth/login
{
  "phone_number": "+1234567890",
  "password": "admin123"
}
```

#### OTP Request
```bash
POST /api/auth/request-otp
{
  "phone_number": "+1999999999"
}
```

#### OTP Verification
```bash
POST /api/auth/verify-otp
{
  "phone_number": "+1999999999",
  "otp": "123456",
  "name": "New User"
}
```

#### Organization Creation (Super Admin)
```bash
POST /api/auth/create-organization
Authorization: Bearer <super_admin_token>
{
  "name": "New Sports Center",
  "admin_phone": "+1555555555",
  "admin_name": "Admin Name",
  "admin_password": "admin123",
  "sports": ["football", "basketball"]
}
```

#### User Registration (Org Admin/Coach Admin)
```bash
POST /api/auth/register-user
Authorization: Bearer <admin_token>
{
  "phone_number": "+1666666666",
  "name": "New Student",
  "role": "student",
  "organization_id": "org_id_here"
}
```

### User Management

#### List Users (with filters)
```bash
GET /api/users?role=student&page=1&per_page=20
Authorization: Bearer <token>
```

#### Update User Role
```bash
PUT /api/users/{user_id}/role
Authorization: Bearer <admin_token>
{
  "role": "coach"
}
```

#### Create Group
```bash
POST /api/users/groups
Authorization: Bearer <admin_token>
{
  "name": "Advanced Football",
  "sport": "football",
  "level": "advanced",
  "coach_id": "coach_id_here",
  "max_students": 15
}
```

#### Assign User to Group
```bash
POST /api/users/groups/{group_id}/assign-user
Authorization: Bearer <token>
{
  "user_id": "student_id_here"
}
```

### Organization Stats
```bash
GET /api/users/organizations/stats?organization_id=org_id
Authorization: Bearer <admin_token>
```

## 🎯 Role-Based Permissions

### Super Admin
- Create and manage all organizations
- Access all data across organizations
- System-wide settings and billing

### Organization Admin
- Manage their organization
- Create/manage coaches and students
- Organization settings and reports

### Coach Admin
- Manage coaches and students in their org
- Class scheduling and management
- Progress tracking and reports

### Coach
- Manage assigned students and classes
- Mark attendance and track progress
- View own class schedules

### Student
- View own profile and classes
- RSVP for classes via WhatsApp
- View own progress and payments
- Access equipment marketplace

## 🧪 Testing

### Authentication Flow Test
```bash
python test_auth.py
```

### API Testing with curl
```bash
# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890", "password": "admin123"}'

# Get profile
curl -X GET http://localhost:5000/api/auth/profile \
  -H "Authorization: Bearer YOUR_TOKEN"

# List users
curl -X GET http://localhost:5000/api/users \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### WhatsApp Webhook Test
```bash
curl -X POST http://localhost:5000/api/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "from": "+1234567800",
      "text": {"body": "YES"}
    }]
  }'
```

## 🔧 Configuration

### Environment Variables
- `MONGODB_URI`: MongoDB connection string
- `SECRET_KEY`: Flask application secret
- `JWT_SECRET_KEY`: JWT signing key
- `TWILIO_*`: Twilio WhatsApp credentials
- `INTERAKT_*`: Interakt WhatsApp credentials
- `CELERY_*`: Redis connection for background tasks

### Multi-Tenant Settings
- Each organization has isolated data
- Users can only access their organization's data
- Super admins have cross-organization access
- JWT tokens include organization context

### WhatsApp Integration
- Supports both Twilio and Interakt
- Automatic provider fallback
- Configurable message templates
- Real-time RSVP processing

## 🚀 Production Deployment

### Using Gunicorn
```bash
# Install gunicorn (included in requirements.txt)
pip install gunicorn

# Start with multiple workers
gunicorn -w 4 -b 0.0.0.0:8000 run:app
```

### Environment Setup
```bash
# Set production environment
export FLASK_ENV=production

# Use production MongoDB
export MONGODB_URI="your-production-mongodb-uri"

# Configure Redis for production
export CELERY_BROKER_URL="redis://production-redis:6379/0"
```

### Background Tasks
```bash
# Start Celery worker
celery -A app.celery worker --loglevel=info

# Start Celery beat (for periodic tasks)
celery -A app.celery beat --loglevel=info
```

## 📖 Additional Documentation

- **API Examples**: See `API_Examples.md` for detailed API documentation
- **Database Schema**: Check model files in `app/models/`
- **Background Tasks**: Review `app/tasks/reminder_tasks.py`
- **Authentication Flow**: Study `app/services/auth_service.py`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

---

**Built with ❤️ for sports coaching communities worldwide** 🏅 