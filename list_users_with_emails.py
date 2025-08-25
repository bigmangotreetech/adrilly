#!/usr/bin/env python3
"""
List all users with their email addresses for verification
"""

from app.app import create_app

def list_users_with_emails():
    """Display all users with their email addresses"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("📋 CURRENT USERS WITH EMAIL ADDRESSES")
        print("=" * 60)
        
        # Get all users
        all_users = list(mongo.db.users.find({}).sort('role', 1))
        
        if not all_users:
            print("❌ No users found in database")
            return False
        
        # Group users by role
        users_by_role = {}
        for user in all_users:
            role = user.get('role', 'unknown')
            if role not in users_by_role:
                users_by_role[role] = []
            users_by_role[role].append(user)
        
        # Display users grouped by role
        role_order = ['super_admin', 'org_admin', 'coach_admin', 'coach', 'student']
        
        for role in role_order:
            if role in users_by_role:
                users = users_by_role[role]
                role_name = role.replace('_', ' ').title()
                print(f"\n🔸 {role_name.upper()} ({len(users)} users):")
                print("-" * 40)
                
                for user in users:
                    name = user.get('name', 'Unknown')
                    phone = user.get('phone_number', 'No phone')
                    email = user.get('email', 'NO EMAIL')
                    
                    print(f"   📧 {name}")
                    print(f"      Phone: {phone}")
                    print(f"      Email: {email}")
                    print()
        
        # Handle any other roles not in the standard list
        other_roles = set(users_by_role.keys()) - set(role_order)
        for role in other_roles:
            users = users_by_role[role]
            role_name = role.replace('_', ' ').title()
            print(f"\n🔸 {role_name.upper()} ({len(users)} users):")
            print("-" * 40)
            
            for user in users:
                name = user.get('name', 'Unknown')
                phone = user.get('phone_number', 'No phone')
                email = user.get('email', 'NO EMAIL')
                
                print(f"   📧 {name}")
                print(f"      Phone: {phone}")
                print(f"      Email: {email}")
                print()
        
        # Summary
        total_users = len(all_users)
        users_with_email = len([u for u in all_users if u.get('email')])
        users_without_email = total_users - users_with_email
        
        print("=" * 60)
        print("📊 SUMMARY:")
        print(f"   • Total Users: {total_users}")
        print(f"   • Users with Email: {users_with_email}")
        print(f"   • Users without Email: {users_without_email}")
        
        if users_without_email == 0:
            print("✅ All users have email addresses!")
        else:
            print(f"⚠️  {users_without_email} users still need email addresses")
        
        return True

if __name__ == '__main__':
    try:
        list_users_with_emails()
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        print("Make sure your Flask app and MongoDB are running.") 