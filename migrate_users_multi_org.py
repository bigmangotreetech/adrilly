"""
Migration script to add multi-organization support to existing users.

This script:
1. Adds 'organization_ids' field to all users who don't have it
2. Converts existing 'organization_id' to an array in 'organization_ids'
3. Maintains backward compatibility by keeping 'organization_id' field

Usage:
    python migrate_users_multi_org.py
"""

from app.extensions import mongo
from bson import ObjectId
from datetime import datetime

def migrate_users_to_multi_org():
    """Migrate all users to support multiple organizations"""
    
    print("Starting multi-organization migration...")
    print("=" * 60)
    
    # Find all users
    users = list(mongo.db.users.find({}))
    total_users = len(users)
    
    print(f"Found {total_users} users to process")
    print()
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for user in users:
        user_id = user['_id']
        user_name = user.get('name', 'Unknown')
        
        try:
            # Check if user already has organization_ids
            if 'organization_ids' in user and user['organization_ids']:
                print(f"✓ Skipping user '{user_name}' (already migrated)")
                skipped_count += 1
                continue
            
            # Get the current organization_id
            org_id = user.get('organization_id')
            
            if not org_id:
                print(f"⚠ Warning: User '{user_name}' has no organization_id, setting empty array")
                org_ids = []
            else:
                # Convert to array
                org_ids = [org_id]
            
            # Update the user
            result = mongo.db.users.update_one(
                {'_id': user_id},
                {
                    '$set': {
                        'organization_ids': org_ids,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"✓ Migrated user '{user_name}' (org_ids: {len(org_ids)})")
                migrated_count += 1
            else:
                print(f"⚠ User '{user_name}' not modified (may already be up to date)")
                skipped_count += 1
                
        except Exception as e:
            print(f"✗ Error migrating user '{user_name}': {str(e)}")
            error_count += 1
    
    print()
    print("=" * 60)
    print("Migration Summary:")
    print(f"  Total users:     {total_users}")
    print(f"  Migrated:        {migrated_count}")
    print(f"  Skipped:         {skipped_count}")
    print(f"  Errors:          {error_count}")
    print("=" * 60)
    
    if error_count > 0:
        print("\n⚠ Some users had errors. Please review the output above.")
    else:
        print("\n✓ Migration completed successfully!")
    
    return migrated_count, skipped_count, error_count

def verify_migration():
    """Verify that all users have organization_ids"""
    
    print("\nVerifying migration...")
    print("=" * 60)
    
    # Count users with organization_ids
    users_with_org_ids = mongo.db.users.count_documents({'organization_ids': {'$exists': True}})
    total_users = mongo.db.users.count_documents({})
    
    # Count users with multiple organizations
    users_multi_org = mongo.db.users.count_documents({
        'organization_ids': {'$exists': True, '$not': {'$size': 0}, '$not': {'$size': 1}}
    })
    
    # Count users with no organizations
    users_no_org = mongo.db.users.count_documents({
        '$or': [
            {'organization_ids': {'$exists': False}},
            {'organization_ids': {'$size': 0}}
        ]
    })
    
    print(f"Total users:                    {total_users}")
    print(f"Users with organization_ids:    {users_with_org_ids}")
    print(f"Users with multiple orgs:       {users_multi_org}")
    print(f"Users with no organizations:    {users_no_org}")
    print("=" * 60)
    
    if users_with_org_ids == total_users:
        print("✓ All users have organization_ids field")
    else:
        print(f"⚠ {total_users - users_with_org_ids} users missing organization_ids")
    
    return users_with_org_ids == total_users

def rollback_migration():
    """
    Rollback the migration if needed.
    WARNING: This will remove the organization_ids field from all users!
    """
    
    print("\n⚠ WARNING: Rolling back migration will remove organization_ids from all users!")
    confirm = input("Are you sure you want to rollback? (type 'yes' to confirm): ")
    
    if confirm.lower() != 'yes':
        print("Rollback cancelled.")
        return
    
    print("\nRolling back migration...")
    
    result = mongo.db.users.update_many(
        {},
        {'$unset': {'organization_ids': ''}}
    )
    
    print(f"Removed organization_ids from {result.modified_count} users")
    print("Rollback complete.")

if __name__ == '__main__':
    import sys
    from app import create_app
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
            rollback_migration()
        elif len(sys.argv) > 1 and sys.argv[1] == '--verify':
            verify_migration()
        else:
            # Run migration
            migrated, skipped, errors = migrate_users_to_multi_org()
            
            # Verify
            print()
            verify_migration()
            
            print("\nMigration complete! You can verify the results by running:")
            print("  python migrate_users_multi_org.py --verify")

