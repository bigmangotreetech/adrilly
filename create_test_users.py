#!/usr/bin/env python3
"""
Create test users with simple phone numbers (without +) for mobile app testing
"""

from app.app import create_app
from app.models.user import User
from app.models.organization import Organization
from datetime import datetime

def create_simple_test_users():
    """Create test users with simple phone numbers for mobile testing"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("🔧 Creating test users with simple phone numbers...")
        
        # First, let's check if we have any organizations
        existing_orgs = list(mongo.db.organizations.find({}))
        
        if not existing_orgs:
            print("📦 No organizations found. Creating a default organization...")
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
            print(f"✅ Created default organization: {org_id}")
        else:
            # Use the first existing organization
            org_id = str(existing_orgs[0]['_id'])
            print(f"✅ Using existing organization: {existing_orgs[0]['name']} ({org_id})")
        
        # Test users to create with simple phone numbers (no +)
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
            }
        ]
        
        created_users = []
        updated_users = []
        
        for user_data in test_users:
            # Check if user already exists
            existing_user = mongo.db.users.find_one({'phone_number': user_data['phone_number']})
            
            if existing_user:
                # Update existing user's password
                user_obj = User.from_dict(existing_user)
                user_obj.set_password(user_data['password'])
                user_obj.verification_status = 'verified'
                user_obj.is_active = True
                user_obj.updated_at = datetime.utcnow()
                
                # Update in database
                mongo.db.users.update_one(
                    {'_id': existing_user['_id']},
                    {'$set': user_obj.to_dict(include_sensitive=True)}
                )
                updated_users.append(user_data)
                print(f"🔄 Updated user: {user_data['phone_number']} ({user_data['name']})")
                
            else:
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
                print(f"✅ Created user: {user_data['phone_number']} ({user_data['name']})")
        
        # Update organization owner if needed
        if existing_orgs:
            org_admin = mongo.db.users.find_one({'phone_number': '1234567890'})
            if org_admin:
                mongo.db.organizations.update_one(
                    {'_id': existing_orgs[0]['_id']},
                    {'$set': {'owner_id': org_admin['_id']}}
                )
                print(f"🔗 Updated organization owner")
        
        print("\n" + "="*60)
        print("🎉 TEST USERS READY FOR MOBILE APP!")
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
        
        print("\n💡 USAGE INSTRUCTIONS:")
        print("="*25)
        print("1. Use any of these phone numbers in your mobile app")
        print("2. Enter the corresponding password")
        print("3. No need to add '+' or country code")
        print("4. All users are verified and ready to use")
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Created: {len(created_users)} new users")
        print(f"   • Updated: {len(updated_users)} existing users")
        print(f"   • Organization: {existing_orgs[0]['name'] if existing_orgs else 'Test Sports Center'}")
        
        return True

if __name__ == '__main__':
    try:
        success = create_simple_test_users()
        if success:
            print("\n✅ Test users creation completed successfully!")
            print("🚀 You can now login to your mobile app with these credentials!")
        else:
            print("\n❌ Test users creation failed!")
    except Exception as e:
        print(f"\n❌ Error creating test users: {e}")
        print("Make sure your Flask app and MongoDB are running.") 