#!/usr/bin/env python3
"""
Independent script to update all users to use organization_ids array.
No Flask dependencies required!

This script:
1. Finds all users with organization_id but without organization_ids
2. Creates organization_ids array from organization_id
3. Updates the users in the database

Usage:
    python update_users_to_multi_org.py
    python update_users_to_multi_org.py --verify
"""

import sys
import os
from datetime import datetime

def get_mongodb_connection():
    """Get MongoDB connection without Flask"""
    try:
        from pymongo import MongoClient
    except ImportError:
        print("ERROR: pymongo not installed!")
        print("Install it with: pip install pymongo")
        sys.exit(1)
    
    # Try environment variable first
    mongodb_uri = os.environ.get('MONGODB_URI')
    
    # Try to read from config.py
    if not mongodb_uri:
        try:
            import importlib.util
            config_path = os.path.join(os.path.dirname(__file__), 'config.py')
            
            if os.path.exists(config_path):
                spec = importlib.util.spec_from_file_location("config", config_path)
                config = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config)
                
                if hasattr(config, 'Config'):
                    mongodb_uri = getattr(config.Config, 'MONGODB_URI', None)
        except Exception:
            pass
    
    # Default fallback
    if not mongodb_uri:
        mongodb_uri = 'mongodb://localhost:27017/coaching_app'
    
    # Parse database name
    db_name = 'coaching_app'
    if '/' in mongodb_uri:
        parts = mongodb_uri.split('/')
        if len(parts) >= 4:
            db_name = parts[-1].split('?')[0]
    
    # Connect
    client = MongoClient(mongodb_uri)
    db = client[db_name]
    
    # Test connection
    try:
        client.server_info()
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    return db, client

def update_users_to_multi_org(db):
    """Update all users to have organization_ids array"""
    
    print("=" * 70)
    print("UPDATING USERS TO MULTI-ORGANIZATION SUPPORT")
    print("=" * 70)
    print()
    
    # Find all users
    all_users = list(db.users.find({}))
    total = len(all_users)
    
    print(f"📊 Found {total} total users in database")
    print()
    
    # Count users by status
    already_migrated = 0
    needs_migration = 0
    no_org = 0
    
    for user in all_users:
        if user.get('organization_ids'):
            already_migrated += 1
        elif user.get('organization_id'):
            needs_migration += 1
        else:
            no_org += 1
    
    print(f"✅ Already migrated:  {already_migrated}")
    print(f"🔄 Need migration:    {needs_migration}")
    print(f"⚠️  No organization:  {no_org}")
    print()
    
    if needs_migration == 0:
        print("✨ All users are already migrated! Nothing to do.")
        return
    
    print(f"🚀 Starting migration of {needs_migration} users...")
    print("-" * 70)
    
    updated = 0
    errors = 0
    
    for user in all_users:
        # Skip if already has organization_ids
        if user.get('organization_ids'):
            continue
        
        user_id = user['_id']
        user_name = user.get('name', 'Unknown')
        org_id = user.get('organization_id')
        
        try:
            if org_id:
                # Create organization_ids array from organization_id
                organization_ids = [org_id]
                
                # Update user
                result = db.users.update_one(
                    {'_id': user_id},
                    {
                        '$set': {
                            'organization_ids': organization_ids,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated += 1
                    print(f"✓ {updated}/{needs_migration}: Updated '{user_name}' (ID: {user_id})")
                
            else:
                # User has no organization - set empty array
                result = db.users.update_one(
                    {'_id': user_id},
                    {
                        '$set': {
                            'organization_ids': [],
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated += 1
                    print(f"⚠ {updated}/{needs_migration}: Updated '{user_name}' (no org) (ID: {user_id})")
                    
        except Exception as e:
            errors += 1
            print(f"✗ Error updating '{user_name}' (ID: {user_id}): {str(e)}")
    
    print("-" * 70)
    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print(f"Total users:       {total}")
    print(f"Already migrated:  {already_migrated}")
    print(f"Updated now:       {updated}")
    print(f"Errors:            {errors}")
    print("=" * 70)
    
    if errors > 0:
        print()
        print("⚠️  WARNING: Some users had errors. Please review the output above.")
    else:
        print()
        print("✅ SUCCESS: All users have been migrated to multi-organization support!")
    
    print()
    print("Next steps:")
    print("1. Restart your application")
    print("2. Test user login and organization features")
    print("3. Verify users can access their organizations")
    
    return updated, errors

def verify_migration(db):
    """Verify that all users have organization_ids"""
    
    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print()
    
    # Get counts
    total_users = db.users.count_documents({})
    users_with_org_ids = db.users.count_documents({'organization_ids': {'$exists': True}})
    users_no_org_ids = total_users - users_with_org_ids
    
    # Get users with multiple orgs
    users_multi_org = db.users.count_documents({
        'organization_ids': {'$exists': True},
        '$expr': {'$gt': [{'$size': '$organization_ids'}, 1]}
    })
    
    # Get users with no orgs
    users_no_orgs = db.users.count_documents({
        '$or': [
            {'organization_ids': {'$size': 0}},
            {'organization_ids': {'$exists': False}}
        ]
    })
    
    print(f"Total users:                   {total_users}")
    print(f"Users with organization_ids:   {users_with_org_ids}")
    print(f"Users WITHOUT organization_ids: {users_no_org_ids}")
    print(f"Users with multiple orgs:      {users_multi_org}")
    print(f"Users with no organizations:   {users_no_orgs}")
    print()
    
    if users_no_org_ids == 0:
        print("✅ PASS: All users have organization_ids field")
        return True
    else:
        print(f"❌ FAIL: {users_no_org_ids} users are missing organization_ids field")
        print()
        print("Missing users:")
        missing_users = db.users.find(
            {'organization_ids': {'$exists': False}},
            {'_id': 1, 'name': 1, 'organization_id': 1}
        ).limit(10)
        
        for user in missing_users:
            print(f"  - {user.get('name', 'Unknown')} (ID: {user['_id']}, org: {user.get('organization_id', 'None')})")
        
        return False

if __name__ == '__main__':
    # Get MongoDB connection
    db, client = get_mongodb_connection()
    
    try:
        # Check for command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--verify' or sys.argv[1] == '-v':
                verify_migration(db)
                sys.exit(0)
            elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
                print("Usage:")
                print("  python update_users_to_multi_org.py          # Run migration")
                print("  python update_users_to_multi_org.py --verify # Verify migration")
                print("  python update_users_to_multi_org.py --help   # Show this help")
                print()
                print("Environment Variables:")
                print("  MONGODB_URI - MongoDB connection string")
                sys.exit(0)
        
        # Run migration
        print()
        print("⚠️  IMPORTANT: Make sure you have backed up your database before proceeding!")
        print()
        
        # Ask for confirmation
        response = input("Do you want to proceed with the migration? (yes/no): ").lower().strip()
        
        if response not in ['yes', 'y']:
            print("Migration cancelled.")
            sys.exit(0)
        
        print()
        
        # Run migration
        updated, errors = update_users_to_multi_org(db)
        
        # Run verification
        if errors == 0:
            print()
            verify_migration(db)
    
    finally:
        # Close connection
        client.close()

