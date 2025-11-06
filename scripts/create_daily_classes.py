#!/usr/bin/env python3
"""
Create Daily Classes
Creates classes for the next N days based on schedule items.
"""

import os
import sys
import argparse
from bson import ObjectId

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    parser = argparse.ArgumentParser(description='Create daily classes')
    parser.add_argument('--days-ahead', type=int, default=7, help='Number of days ahead to create classes (default: 7)')
    parser.add_argument('--org-id', type=str, help='Optional organization ID (creates for all orgs if not specified)')
    args = parser.parse_args()
    
    try:
        from app.app import create_app
        from app.tasks.class_creation_tasks import create_daily_classes_function
        
        app, _ = create_app()
        
        with app.app_context():
            org_id = ObjectId(args.org_id) if args.org_id else None
            result = create_daily_classes_function(days_ahead=args.days_ahead, org_id=org_id)
            
            if result.get('success'):
                print(f"✅ Created {result['created_classes']} classes")
                if result.get('cleaned_classes', 0) > 0:
                    print(f"   Cleaned up {result['cleaned_classes']} old classes")
            else:
                print(f"❌ Error: {result.get('error')}")
                return 1
            
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
