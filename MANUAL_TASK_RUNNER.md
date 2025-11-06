# Manual Celery Task Runner

A utility for running Celery tasks manually when the Celery worker is not available. This is useful for:
- Development and testing
- Debugging tasks
- Running one-off tasks
- Fallback scenarios when Celery is down

## Features

- ✅ **Automatic Task Discovery**: Discovers all Celery tasks from all task modules
- ✅ **Code Reuse**: Automatically uses underlying functions when available (e.g., `create_daily_classes_function`)
- ✅ **Smart Argument Parsing**: Automatically converts argument types (int, float, bool, None, ObjectId)
- ✅ **Bound Task Support**: Handles tasks with `bind=True` automatically
- ✅ **Flask Context**: Runs tasks with proper Flask application context
- ✅ **Graceful Error Handling**: Provides detailed error messages and tracebacks

## Usage

### List All Available Tasks

```bash
python manual_task_runner.py list
```

This will show all available tasks grouped by module, with their signatures and descriptions.

### Run a Task

```bash
python manual_task_runner.py run <task_name> [arguments]
```

#### Examples

**Run a task with no arguments:**
```bash
python manual_task_runner.py run send_automated_class_reminders
```

**Run a task with keyword arguments:**
```bash
python manual_task_runner.py run create_daily_classes days_ahead=7
```

**Run a task with ObjectId (auto-converted):**
```bash
python manual_task_runner.py run create_classes_for_organization org_id=507f1f77bcf86cd799439011 days_ahead=7
```

**Run a task with multiple arguments:**
```bash
python manual_task_runner.py run import_yearly_holidays year=2024 country_code=IN
```

**Run a bound task (tasks with `bind=True`):**
```bash
python manual_task_runner.py run import_yearly_holidays year=2024
```

## Argument Format

Arguments can be provided in two formats:

1. **Keyword arguments**: `key=value`
   - Example: `days_ahead=7`, `org_id=507f1f77bcf86cd799439011`
   
2. **Positional arguments**: Just the value
   - Example: `7`, `hello`

### Automatic Type Conversion

The runner automatically converts argument values to appropriate types:

- **Integers**: `7` → `int(7)`
- **Floats**: `3.14` → `float(3.14)`
- **Booleans**: `true` → `True`, `false` → `False`
- **None**: `none` or `null` → `None`
- **ObjectIds**: 24-character hex strings → `ObjectId(...)`
- **Strings**: Everything else → `str`

## Available Task Modules

The runner discovers tasks from the following modules:

1. **reminder_tasks** - Basic reminder tasks
2. **enhanced_reminder_tasks** - Enhanced reminder and notification tasks
3. **class_creation_tasks** - Automated class creation
4. **holiday_tasks** - Holiday management and import
5. **billing_cycle_tasks** - Billing cycle processing

## Code Reuse

The runner efficiently reuses underlying functions when available. For example:

- `create_daily_classes` → uses `create_daily_classes_function` if available
- `create_classes_for_organization` → uses `create_classes_for_organization_function` if available

This ensures that the same code path is used whether the task runs via Celery or manually.

## Error Handling

If a task fails, the runner will:
1. Display the error message
2. Show the error type
3. Print a full traceback for debugging
4. Return a non-zero exit code

## Limitations

- Tasks that depend on Celery-specific features (like `self.retry()` or `self.update_state()`) will work, but those calls will be no-ops
- Tasks designed to run in a distributed environment won't have access to Celery's result backend
- Long-running tasks will block until completion (no async execution)

## Exit Codes

- `0` - Success
- `1` - Failure (task error, invalid arguments, etc.)

## Examples

```bash
# List all tasks
python manual_task_runner.py list

# Send class reminders
python manual_task_runner.py run send_automated_class_reminders

# Create classes for next 7 days
python manual_task_runner.py run create_daily_classes days_ahead=7

# Import holidays for 2024
python manual_task_runner.py run import_yearly_holidays year=2024

# Process billing cycles
python manual_task_runner.py run process_billing_cycles

# Mark overdue payments
python manual_task_runner.py run mark_overdue_payments
```
