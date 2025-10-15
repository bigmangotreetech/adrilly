# botle Sports Coaching - Startup Guide

This guide explains how to start the application with all necessary scripts and Celery tasks properly configured.

## 🚀 Quick Start

### Option 1: Automated Startup (Recommended)

**Windows:**
```batch
# Double-click or run in Command Prompt
start.bat
```

**Linux/macOS:**
```bash
# Make executable (first time only)
chmod +x start.sh

# Run the startup script
./start.sh
```

### Option 2: Manual Startup

1. **Initialize the system:**
   ```bash
   python startup.py
   ```

2. **Start Redis (required for Celery):**
   ```bash
   # Windows (if installed)
   redis-server
   
   # Linux/macOS
   redis-server --daemonize yes
   ```

3. **Start Celery worker:**
   ```bash
   python celery_worker.py
   ```

4. **Start Celery beat scheduler (in separate terminal):**
   ```bash
   python -m celery -A celery_worker.celery beat --loglevel=info
   ```

5. **Start Flask application:**
   ```bash
   python run.py
   ```

## 🔧 Management Commands

Use the `manage.py` script for various operations:

### Database Management
```bash
# Initialize database and collections
python manage.py init-db

# Seed with sample data
python manage.py seed
```

### Class Management
```bash
# Create classes for next 7 days
python manage.py create-classes

# Create classes for specific organization
python manage.py create-classes --org-id 507f1f77bcf86cd799439011

# Create classes for next 14 days
python manage.py create-classes --days 14
```

### Holiday Management
```bash
# Import holidays for current year
python manage.py import-holidays

# Import holidays for specific year
python manage.py import-holidays --year 2024
```

### System Operations
```bash
# Run complete startup initialization
python manage.py startup

# Check system status
python manage.py status

# Run system tests
python manage.py test

# Start Celery worker
python manage.py celery-worker

# Start Celery beat scheduler
python manage.py celery-beat
```

## 🔄 Automated Tasks

The system automatically runs these tasks when properly configured:

### Periodic Tasks (Celery Beat)

| Task | Schedule | Description |
|------|----------|-------------|
| **Class Reminders** | Every 30 minutes | Send WhatsApp reminders 2 hours before classes |
| **Payment Reminders** | Daily at 9 AM | Send payment overdue notifications |
| **Recurring Payments** | Daily at 6 AM | Generate recurring payment entries |
| **Class Status Updates** | Every 15 minutes | Update class status (completed/cancelled) |
| **OTP Cleanup** | Every hour | Remove expired OTP codes |
| **Daily Class Creation** | Daily at 6 AM | Create classes for next 7 days |
| **Holiday Import** | Dec 31 at 11 PM | Import holidays for next year |
| **Holiday Sync** | Weekly on Sunday 3 AM | Sync master holidays with organizations |
| **Class Cleanup** | Weekly on Sunday 2 AM | Archive old completed classes |
| **Holiday Cleanup** | Monthly on 1st at 4 AM | Remove old holiday data |

### Startup Initialization

When the app starts, it automatically:

1. ✅ **Database Connection** - Verifies MongoDB connectivity
2. ✅ **Collections Setup** - Creates required MongoDB collections
3. ✅ **Celery Tasks** - Registers all background tasks
4. ✅ **Class Creation** - Creates initial classes if none exist
5. ✅ **Holiday Import** - Imports master holidays if missing
6. ✅ **Periodic Tasks** - Configures scheduled tasks

## 🛠️ Configuration

### Environment Variables

Create a `.env` file with:

```env
# Database
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/adrilly

# Security
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# Celery (Redis required)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Skip startup initialization (optional)
SKIP_STARTUP_INIT=false

# Flask settings
FLASK_ENV=development
APP_HOST=0.0.0.0
APP_PORT=5000
DEBUG=true
```

### Startup Control

- Set `SKIP_STARTUP_INIT=true` to skip automatic initialization
- Use `python startup.py --task <task_name>` to run specific initialization tasks
- Available tasks: `database`, `collections`, `celery`, `classes`, `holidays`, `periodic`

## 📊 Monitoring

### Check System Status
```bash
python manage.py status
```

### View Celery Tasks
```bash
# Monitor Celery worker
celery -A celery_worker.celery events

# View active tasks
celery -A celery_worker.celery inspect active

# View scheduled tasks
celery -A celery_worker.celery inspect scheduled
```

### Logs

Logs are written to:
- `logs/startup.log` - Startup initialization logs
- Console output for real-time monitoring

## 🚨 Troubleshooting

### Common Issues

1. **Redis Connection Error**
   - Install Redis: https://redis.io/download
   - Start Redis server before starting the app

2. **MongoDB Connection Error**
   - Check `MONGODB_URI` in `.env`
   - Ensure MongoDB Atlas cluster is running
   - Verify network connectivity

3. **Celery Tasks Not Running**
   - Ensure Redis is running
   - Check Celery worker is started
   - Verify task imports in `celery_worker.py`

4. **Classes Not Being Created**
   - Check if `daily_class_creator.py` exists
   - Verify center schedules are configured
   - Check organization and center `is_active` status

5. **Holidays Not Importing**
   - Verify internet connection for API calls
   - Check if `fetch_indian_holidays.py` exists
   - Review holiday import logs

### Manual Recovery

If automatic startup fails:

```bash
# Run each step manually
python manage.py init-db
python manage.py import-holidays
python manage.py create-classes
python manage.py test
```

## 🔄 Development Mode

For development, you can disable certain features:

```bash
# Skip startup initialization
export SKIP_STARTUP_INIT=true

# Run without Celery
python run.py

# Run specific initialization only
python startup.py --task database
```

## 📞 Support

If you encounter issues:

1. Check the logs in `logs/` directory
2. Run `python manage.py test` to verify system health
3. Use `python manage.py status` to check component status
4. Review this guide for configuration options

---

**Note:** The automated startup scripts (`start.bat`/`start.sh`) handle all the complexity for you. Use them for the easiest experience!
