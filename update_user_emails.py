#!/usr/bin/env python3
"""
Update user emails based on their roles for users without email addresses
"""

from app.app import create_app
from datetime import datetime
import re

def update_user_emails():
    """Find users without emails and update them based on their roles"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("🔍 Finding users without email addresses...")
        
        # Find all users
        all_users = list(mongo.db.users.find({}))
        users_without_email = []
        
        for user in all_users:
            # Check if user has no email or empty email
            if not user.get('email') or user.get('email') == '':
                users_without_email.append(user)
        
        print(f"📊 Found {len(users_without_email)} users without email addresses out of {len(all_users)} total users")
        
        if not users_without_email:
            print("✅ All users already have email addresses!")
            return True
        
        print("\n📝 Users without email:")
        for user in users_without_email:
            print(f"   - {user.get('name', 'Unknown')} ({user.get('phone_number', 'No phone')}) - Role: {user.get('role', 'Unknown')}")
        
        print("\n🔧 Updating user emails based on roles...")
        
        updated_count = 0
        
        for user in users_without_email:
            user_id = user['_id']
            name = user.get('name', 'User')
            role = user.get('role', 'student')
            phone = user.get('phone_number', '0000000000')
            
            # Generate email based on role and name
            email = generate_email_by_role(name, role, phone)
            
            # Update user with email
            result = mongo.db.users.update_one(
                {'_id': user_id},
                {
                    '$set': {
                        'email': email,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                updated_count += 1
                print(f"✅ Updated {name} ({role}): {email}")
            else:
                print(f"❌ Failed to update {name}")
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Total users found: {len(all_users)}")
        print(f"   • Users without email: {len(users_without_email)}")
        print(f"   • Users updated: {updated_count}")
        
        if updated_count > 0:
            print(f"\n📧 EMAIL PATTERNS USED:")
            print(f"   • Super Admin: admin@testsports.com")
            print(f"   • Org Admin: orgadmin@testsports.com")
            print(f"   • Coach Admin: coachadmin@testsports.com")
            print(f"   • Coach: coach.[clean_name]@testsports.com")
            print(f"   • Student: student.[clean_name]@testsports.com")
            print(f"   • Fallback: user.[phone_last4]@testsports.com")
        
        return True

def generate_email_by_role(name, role, phone):
    """Generate appropriate email based on user role"""
    
    # Clean name for email (remove spaces, special chars, convert to lowercase)
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', name.lower()) if name else 'user'
    
    # Get last 4 digits of phone for uniqueness
    phone_last4 = phone[-4:] if phone and len(phone) >= 4 else '0000'
    
    # Base domain
    domain = 'testsports.com'
    
    # Generate email based on role
    if role == 'super_admin':
        return f'admin@{domain}'
    elif role == 'org_admin':
        return f'orgadmin@{domain}'
    elif role == 'coach_admin':
        return f'coachadmin@{domain}'
    elif role == 'coach':
        if clean_name and clean_name != 'user':
            return f'coach.{clean_name}@{domain}'
        else:
            return f'coach.{phone_last4}@{domain}'
    elif role == 'student':
        if clean_name and clean_name != 'user':
            return f'student.{clean_name}@{domain}'
        else:
            return f'student.{phone_last4}@{domain}'
    else:
        # Fallback for unknown roles
        return f'user.{phone_last4}@{domain}'

def check_email_duplicates():
    """Check for duplicate emails after update"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("\n🔍 Checking for duplicate emails...")
        
        # Aggregate to find duplicate emails
        pipeline = [
            {'$group': {
                '_id': '$email',
                'count': {'$sum': 1},
                'users': {'$push': {'name': '$name', 'phone': '$phone_number', 'role': '$role'}}
            }},
            {'$match': {'count': {'$gt': 1}}}
        ]
        
        duplicates = list(mongo.db.users.aggregate(pipeline))
        
        if duplicates:
            print(f"⚠️  Found {len(duplicates)} duplicate email(s):")
            for dup in duplicates:
                print(f"   Email: {dup['_id']} (used by {dup['count']} users)")
                for user in dup['users']:
                    print(f"     - {user['name']} ({user['role']}) - {user['phone']}")
        else:
            print("✅ No duplicate emails found!")
        
        return len(duplicates) == 0

def fix_duplicate_emails():
    """Fix duplicate emails by making them unique"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("\n🔧 Fixing duplicate emails...")
        
        # Find users with duplicate emails
        pipeline = [
            {'$group': {
                '_id': '$email',
                'count': {'$sum': 1},
                'users': {'$push': {'_id': '$_id', 'name': '$name', 'phone_number': '$phone_number', 'role': '$role'}}
            }},
            {'$match': {'count': {'$gt': 1}}}
        ]
        
        duplicates = list(mongo.db.users.aggregate(pipeline))
        fixed_count = 0
        
        for dup in duplicates:
            email_base = dup['_id']
            users = dup['users']
            
            # Keep the first user with the original email, modify others
            for i, user in enumerate(users[1:], 1):  # Skip first user
                phone_last4 = user['phone_number'][-4:] if user['phone_number'] and len(user['phone_number']) >= 4 else '0000'
                new_email = f"{email_base.split('@')[0]}.{phone_last4}@{email_base.split('@')[1]}"
                
                result = mongo.db.users.update_one(
                    {'_id': user['_id']},
                    {
                        '$set': {
                            'email': new_email,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    fixed_count += 1
                    print(f"✅ Fixed duplicate: {user['name']} -> {new_email}")
        
        print(f"🔧 Fixed {fixed_count} duplicate emails")
        return True

if __name__ == '__main__':
    try:
        print("🚀 Starting email update process...")
        print("=" * 50)
        
        # Step 1: Update users without emails
        success = update_user_emails()
        
        if success:
            # Step 2: Check for duplicates
            no_duplicates = check_email_duplicates()
            
            # Step 3: Fix duplicates if found
            if not no_duplicates:
                fix_duplicate_emails()
                # Re-check after fixing
                check_email_duplicates()
            
            print("\n" + "=" * 50)
            print("✅ Email update process completed successfully!")
            print("📧 All users now have appropriate email addresses")
        else:
            print("\n❌ Email update process failed!")
            
    except Exception as e:
        print(f"\n❌ Error during email update: {e}")
        print("Make sure your Flask app and MongoDB are running.") 