#!/usr/bin/env python3
"""
Script to find all users who do not have an organization_id and update them 
to the first organization in the database.

This script is useful for data migration or cleanup when users were created 
without organization assignments.
"""

from app.app import create_app
from app.models.user import User
from app.models.organization import Organization
from datetime import datetime
from bson import ObjectId

def update_users_with_first_org():
    """Find users without organization_id and assign them to the first organization"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("🔍 Finding users without organization ID...")
        print("="*60)
        
        # Step 1: Find the first organization in the database
        print("1️⃣ Looking for organizations...")
        first_org = mongo.db.organizations.find_one({}, sort=[('created_at', 1)])
        
        if not first_org:
            print("❌ No organizations found in the database!")
            print("   Please create at least one organization first.")
            return False
        
        org_id = first_org['_id']
        org_name = first_org['name']
        print(f"✅ Found first organization: '{org_name}' (ID: {org_id})")
        
        # Step 2: Find users without organization_id
        print("\n2️⃣ Finding users without organization ID...")
        
        # Query for users where organization_id is null or missing
        users_without_org = list(mongo.db.users.find({
            '$or': [
                {'organization_id': None},
                {'organization_id': {'$exists': False}}
            ]
        }))
        
        if not users_without_org:
            print("✅ All users already have organization assignments!")
            return True
        
        print(f"📋 Found {len(users_without_org)} users without organization ID:")
        
        # Display users that will be updated
        for user in users_without_org:
            print(f"   • {user.get('name', 'Unknown')} (Phone: {user.get('phone_number', 'N/A')}) - Role: {user.get('role', 'unknown')}")
        
        # Step 3: Ask for confirmation
        print(f"\n⚠️  About to update {len(users_without_org)} users:")
        print(f"   Organization: '{org_name}' (ID: {org_id})")
        
        confirmation = input("\n❓ Do you want to proceed with the update? (y/N): ").strip().lower()
        
        if confirmation not in ['y', 'yes']:
            print("❌ Update cancelled by user.")
            return False
        
        # Step 4: Update users
        print(f"\n3️⃣ Updating users with organization ID...")
        
        updated_count = 0
        failed_updates = []
        
        for user in users_without_org:
            try:
                # Update the user document
                result = mongo.db.users.update_one(
                    {'_id': user['_id']},
                    {
                        '$set': {
                            'organization_id': org_id,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ Updated: {user.get('name', 'Unknown')} (Phone: {user.get('phone_number', 'N/A')})")
                else:
                    failed_updates.append(user.get('name', 'Unknown'))
                    print(f"⚠️  Failed to update: {user.get('name', 'Unknown')}")
                    
            except Exception as e:
                failed_updates.append(user.get('name', 'Unknown'))
                print(f"❌ Error updating {user.get('name', 'Unknown')}: {e}")
        
        # Step 5: Summary
        print("\n" + "="*60)
        print("📊 UPDATE SUMMARY")
        print("="*60)
        print(f"✅ Successfully updated: {updated_count} users")
        print(f"❌ Failed updates: {len(failed_updates)} users")
        print(f"🏢 Organization assigned: '{org_name}' (ID: {org_id})")
        
        if failed_updates:
            print(f"\n⚠️  Failed to update the following users:")
            for failed_user in failed_updates:
                print(f"   • {failed_user}")
        
        # Step 6: Verification
        print(f"\n4️⃣ Verifying updates...")
        remaining_users = mongo.db.users.count_documents({
            '$or': [
                {'organization_id': None},
                {'organization_id': {'$exists': False}}
            ]
        })
        
        if remaining_users == 0:
            print("✅ All users now have organization assignments!")
        else:
            print(f"⚠️  {remaining_users} users still without organization ID")
        
        print(f"\n🎉 Update completed successfully!")
        print(f"   Updated {updated_count} out of {len(users_without_org)} users")
        
        return True

def preview_users_without_org():
    """Preview users that would be affected without making changes"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("👀 PREVIEW: Users without organization ID")
        print("="*50)
        
        # Find users without organization_id
        users_without_org = list(mongo.db.users.find({
            '$or': [
                {'organization_id': None},
                {'organization_id': {'$exists': False}}
            ]
        }))
        
        if not users_without_org:
            print("✅ All users already have organization assignments!")
            return
        
        print(f"📋 Found {len(users_without_org)} users without organization ID:")
        print()
        
        for i, user in enumerate(users_without_org, 1):
            print(f"{i:2d}. Name: {user.get('name', 'Unknown')}")
            print(f"    Phone: {user.get('phone_number', 'N/A')}")
            print(f"    Role: {user.get('role', 'unknown')}")
            print(f"    Created: {user.get('created_at', 'Unknown')}")
            print(f"    Active: {user.get('is_active', 'Unknown')}")
            print()
        
        # Show available organizations
        print("🏢 Available organizations:")
        orgs = list(mongo.db.organizations.find({}, sort=[('created_at', 1)]))
        
        if not orgs:
            print("   ❌ No organizations found!")
        else:
            for i, org in enumerate(orgs, 1):
                print(f"{i}. {org['name']} (ID: {org['_id']}) - Created: {org.get('created_at', 'Unknown')}")
        
        if orgs:
            print(f"\n💡 The script will assign all users to: '{orgs[0]['name']}'")

if __name__ == '__main__':
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == 'preview':
        try:
            preview_users_without_org()
        except Exception as e:
            print(f"\n❌ Error during preview: {e}")
            print("Make sure your Flask app and MongoDB are running.")
    else:
        try:
            success = update_users_with_first_org()
            if success:
                print("\n✅ Script completed successfully!")
            else:
                print("\n❌ Script execution failed!")
        except Exception as e:
            print(f"\n❌ Error executing script: {e}")
            print("Make sure your Flask app and MongoDB are running.")
            print("\n💡 Usage:")
            print("   python update_users_with_org.py          # Run the update")
            print("   python update_users_with_org.py preview  # Preview without changes")