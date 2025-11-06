#!/usr/bin/env python3
"""
Manual Celery Task Runner
Allows running Celery tasks manually when the Celery worker is not available.
This is useful for development, testing, or fallback scenarios.

Usage:
    python manual_task_runner.py list                    # List all available tasks
    python manual_task_runner.py run <task_name> [args]  # Run a specific task
    python manual_task_runner.py run-all                 # Run all tasks (not recommended)
"""

import os
import sys
import argparse
import inspect
import logging
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ManualTaskRunner:
    """Runner for executing Celery tasks manually"""
    
    def __init__(self):
        self.app = None
        self.celery = None
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._initialize_app()
        self._discover_tasks()
    
    def _initialize_app(self):
        """Initialize Flask app and Celery instance"""
        try:
            from app.app import create_app
            self.app, self.celery = create_app()
            logger.info("✅ Flask app and Celery instance initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize app: {str(e)}")
            raise
    
    def _extract_task_function(self, task):
        """Extract the actual function from a Celery task"""
        # If it's a Celery task, get the underlying function
        if hasattr(task, '__wrapped__'):
            # Regular tasks have __wrapped__ attribute
            original_func = task.__wrapped__
        elif hasattr(task, 'run'):
            # Bound tasks (bind=True) have a run method, but we want the original
            # Check if run has __wrapped__
            if hasattr(task.run, '__wrapped__'):
                original_func = task.run.__wrapped__
            else:
                original_func = task.run
        elif hasattr(task, '_decorated'):
            # Some Celery versions use _decorated
            original_func = task._decorated
        elif inspect.isfunction(task) or inspect.ismethod(task):
            # Direct function or method
            original_func = task
        elif callable(task):
            # Fallback: try to use it directly
            original_func = task
        else:
            raise ValueError(f"Cannot extract function from {type(task)}")
        
        return original_func
    
    def _discover_tasks(self):
        """Discover all available Celery tasks"""
        logger.info("🔍 Discovering available tasks...")
        
        # Note: Modules are imported in _discover_tasks to handle missing modules gracefully
        
        # Discover tasks from each module
        modules_to_register = []
        
        try:
            from app.tasks import reminder_tasks
            modules_to_register.append((reminder_tasks, 'reminder_tasks'))
        except ImportError as e:
            logger.warning(f"⚠️ Could not import reminder_tasks: {e}")
        
        try:
            from app.tasks import enhanced_reminder_tasks
            modules_to_register.append((enhanced_reminder_tasks, 'enhanced_reminder_tasks'))
        except ImportError as e:
            logger.warning(f"⚠️ Could not import enhanced_reminder_tasks: {e}")
        
        try:
            from app.tasks import class_creation_tasks
            modules_to_register.append((class_creation_tasks, 'class_creation_tasks'))
        except ImportError as e:
            logger.warning(f"⚠️ Could not import class_creation_tasks: {e}")
        
        try:
            from app.tasks import holiday_tasks
            modules_to_register.append((holiday_tasks, 'holiday_tasks'))
        except ImportError as e:
            logger.warning(f"⚠️ Could not import holiday_tasks: {e}")
        
        try:
            from app.tasks import billing_cycle_tasks
            modules_to_register.append((billing_cycle_tasks, 'billing_cycle_tasks'))
        except ImportError as e:
            logger.warning(f"⚠️ Could not import billing_cycle_tasks: {e}")
        
        for module, module_name in modules_to_register:
            self._register_tasks_from_module(module, module_name)
        
        logger.info(f"✅ Discovered {len(self.tasks)} tasks")
    
    def _register_tasks_from_module(self, module, module_name: str):
        """Register tasks from a module"""
        # Skip these - they're not actual tasks
        skip_names = {
            'setup_periodic_tasks', 'setup_holiday_periodic_tasks', 'setup_billing_periodic_tasks',
            'make_celery', 'create_app', 'ContextTask'
        }
        
        for name, obj in inspect.getmembers(module):
            # Skip private attributes, non-callable objects, and excluded names
            if name.startswith('_') or not callable(obj) or name in skip_names:
                continue
            
            # Skip if it's a class (not a function)
            if inspect.isclass(obj):
                continue
            
            # Check if it's a Celery task by checking for task-specific attributes
            is_celery_task = (
                hasattr(obj, 'task') or  # Has task attribute
                (hasattr(obj, '__call__') and hasattr(obj, 'name')) or  # Callable with name
                (hasattr(obj, 'apply_async') or hasattr(obj, 'delay'))  # Has Celery methods
            )
            
            # Also check if it's a task registered with celery
            if not is_celery_task and self.celery:
                try:
                    # Check if it's registered in Celery
                    if hasattr(obj, '__name__') and obj.__name__ in self.celery.tasks:
                        is_celery_task = True
                except:
                    pass
            
            if is_celery_task:
                try:
                    # Check if there's an underlying function first (like in class_creation_tasks)
                    underlying_func_name = f"{name}_function"
                    underlying_func = getattr(module, underlying_func_name, None)
                    
                    if underlying_func:
                        # Use underlying function
                        task_func = underlying_func
                        logger.info(f"   Using underlying function '{underlying_func_name}' for {name}")
                    else:
                        # Extract the function from Celery task
                        task_func = self._extract_task_function(obj)
                    
                    # Get function signature for help text
                    sig = inspect.signature(task_func)
                    params = list(sig.parameters.keys())
                    
                    # Remove 'self' from params if it's a bound task
                    if 'self' in params and hasattr(obj, 'bind') and obj.bind:
                        params = [p for p in params if p != 'self']
                    
                    self.tasks[name] = {
                        'module': module_name,
                        'function': task_func,
                        'signature': sig,
                        'params': params,
                        'doc': inspect.getdoc(task_func) or "No documentation available",
                        'original': obj
                    }
                    
                    logger.info(f"   ✅ Registered: {name} from {module_name}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not register {name}: {e}")
    
    def list_tasks(self):
        """List all available tasks"""
        print("\n" + "="*80)
        print("📋 AVAILABLE CELERY TASKS")
        print("="*80 + "\n")
        
        if not self.tasks:
            print("❌ No tasks found")
            return
        
        # Group by module
        by_module: Dict[str, List[str]] = {}
        for task_name, task_info in self.tasks.items():
            module = task_info['module']
            if module not in by_module:
                by_module[module] = []
            by_module[module].append(task_name)
        
        for module, task_names in sorted(by_module.items()):
            print(f"\n📦 {module.upper()}")
            print("-" * 80)
            for task_name in sorted(task_names):
                task_info = self.tasks[task_name]
                params = ', '.join(task_info['params'])
                print(f"  • {task_name}({params})")
                # Print first line of docstring
                doc_lines = task_info['doc'].split('\n')
                if doc_lines[0]:
                    print(f"    {doc_lines[0]}")
        
        print("\n" + "="*80)
        print(f"Total: {len(self.tasks)} tasks")
        print("="*80 + "\n")
    
    def run_task(self, task_name: str, args: List[str] = None, kwargs: Dict[str, Any] = None):
        """Run a specific task"""
        if task_name not in self.tasks:
            logger.error(f"❌ Task '{task_name}' not found")
            print(f"\n❌ Task '{task_name}' not found")
            print(f"\nAvailable tasks:")
            for name in sorted(self.tasks.keys()):
                print(f"  • {name}")
            return False
        
        task_info = self.tasks[task_name]
        task_func = task_info['function']
        sig = task_info['signature']
        
        # Parse arguments
        parsed_args = []
        parsed_kwargs = {}
        
        if args:
            parsed_args = args
        
        if kwargs:
            parsed_kwargs = kwargs
        
        # Try to parse args from command line if provided as strings
        if args and isinstance(args[0], str):
            parsed_args = []
            parsed_kwargs = {}
            for arg in args:
                if '=' in arg:
                    # Keyword argument
                    key, value = arg.split('=', 1)
                    # Try to parse value
                    parsed_kwargs[key] = self._parse_value(value)
                else:
                    # Positional argument
                    parsed_args.append(self._parse_value(arg))
        
        print(f"\n{'='*80}")
        print(f"🚀 RUNNING TASK: {task_name}")
        print(f"{'='*80}")
        print(f"Module: {task_info['module']}")
        print(f"Function: {task_func.__name__}")
        if parsed_args:
            print(f"Args: {parsed_args}")
        if parsed_kwargs:
            print(f"Kwargs: {parsed_kwargs}")
        print(f"{'='*80}\n")
        
        try:
            # Run task with app context
            with self.app.app_context():
                start_time = datetime.utcnow()
                
                # Check if this is a bound task (has 'self' as first parameter)
                sig_params = list(sig.parameters.keys())
                is_bound_task = len(sig_params) > 0 and sig_params[0] == 'self'
                
                # For bound tasks, we need to handle the 'self' parameter
                # Most bound tasks don't actually use 'self', so we create a mock
                if is_bound_task:
                    # Create a simple mock task object for 'self'
                    class MockTask:
                        def __init__(self, name):
                            self.name = name
                            self.request = type('Request', (), {'id': None})()
                            self.retry = lambda *args, **kwargs: None  # No-op retry
                            self.update_state = lambda *args, **kwargs: None  # No-op update_state
                    
                    mock_self = MockTask(task_name)
                    # Add 'self' as first argument
                    if parsed_kwargs:
                        result = task_func(mock_self, *parsed_args, **parsed_kwargs)
                    elif parsed_args:
                        result = task_func(mock_self, *parsed_args)
                    else:
                        result = task_func(mock_self)
                else:
                    # Regular task - call normally
                    if parsed_kwargs:
                        result = task_func(*parsed_args, **parsed_kwargs)
                    elif parsed_args:
                        result = task_func(*parsed_args)
                    else:
                        result = task_func()
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                print(f"\n{'='*80}")
                print(f"✅ TASK COMPLETED SUCCESSFULLY")
                print(f"{'='*80}")
                print(f"Duration: {duration:.2f} seconds")
                print(f"Result: {result}")
                print(f"{'='*80}\n")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Task '{task_name}' failed: {str(e)}", exc_info=True)
            print(f"\n{'='*80}")
            print(f"❌ TASK FAILED")
            print(f"{'='*80}")
            print(f"Error: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            print(f"\nTraceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            return False
    
    def _parse_value(self, value: str):
        """Parse a string value to appropriate type"""
        # Try boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try None
        if value.lower() in ('none', 'null'):
            return None
        
        # Try ObjectId (MongoDB)
        if len(value) == 24:  # ObjectIds are 24 hex characters
            try:
                from bson import ObjectId
                # Validate it's a valid hex string
                int(value, 16)
                return ObjectId(value)
            except (ValueError, ImportError):
                pass
        
        # Return as string
        return value


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description='Manual Celery Task Runner - Run tasks without Celery worker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available tasks
  python manual_task_runner.py list
  
  # Run a task with no arguments
  python manual_task_runner.py run send_automated_class_reminders
  
  # Run a task with keyword arguments
  python manual_task_runner.py run create_daily_classes days_ahead=7
  
  # Run a task with ObjectId (24-character hex string is auto-converted)
  python manual_task_runner.py run create_classes_for_organization org_id=507f1f77bcf86cd799439011 days_ahead=7
  
  # Run a task with multiple arguments
  python manual_task_runner.py run import_yearly_holidays year=2024 country_code=IN
  
  # Run a bound task (tasks with bind=True, self parameter is handled automatically)
  python manual_task_runner.py run import_yearly_holidays year=2024

Note: ObjectIds (MongoDB IDs) are automatically detected and converted if they are
24-character hexadecimal strings. Other argument types (int, float, bool, None) are
also automatically parsed.
        """
    )
    
    parser.add_argument(
        'command',
        choices=['list', 'run'],
        help='Command to execute: list (show all tasks) or run (execute a task)'
    )
    
    parser.add_argument(
        'task_name',
        nargs='?',
        help='Name of the task to run (required for "run" command)'
    )
    
    parser.add_argument(
        'args',
        nargs='*',
        help='Arguments to pass to the task (format: arg1 arg2 key=value)'
    )
    
    args = parser.parse_args()
    
    try:
        runner = ManualTaskRunner()
        
        if args.command == 'list':
            runner.list_tasks()
            return 0
        elif args.command == 'run':
            if not args.task_name:
                print("❌ Task name is required for 'run' command")
                parser.print_help()
                return 1
            
            success = runner.run_task(args.task_name, args.args)
            return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}", exc_info=True)
        print(f"\n❌ Fatal error: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
