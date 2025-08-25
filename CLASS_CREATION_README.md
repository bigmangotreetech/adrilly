# Automated Class Creation System

This system automatically creates classes for organizations based on their centers' schedules. It runs daily to ensure that classes are created according to the defined schedules.

## 🚀 Features

- **Automatic Class Creation**: Creates classes based on center schedules and operating hours
- **Organization Support**: Works with multiple organizations and their centers
- **Conflict Prevention**: Prevents duplicate class creation
- **Schedule-Based**: Uses existing center schedules to determine when to create classes
- **Flexible Scheduling**: Supports multiple scheduling methods (Celery, Cron, Windows Task Scheduler)
- **Cleanup**: Automatically cleans up old completed/cancelled classes

## 📁 Files

### Core Script
- `daily_class_creator.py` - Main script for creating classes based on schedules

### Scheduling
- `schedule_class_creation.py` - Setup script for different scheduling methods
- `create_classes_cron.sh` - Shell script for cron scheduling (auto-generated)
- `create_classes_task.bat` - Windows batch script for Task Scheduler (auto-generated)

### Celery Integration
- `app/tasks/enhanced_reminder_tasks.py` - Contains Celery tasks for class creation
- `app/tasks/reminder_tasks.py` - Periodic task configuration

## 🛠️ Setup

### 1. Database Requirements

The system requires the following MongoDB collections to exist:

- `organizations` - Active organizations with `is_active: true`
- `centers` - Centers belonging to organizations with `is_active: true`
- `schedules` - Weekly schedules for centers with day_of_week, time_slot_id, etc.
- `time_slots` - Time slot definitions with start_time and duration
- `activities` - Activity/sport definitions
- `classes` - Where new classes will be created

### 2. Schedule Data Structure

Centers should have schedules in this format:
```json
{
  "center_id": "ObjectId",
  "day_of_week": "monday|tuesday|...|sunday",
  "time_slot_id": "ObjectId",
  "activity_id": "ObjectId", 
  "coach_id": "ObjectId" (optional)
}
```

Time slots should have:
```json
{
  "start_time": "HH:MM",
  "duration_minutes": 60,
  "name": "Morning Session"
}
```

### 3. Environment Variables

Ensure these environment variables are set:
```bash
MONGODB_URI=mongodb://localhost:27017/sports_coaching
# or for MongoDB Atlas:
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/adrilly
```

## 📅 Usage

### Option 1: Manual Execution

```bash
# Create classes for next 7 days
python daily_class_creator.py

# Create classes for specific date
python daily_class_creator.py --date 2024-01-15

# Create classes for specific organization
python daily_class_creator.py --org-id 507f1f77bcf86cd799439011

# Create classes for next 14 days
python daily_class_creator.py --days-ahead 14

# Show statistics only
python daily_class_creator.py --stats
```

### Option 2: Automated Scheduling Setup

```bash
# Setup all scheduling methods
python schedule_class_creation.py --setup-all

# Run immediately
python schedule_class_creation.py --now

# Create just cron script
python schedule_class_creation.py --create-cron

# Create just Windows batch script  
python schedule_class_creation.py --create-windows
```

### Option 3: Celery (Recommended for Production)

The system is already integrated with Celery. Start Celery beat:

```bash
# Start Celery worker
celery -A app.celery worker --loglevel=info

# Start Celery beat scheduler (in separate terminal)
celery -A app.celery beat --loglevel=info
```

Classes will be created automatically every day at 6 AM.

### Option 4: Cron (Linux/Mac)

```bash
# Make script executable
chmod +x create_classes_cron.sh

# Add to crontab
crontab -e

# Add this line to run daily at 6 AM:
0 6 * * * /path/to/adrilly-web/create_classes_cron.sh
```

### Option 5: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" at 6:00 AM
4. Set action to run `create_classes_task.bat`

## 🔍 How It Works

1. **Fetch Organizations**: Gets all active organizations
2. **Get Centers**: For each organization, gets all active centers
3. **Check Schedules**: For each center, checks schedules for the target day
4. **Create Classes**: For each schedule item:
   - Gets time slot and activity details
   - Creates a datetime for the class
   - Checks for existing classes to prevent duplicates
   - Creates new class with proper organization_id and center_id
5. **Cleanup**: Removes old completed/cancelled classes

## 📊 Class Creation Logic

### Schedule Matching
- Matches `day_of_week` (monday, tuesday, etc.) with target date
- Uses `time_slot_id` to get start time and duration
- Uses `activity_id` to get sport/activity type
- Uses `coach_id` if specified, otherwise uses first available center coach

### Class Properties
- **Title**: "{Activity Name} - {Center Name}"
- **Organization ID**: From the center's organization
- **Coach ID**: From schedule or center's first coach
- **Scheduled At**: Target date + time slot start time
- **Duration**: From time slot (default 60 minutes)
- **Location**: Center details including center_id
- **Sport**: From activity definition
- **Status**: "scheduled"

### Duplicate Prevention
- Checks for existing classes in ±30 minute window
- Prevents creating multiple classes for same time/center/activity

## 🧹 Cleanup

The system automatically cleans up:
- Classes older than 30 days with status "completed" or "cancelled"
- This prevents database bloat while keeping recent history

## 📝 Logging

Logs are written to:
- `logs/class_creation.log` - Execution logs
- Console output during execution

## ⚠️ Error Handling

The system handles:
- Missing time slots or activities
- Invalid date formats
- Database connection issues
- Missing coach assignments
- Schedule conflicts

## 🔧 Troubleshooting

### No Classes Created
1. Check if organizations are `is_active: true`
2. Check if centers are `is_active: true` 
3. Verify schedules exist for the target day of week
4. Check time_slots and activities collections
5. Verify MongoDB connection

### Duplicate Classes
- The system prevents duplicates automatically
- Check console output for "already exists" messages

### Permission Issues
- Ensure MongoDB user has read/write access
- Check file permissions for scripts
- Verify environment variables are set

### Celery Issues
- Ensure Redis is running (for Celery broker)
- Check Celery worker and beat are started
- Verify task registration in Celery

## 📈 Monitoring

Monitor the system by:
1. Checking log files
2. Running with `--stats` to see current state
3. Monitoring Celery task execution
4. Checking database for created classes

## 🔄 Customization

To customize the system:
1. Modify `daily_class_creator.py` for different logic
2. Adjust timing in periodic task configuration
3. Change cleanup retention period
4. Modify class title generation
5. Add additional validation rules

## 📞 Support

For issues or questions:
1. Check the logs for error messages
2. Verify database schema matches expectations
3. Test with `--stats` to see system state
4. Run manually before scheduling to verify functionality
