#!/usr/bin/env python3
"""
Script to fix email and phone_number indexes in the database.
This script drops old non-sparse unique indexes and creates new sparse unique indexes
to allow multiple NULL values while maintaining uniqueness for non-NULL values.
"""

import os
import sys
from app.app import create_app
from app.extensions import mongo

def fix_indexes():
    """Drop old indexes and create new sparse indexes"""
    print("Fixing email and phone_number indexes...")
    print("=" * 50)
    
    # Create Flask app context
    app, _ = create_app()
    
    with app.app_context():
        try:
            # Get all indexes for users collection
            existing_indexes = mongo.db.users.list_indexes()
            print("\nExisting indexes:")
            index_names = []
            for index in existing_indexes:
                index_name = index.get('name', 'unknown')
                index_keys = index.get('key', {})
                is_sparse = index.get('sparse', False)
                is_unique = index.get('unique', False)
                index_names.append(index_name)
                print(f"   - {index_name}: {index_keys} (unique={is_unique}, sparse={is_sparse})")
            
            # Drop old non-sparse indexes
            indexes_to_drop = ['email_1', 'phone_number_1']
            
            print("\nDropping old indexes...")
            for index_name in indexes_to_drop:
                try:
                    mongo.db.users.drop_index(index_name)
                    print(f"   [OK] Dropped index: {index_name}")
                except Exception as e:
                    if 'index not found' in str(e).lower() or 'not found' in str(e).lower():
                        print(f"   [SKIP] Index {index_name} not found (already removed)")
                    else:
                        print(f"   [WARN] Could not drop {index_name}: {e}")
            
            # Create new sparse indexes
            print("\nCreating new sparse indexes...")
            try:
                mongo.db.users.create_index("email", unique=True, sparse=True, name="email_1")
                print("   [OK] Created sparse unique index on email")
            except Exception as e:
                print(f"   [WARN] Could not create email index: {e}")
            
            try:
                mongo.db.users.create_index("phone_number", unique=True, sparse=True, name="phone_number_1")
                print("   [OK] Created sparse unique index on phone_number")
            except Exception as e:
                print(f"   [WARN] Could not create phone_number index: {e}")
            
            # Verify new indexes
            print("\nVerifying new indexes...")
            new_indexes = mongo.db.users.list_indexes()
            for index in new_indexes:
                index_name = index.get('name', 'unknown')
                if index_name in ['email_1', 'phone_number_1']:
                    index_keys = index.get('key', {})
                    is_sparse = index.get('sparse', False)
                    is_unique = index.get('unique', False)
                    status = "[OK]" if (is_sparse and is_unique) else "[FAIL]"
                    print(f"   {status} {index_name}: {index_keys} (unique={is_unique}, sparse={is_sparse})")
            
            print("\nIndex fix completed!")
            print("=" * 50)
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Error fixing indexes: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("Email/Phone Index Fix Script")
    print("=" * 50)
    success = fix_indexes()
    sys.exit(0 if success else 1)

