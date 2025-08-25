#!/usr/bin/env python3
"""
Reset users and create simple test users for mobile app testing
"""

from app.app import create_app
from app.models.user import User
from app.models.organization import Organization
from datetime import datetime

def reset_and_create_users():
    """Clear existing users and create fresh test users with simple phone numbers"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("🧹 Clearing existing users...")
        
        # Clear all existing users
        result = mongo.db.users.delete_many({})
        print(f"   Deleted {result.deleted_count} existing users")
        
        # Clear existing organizations to start fresh
        result = mongo.db.organizations.delete_many({})
        print(f"   Deleted {result.deleted_count} existing organizations")
        
        print("\n🏢 Creating default organization...")
        # Create a default organization
        default_org = Organization(
            name="Test Sports Center",
            owner_id=None,
            contact_info={'email': 'admin@testsports.com', 'phone': '1234567890'},
            address={'street': '123 Test St', 'city': 'Test City', 'state': 'TC', 'zip': '12345'},
            sports=['football', 'basketball', 'tennis']
        )
        result = mongo.db.organizations.insert_one(default_org.to_dict())
        default_org._id = result.inserted_id
        org_id = str(default_org._id)
        print(f"✅ Created organization: Test Sports Center ({org_id})")
        
        print("\n👥 Creating test users...")
        
        # Test users with simple phone numbers (no +)
        test_users = [
            {
                'phone_number': '1000000000',
                'name': 'Super Admin',
                'role': 'super_admin',
                'password': 'admin123',
                'organization_id': None  # Super admin doesn't need org
            },
            {
                'phone_number': '1234567890',
                'name': 'Org Admin',
                'role': 'org_admin', 
                'password': 'admin123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567891',
                'name': 'Coach Admin',
                'role': 'coach_admin',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567892',
                'name': 'Senior Coach',
                'role': 'coach',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567893',
                'name': 'Basketball Coach',
                'role': 'coach',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543210',
                'name': 'Test Student 1',
                'role': 'student',
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543211',
                'name': 'Test Student 2', 
                'role': 'student',
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543212',
                'name': 'Test Student 3',
                'role': 'student', 
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '5555555555',
                'name': 'Quick Test User',
                'role': 'coach',
                'password': 'test123',
                'organization_id': org_id
            }
        ]
        
        created_users = []
        org_admin_id = None
        
        for user_data in test_users:
            # Create new user
            new_user = User(
                phone_number=user_data['phone_number'],
                name=user_data['name'],
                role=user_data['role'],
                password=user_data['password'],
                organization_id=user_data['organization_id']
            )
            new_user.verification_status = 'verified'
            new_user.is_active = True
            
            result = mongo.db.users.insert_one(new_user.to_dict(include_sensitive=True))
            new_user._id = result.inserted_id
            created_users.append(user_data)
            
            # Remember org admin for organization update
            if user_data['role'] == 'org_admin':
                org_admin_id = new_user._id
            
            print(f"✅ Created user: {user_data['phone_number']} ({user_data['name']})")
        
        # Update organization owner
        if org_admin_id:
            mongo.db.organizations.update_one(
                {'_id': default_org._id},
                {'$set': {'owner_id': org_admin_id}}
            )
            print(f"🔗 Updated organization owner")
        
        print("\n" + "="*60)
        print("🎉 FRESH TEST USERS CREATED FOR MOBILE APP!")
        print("="*60)
        print("\n📱 LOGIN CREDENTIALS (NO + NEEDED):")
        print("="*40)
        
        print("\n🔧 SUPER ADMIN:")
        print("   Phone: 1000000000")
        print("   Password: admin123")
        print("   Role: Super Admin (full access)")
        
        print("\n🏢 ORGANIZATION ADMIN:")
        print("   Phone: 1234567890") 
        print("   Password: admin123")
        print("   Role: Org Admin (manage center)")
        
        print("\n👨‍🏫 COACH ADMIN:")
        print("   Phone: 1234567891")
        print("   Password: coach123")
        print("   Role: Coach Admin (manage coaches/students)")
        
        print("\n🏃‍♂️ COACHES:")
        print("   Phone: 1234567892")
        print("   Password: coach123")
        print("   Role: Senior Coach")
        print()
        print("   Phone: 1234567893")
        print("   Password: coach123") 
        print("   Role: Basketball Coach")
        print()
        print("   Phone: 5555555555")
        print("   Password: test123")
        print("   Role: Quick Test User")
        
        print("\n🎓 STUDENTS:")
        print("   Phone: 9876543210")
        print("   Password: student123")
        print("   Name: Test Student 1")
        print()
        print("   Phone: 9876543211")
        print("   Password: student123")
        print("   Name: Test Student 2")
        print()
        print("   Phone: 9876543212")
        print("   Password: student123")
        print("   Name: Test Student 3")
        
        print("\n💡 QUICK START:")
        print("="*15)
        print("🚀 RECOMMENDED FOR FIRST TEST:")
        print("   Phone: 1234567890")
        print("   Password: admin123")
        print("   (This gives you org admin access)")
        print()
        print("🎯 OR FOR COACH TESTING:")
        print("   Phone: 5555555555")
        print("   Password: test123")
        print("   (Quick test coach account)")
        
        print("\n💡 USAGE INSTRUCTIONS:")
        print("="*25)
        print("1. Open your mobile app")
        print("2. Choose 'Login with Password'") 
        print("3. Enter phone number (no + needed)")
        print("4. Enter corresponding password")
        print("5. All users are verified and ready!")
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Created: {len(created_users)} fresh users")
        print(f"   • Organization: Test Sports Center")
        print(f"   • All users verified and active")
        
        return True

if __name__ == '__main__':
    try:
        success = reset_and_create_users()
        if success:
            print("\n✅ Fresh test users created successfully!")
            print("🚀 Ready to test your mobile app!")
        else:
            print("\n❌ Test users creation failed!")
    except Exception as e:
        print(f"\n❌ Error creating test users: {e}")
        print("Make sure your Flask app and MongoDB are running.") 