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
        
        
        collections = ['activities', 'activity_links', 'attendance', 'bookings', 'cancellations', 'centers', 'class_pictures', 'classes', 'comments', 'equipment', 'likes', 'notifications', 'org_holidays', 'organizations', 'otps', 'payment_links', 'payment_plans', 'payments', 'posts', 'progress', 'rsvps', 'rubrics', 'schedules', 'time_slots']
        for collection in collections:
            result = mongo.db[collection].delete_many({})
            print(f"   Deleted {result.deleted_count} existing {collection}")

        result = mongo.db.activities.delete_many({})
        print(f"   Deleted {result.deleted_count} existing activities")

        result = mongo.db.activity_links.delete_many({})
        print(f"   Deleted {result.deleted_count} existing timeslots")
        
        result = mongo.db.attendance.delete_many({})
        print(f"   Deleted {result.deleted_count} existing attendance")

        result = mongo.db.bookings.delete_many({})
        print(f"   Deleted {result.deleted_count} existing bookings")
        
        result = mongo.db.cancellations.delete_many({})
        print(f"   Deleted {result.deleted_count} existing cancellations")
        
        result = mongo.db.centers.delete_many({})
        print(f"   Deleted {result.deleted_count} existing centers")

        result = mongo.db.class_pictures.delete_many({})
        print(f"   Deleted {result.deleted_count} existing class pictures")

        result = mongo.db.classes.delete_many({})
        print(f"   Deleted {result.deleted_count} existing classes")

        result = mongo.db.comments.delete_many({})
        print(f"   Deleted {result.deleted_count} existing comments")


        result = mongo.db.equipment.delete_many({})
        print(f"   Deleted {result.deleted_count} existing equipment")

        # result = mongo.db.holidays.delete_many({})
        # print(f"   Deleted {result.deleted_count} existing holidays")

        result = mongo.db.likes.delete_many({})
        print(f"   Deleted {result.deleted_count} existing likes")

        result = mongo.db.notifications.delete_many({})
        print(f"   Deleted {result.deleted_count} existing notifications")

        result = mongo.db.org_holidays.delete_many({})
        print(f"   Deleted {result.deleted_count} existing org holidays")

        # Clear existing organizations to start fresh
        result = mongo.db.organizations.delete_many({})
        print(f"   Deleted {result.deleted_count} existing organizations")

        result = mongo.db.otps.delete_many({})
        print(f"   Deleted {result.deleted_count} existing otps")

        result = mongo.db.payment_links.delete_many({})
        print(f"   Deleted {result.deleted_count} existing payment links")

        result = mongo.db.payment_plans.delete_many({})
        print(f"   Deleted {result.deleted_count} existing payment plans")

        result = mongo.db.payments.delete_many({})
        print(f"   Deleted {result.deleted_count} existing payments")


        result = mongo.db.posts.delete_many({})
        print(f"   Deleted {result.deleted_count} existing posts")

        result = mongo.db.progress.delete_many({})
        print(f"   Deleted {result.deleted_count} existing progress")

        result = mongo.db.rsvps.delete_many({})
        print(f"   Deleted {result.deleted_count} existing profile data")

        result = mongo.db.rubrics.delete_many({})
        print(f"   Deleted {result.deleted_count} existing rubrics")

        result = mongo.db.schedules.delete_many({})
        print(f"   Deleted {result.deleted_count} existing schedules")

        result = mongo.db.time_slots.delete_many({})
        print(f"   Deleted {result.deleted_count} existing time slots")

        result = mongo.db.payments.delete_many({})
        print(f"   Deleted {result.deleted_count} existing payments")

        # Clear all existing users
        result = mongo.db.users.delete_many({})
        print(f"   Deleted {result.deleted_count} existing users")
        
        result = mongo.db.groups.delete_many({})
        print(f"   Deleted {result.deleted_count} existing groups") 

        result = mongo.db.equipment.delete_many({})
        print(f"   Deleted {result.deleted_count} existing equipment")



        print("\n🏢 Creating default organization...")
        # Create a default organization
        default_org = Organization(
            name="Test Sports Center",
            owner_id=None,
            contact_info={'email': 'admin@testsports.com', 'phone': '1234567890'},
            address={'street': '123 Test St', 'city': 'Test City', 'state': 'TC', 'zip': '12345'},
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
                'email': 'superadmin@testsports.com',
                'role': 'super_admin',
                'password': 'admin123',
                'organization_id': None  # Super admin doesn't need org
            },
            {
                'phone_number': '1234567890',
                'name': 'Org Admin',
                'email': 'orgadmin@testsports.com',
                'role': 'org_admin', 
                'password': 'admin123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567891',
                'name': 'Coach Admin',
                'email': 'coachadmin@testsports.com',
                'role': 'coach_admin',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567892',
                'name': 'Senior Coach',
                'email': 'seniorcoach@testsports.com',
                'role': 'coach',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '1234567893',
                'name': 'Basketball Coach',
                'email': 'basketballcoach@testsports.com',
                'role': 'coach',
                'password': 'coach123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543210',
                'name': 'Test Student 1',
                'email': 'student1@testsports.com',
                'role': 'student',
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543211',
                'name': 'Test Student 2',
                'email': 'student2@testsports.com',
                'role': 'student',
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '9876543212',
                'name': 'Test Student 3',
                'email': 'student3@testsports.com',
                'role': 'student', 
                'password': 'student123',
                'organization_id': org_id
            },
            {
                'phone_number': '5555555555',
                'name': 'Quick Test User',
                'email': 'quicktest@testsports.com',
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
                email=user_data['email'],
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