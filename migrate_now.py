#!/usr/bin/env python3
"""
Independent migration script for multi-organization support.
No Flask dependencies required!

Usage: 
    python migrate_now.py
    
    # Or with custom MongoDB URI
    MONGODB_URI="mongodb://localhost:27017/mydb" python migrate_now.py
"""

import os
import sys
from datetime import datetime

def get_mongodb_uri():
    """Get MongoDB URI from environment or use default"""
    # Try environment variable first
    uri = os.environ.get('MONGODB_URI')
    
    if uri:
        return uri
    
    # Try to read from config.py
    try:
        import importlib.util
        config_path = os.path.join(os.path.dirname(__file__), 'config.py')
        
        if os.path.exists(config_path):
            spec = importlib.util.spec_from_file_location("config", config_path)
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
            
            if hasattr(config, 'Config'):
                return getattr(config.Config, 'MONGODB_URI', None)
    except Exception as e:
        print(f"Warning: Could not read config.py: {e}")
    
    # Default fallback
    return 'mongodb://localhost:27017/coaching_app'

def parse_mongodb_uri(uri):
    """Parse MongoDB URI to get database name"""
    # Simple parser for mongodb://host:port/database format
    if '/' in uri:
        parts = uri.split('/')
        if len(parts) >= 4:
            db_name = parts[-1].split('?')[0]  # Remove query params
            return db_name
    
    return 'coaching_app'  # Default database name

def migrate():
    """Run the migration"""
    try:
        # Import pymongo
        try:
            from pymongo import MongoClient
        except ImportError:
            print("ERROR: pymongo not installed!")
            print("Install it with: pip install pymongo")
            sys.exit(1)
        
        # Get MongoDB connection
        mongodb_uri = get_mongodb_uri()
        db_name = 'adrilly'
        
        print(f"Connecting to MongoDB...")
        print(f"URI: {mongodb_uri.replace(mongodb_uri.split('@')[-1] if '@' in mongodb_uri else '', '***')}")
        print(f"Database: {db_name}")
        print()
        
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        # Test connection
        try:
            client.server_info()
            print("✓ Connected to MongoDB successfully!")
        except Exception as e:
            print(f"✗ Failed to connect to MongoDB: {e}")
            print("\nTroubleshooting:")
            print("1. Make sure MongoDB is running")
            print("2. Check MONGODB_URI environment variable")
            print("3. Verify connection string is correct")
            sys.exit(1)
        
        print()
        
        # Get all users
        all_users = list(db.users.find({}))
        updated = 0
        skipped = 0
        
        print(f"Found {len(all_users)} users in database")
        print(f"Starting migration...")
        print("-" * 60)
        
        for user in all_users:
            # Skip if already has organization_ids
            if user.get('organization_ids'):
                skipped += 1
                continue
            
            # Get organization_id and convert to array
            org_id = user.get('organization_id')
            org_ids = [org_id] if org_id else []
            
            # Update user
            db.users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'organization_ids': org_ids,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            updated += 1
            
            # Show progress every 10 users
            if updated % 10 == 0:
                print(f"  Processed {updated + skipped}/{len(all_users)} users...")
        
        print("-" * 60)
        print()
        print(f"✓ Migration complete!")
        print(f"  Total users:      {len(all_users)}")
        print(f"  Updated:          {updated}")
        print(f"  Already migrated: {skipped}")
        print()
        
        # Verify migration
        print("Verifying migration...")
        total = db.users.count_documents({})
        with_org_ids = db.users.count_documents({'organization_ids': {'$exists': True}})
        
        print(f"  Users with organization_ids: {with_org_ids}/{total}")
        
        if total == with_org_ids:
            print()
            print("✅ SUCCESS! All users migrated successfully!")
        else:
            missing = total - with_org_ids
            print()
            print(f"⚠️  WARNING: {missing} users still need migration")
            
            # Show first few missing users
            print("\nFirst few users without organization_ids:")
            missing_users = db.users.find(
                {'organization_ids': {'$exists': False}},
                {'_id': 1, 'name': 1, 'organization_id': 1}
            ).limit(5)
            
            for user in missing_users:
                print(f"  - {user.get('name', 'Unknown')} (ID: {user['_id']})")
        
        # Close connection
        client.close()
        
        return updated, skipped
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("MULTI-ORGANIZATION MIGRATION")
    print("=" * 60)
    print()
    
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("Usage:")
        print("  python migrate_now.py")
        print()
        print("Environment Variables:")
        print("  MONGODB_URI - MongoDB connection string")
        print("                (default: reads from config.py or uses localhost)")
        print()
        print("Examples:")
        print('  python migrate_now.py')
        print('  MONGODB_URI="mongodb://localhost:27017/mydb" python migrate_now.py')
        print()
        sys.exit(0)
    
    migrate()
    
    print()
    print("=" * 60)
    print("Next steps:")
    print("1. Restart your application")
    print("2. Test user login and organization features")
    print("=" * 60)
    print()

