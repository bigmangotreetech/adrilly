# Standalone Task Scripts

This folder contains standalone scripts for running Celery tasks without a Celery worker. Each script can be executed directly from the command line.

## Usage

All scripts should be run from the project root directory:

```bash
python scripts/<script_name>.py [arguments]
```

## Available Scripts

### Class Management

#### `update_class_statuses.py`
Updates class statuses based on current time:
- Marks classes as "ongoing" if they've started
- Marks classes as "completed" if the end time has passed

**Usage:**
```bash
python scripts/update_class_statuses.py
```

**When to run:** Every 15 minutes (or as needed)

---

### Reminders & Notifications

#### `send_class_reminders.py`
Sends WhatsApp reminders to students for upcoming classes.

**Usage:**
```bash
python scripts/send_class_reminders.py [--hours-before=2]
```

**Arguments:**
- `--hours-before`: Hours before class to send reminder (default: 2)

**When to run:** Every 30 minutes

---

#### `send_organization_class_reminders.py`
Sends class reminders based on each organization's reminder settings.

**Usage:**
```bash
python scripts/send_organization_class_reminders.py
```

**When to run:** Every minute

---

#### `send_payment_reminders.py`
Sends payment reminders for overdue and upcoming payments.

**Usage:**
```bash
python scripts/send_payment_reminders.py
```

**When to run:** Daily at 9:00 AM

---

#### `send_welcome_messages.py`
Sends welcome messages to new users who joined in the last 24 hours.

**Usage:**
```bash
python scripts/send_welcome_messages.py
```

**When to run:** Daily at 10:00 AM

---

#### `send_daily_digest.py`
Sends daily digest messages to coaches and admins with tomorrow's schedule.

**Usage:**
```bash
python scripts/send_daily_digest.py
```

**When to run:** Daily at 8:00 PM

---

### Class Creation

#### `create_daily_classes.py`
Creates classes for the next N days based on schedule items.

**Usage:**
```bash
python scripts/create_daily_classes.py [--days-ahead=7] [--org-id=ORG_ID]
```

**Arguments:**
- `--days-ahead`: Number of days ahead to create classes (default: 7)
- `--org-id`: Optional organization ID (creates for all orgs if not specified)

**When to run:** Daily at 6:00 AM

**Example:**
```bash
python scripts/create_daily_classes.py --days-ahead=7
python scripts/create_daily_classes.py --days-ahead=14 --org-id=507f1f77bcf86cd799439011
```

---

### Billing & Payments

#### `process_billing_cycles.py`
Processes billing cycles for users with subscriptions and marks payments as due.

**Usage:**
```bash
python scripts/process_billing_cycles.py
```

**When to run:** Daily at 12:01 AM

---

#### `mark_overdue_payments.py`
Marks payments as overdue if they're past due date and still pending.

**Usage:**
```bash
python scripts/mark_overdue_payments.py
```

**When to run:** Daily at 12:30 AM

---

#### `generate_recurring_payments.py`
Generates payments for active payment plans.

**Usage:**
```bash
python scripts/generate_recurring_payments.py
```

**When to run:** Daily (recommended: 6:00 AM)

---

### Maintenance & Cleanup

#### `cleanup_expired_otps.py`
Cleans up expired OTP codes from the database.

**Usage:**
```bash
python scripts/cleanup_expired_otps.py
```

**When to run:** Hourly

---

#### `cleanup_old_whatsapp_logs.py`
Cleans up old WhatsApp logs older than 90 days.

**Usage:**
```bash
python scripts/cleanup_old_whatsapp_logs.py
```

**When to run:** Weekly on Sunday at 2:00 AM

---

#### `generate_whatsapp_analytics.py`
Generates daily WhatsApp analytics reports for organizations.

**Usage:**
```bash
python scripts/generate_whatsapp_analytics.py
```

**When to run:** Daily at 11:00 PM

---

### Holiday Management

#### `import_yearly_holidays.py`
Imports holidays for a specific year.

**Usage:**
```bash
python scripts/import_yearly_holidays.py [--year=2024] [--country-code=IN]
```

**Arguments:**
- `--year`: Year to import holidays for (default: current year)
- `--country-code`: Country code (default: IN)

**Example:**
```bash
python scripts/import_yearly_holidays.py --year=2024
```

---

#### `sync_organization_holidays.py`
Syncs master holidays with organization holidays.

**Usage:**
```bash
python scripts/sync_organization_holidays.py [--org-id=ORG_ID]
```

**Arguments:**
- `--org-id`: Optional organization ID (syncs for all orgs if not specified)

**When to run:** Weekly on Sunday at 3:00 AM

---

#### `cleanup_expired_holidays.py`
Cleans up old holidays that are no longer relevant (older than 2 years).

**Usage:**
```bash
python scripts/cleanup_expired_holidays.py
```

**When to run:** Monthly on the 1st at 4:00 AM

---

#### `validate_holiday_data.py`
Validates holiday data integrity and checks for issues.

**Usage:**
```bash
python scripts/validate_holiday_data.py
```

**When to run:** Weekly on Monday at 9:00 AM

---

## Setting Up Cron Jobs (Linux/Mac)

To automate these scripts, add them to your crontab:

```bash
crontab -e
```

Example crontab entries:

```cron
# Update class statuses every 15 minutes
*/15 * * * * cd /path/to/project && python scripts/update_class_statuses.py

# Send class reminders every 30 minutes
*/30 * * * * cd /path/to/project && python scripts/send_class_reminders.py

# Process billing cycles daily at midnight
1 0 * * * cd /path/to/project && python scripts/process_billing_cycles.py

# Create daily classes at 6 AM
0 6 * * * cd /path/to/project && python scripts/create_daily_classes.py
```

## Setting Up Scheduled Tasks (Windows)

Use Task Scheduler to run these scripts:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (time/event)
4. Set action: Start a program
5. Program: `python`
6. Arguments: `scripts\<script_name>.py`
7. Start in: Project root directory

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running from the project root directory:
```bash
cd "adrilly web"
python scripts/update_class_statuses.py
```

### Database Connection Errors
Ensure your `.env` file has the correct MongoDB connection string:
```
MONGODB_URI=mongodb://localhost:27017/adrilly
```

### Permission Errors
On Linux/Mac, make scripts executable:
```bash
chmod +x scripts/*.py
```

## Notes

- All scripts initialize the Flask app context automatically
- Scripts output progress information to stdout
- Exit code 0 = success, 1 = error
- Scripts can be used with cron, Task Scheduler, or run manually

