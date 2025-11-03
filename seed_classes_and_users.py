from datetime import datetime
from bson import ObjectId
from app.models.organizations import Organization
from app.models.users import User
from pymongo import MongoClient
from typing import List, Dict
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/adrilly')
client = MongoClient(MONGODB_URI)

# Extract database name from URI or use default
if '/adrilly' in MONGODB_URI:
    db_name = MONGODB_URI.split('/')[-1].split('?')[0]
else:
    db_name = 'adrilly'
db = client[db_name]

def create_organization(org_data: Dict) -> ObjectId:
    """Create an organization with provided data"""
    org = Organization(
        _id=ObjectId(),
        name=org_data['name'],
        type="coaching_center",
        status="active",
        contact_email=org_data['contact_email'],
        contact_phone=org_data['contact_phone'],
        address=org_data['address'],
        admin_id=org_data['admin_id'],
        subscription_plan="premium",
        subscription_status="active",
        features_enabled=["attendance", "payments", "notifications"],
        working_hours={
            "monday": {"start": "06:00", "end": "21:00"},
            "tuesday": {"start": "06:00", "end": "21:00"},
            "wednesday": {"start": "06:00", "end": "21:00"},
            "thursday": {"start": "06:00", "end": "21:00"},
            "friday": {"start": "06:00", "end": "21:00"},
            "saturday": {"start": "07:00", "end": "20:00"}
        }
    )
    db.organizations.insert_one(org.__dict__)
    return org._id


def create_users(org_id: ObjectId, org_config: Dict) -> List[ObjectId]:
    """Create users for an organization based on configuration"""
    user_ids = []
    user_count = 0
    
    # Extract config
    num_coaches = org_config['num_coaches']
    num_students = org_config['num_students']
    specializations = org_config['specializations']
    email_domain = org_config['email_domain']
    org_short_name = org_config['short_name']
    
    # Get names from config
    first_names = org_config.get('first_names', [
        "Aarav", "Advait", "Aryan", "Vihaan", "Reyansh", "Aisha", "Ananya", "Diya", 
        "Saanvi", "Aadhya", "Kabir", "Vivaan", "Aditya", "Atharv", "Ishaan", "Zara", 
        "Kiara", "Myra", "Shanaya", "Pari", "Dhruv", "Arjun", "Shaurya", "Arnav", 
        "Yash", "Avni", "Mira", "Riya", "Ira", "Anika", "Rohan", "Neha", "Priya",
        "Rahul", "Amit", "Sneha", "Pooja", "Raj", "Anjali", "Vikram", "Meera",
        "Karan", "Nisha", "Arun", "Divya", "Sanjay", "Kavita", "Rajesh", "Deepa", "Suresh"
    ])
    
    last_names = org_config.get('last_names', [
        "Sharma", "Patel", "Kumar", "Singh", "Verma", "Gupta", "Shah", "Mehta",
        "Reddy", "Iyer", "Kapoor", "Joshi", "Malhotra", "Nair", "Rao", "Chopra",
        "Sinha", "Desai", "Menon", "Pillai", "Bhat", "Chauhan", "Saxena", "Trivedi", "Soni"
    ])
    
    total_users = num_coaches + 1 + num_students  # coaches + admin + students
    base_phone = org_config['base_phone']
    
    # Create users with different roles
    for i in range(total_users):
        first = first_names[i % len(first_names)]
        last = last_names[i % len(last_names)]
        name = f"{first} {last}"
        
        # Determine role
        if i < num_coaches:
            role = "coach"
            email = f"{first.lower()}.{last.lower()}@{email_domain}"
            phone = f"{base_phone}{i:02d}"
            metadata = {"specialization": specializations[i % len(specializations)]}
        elif i == num_coaches:
            role = "org_admin"
            email = f"admin@{email_domain}"
            phone = f"{base_phone}{99}"
            metadata = {}   
        else:
            role = "student"
            email = f"{first.lower()}.{last.lower()}.{org_short_name}{i}@gmail.com"
            phone = f"{org_config['student_phone_base']}{100+i:03d}"
            metadata = {}
        
        user = User(
            _id=ObjectId(),
            email=email,
            phone_number=phone,
            name=name,
            role=role,
            organization_id=org_id,
            status="active",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewFX", # dummy hash
            metadata=metadata,
            email_verified=True,
            phone_verified=True
        )
        
        db.users.insert_one(user.__dict__)
        user_ids.append(user._id)
        
        print(f"Created {role}: {name} ({phone})")
        user_count += 1
    
    print(f"\nTotal users created for {org_config['short_name']}: {user_count}")
    return user_ids


def clean_seeded_data():
    """Clean only the data created by this seed script"""
    org_names = [
        "Serenity Yoga & Pilates Studio",
        "FitBox Boxing Academy",
        "Ace Badminton Club"
    ]
    
    for org_name in org_names:
        # Find the organization
        org = db.organizations.find_one({"name": org_name})
        if org:
            org_id = org['_id']
            
            # Delete all related data
            db.centers.delete_many({"organization_id": org_id})
            db.users.delete_many({"organization_id": org_id})
            db.groups.delete_many({"organization_id": org_id})
            db.classes.delete_many({"organization_id": org_id})
            db.organizations.delete_one({"_id": org_id})
            
            print(f"Cleaned data for: {org_name}")
        else:
            print(f"No data found for: {org_name}")
    
    # Note: Super admin is NOT deleted in clean_seeded_data to preserve platform admin access

def clean_all_data():
    """Clean all data from collections"""
    collections = ['users', 'activities', 'activity_links', 'attendance', 'bookings', 'cancellations', 'centers', 'class_pictures', 'classes', 'comments', 'equipment', 'likes', 'notifications', 'org_holidays', 'organizations', 'otps', 'payment_links', 'payment_plans', 'payments', 'posts', 'progress', 'rsvps', 'rubrics', 'schedules', 'time_slots']
    for collection in collections:
        db[collection].drop()
    print("Cleaned all data")

def setup_database(clean_mode='all'):
    """Setup database collections and indexes"""
    if clean_mode == 'all':
        clean_all_data()
    elif clean_mode == 'seeded':
        clean_seeded_data()
    
    # Create indexes
    # Drop existing non-sparse indexes if they exist, then create sparse indexes
    # Use sparse indexes for email and phone_number to allow multiple NULLs while maintaining uniqueness
    try:
        db.users.drop_index("phone_number_1")
    except Exception:
        pass  # Index doesn't exist, which is fine
    
    try:
        db.users.drop_index("email_1")
    except Exception:
        pass  # Index doesn't exist, which is fine
    
    db.users.create_index("email", unique=True, sparse=True)
    db.users.create_index("phone_number", unique=True, sparse=True)
    db.organizations.create_index("name", unique=True)
    
    print("Database setup completed")

def get_organization_configs():
    """Return configurations for all 3 organizations"""
    return [
        {
            'name': 'Serenity Yoga & Pilates Studio',
            'short_name': 'serenity',
            'contact_email': 'contact@serenityyoga.com',
            'contact_phone': '9123456789',
            'email_domain': 'serenityyoga.com',
            'address': {
                'street': '42 Lavelle Road',
                'city': 'Bangalore',
                'state': 'Karnataka',
                'country': 'India',
                'pincode': '560001'
            },
            'num_coaches': 6,
            'num_students': 24,
            'specializations': [
                'Hatha Yoga', 
                'Vinyasa Yoga', 
                'Ashtanga Yoga', 
                'Mat Pilates', 
                'Reformer Pilates',
                'Yin Yoga'
            ],
            'base_phone': '91234567',
            'student_phone_base': '81234567'
        },
        {
            'name': 'FitBox Boxing Academy',
            'short_name': 'fitbox',
            'contact_email': 'contact@fitboxing.com',
            'contact_phone': '9234567890',
            'email_domain': 'fitboxing.com',
            'address': {
                'street': '18 Koramangala 4th Block',
                'city': 'Bangalore',
                'state': 'Karnataka',
                'country': 'India',
                'pincode': '560034'
            },
            'num_coaches': 5,
            'num_students': 22,
            'specializations': [
                'Boxing', 
                'Kickboxing', 
                'MMA Training', 
                'Cardio Boxing',
                'Competitive Boxing'
            ],
            'base_phone': '92345678',
            'student_phone_base': '82345678'
        },
        {
            'name': 'Ace Badminton Club',
            'short_name': 'ace',
            'contact_email': 'contact@acebadminton.com',
            'contact_phone': '9345678901',
            'email_domain': 'acebadminton.com',
            'address': {
                'street': '25 Indiranagar 100 Feet Road',
                'city': 'Bangalore',
                'state': 'Karnataka',
                'country': 'India',
                'pincode': '560038'
            },
            'num_coaches': 5,
            'num_students': 20,
            'specializations': [
                'Singles Training', 
                'Doubles Training', 
                'Tournament Prep',
                'Youth Training',
                'Advanced Techniques'
            ],
            'base_phone': '93456789',
            'student_phone_base': '83456789'
        }
    ]


def create_organization_with_users(org_config: Dict) -> ObjectId:
    """Create a single organization with its users"""
    print(f"\n{'='*60}")
    print(f"Creating Organization: {org_config['name']}")
    print(f"{'='*60}")
    
    # Create organization with temporary admin ID
    temp_admin_id = ObjectId()
    org_data = {
        'name': org_config['name'],
        'contact_email': org_config['contact_email'],
        'contact_phone': org_config['contact_phone'],
        'address': org_config['address'],
        'admin_id': temp_admin_id
    }
    
    org_id = create_organization(org_data)
    print(f"\n✓ Created organization: {org_config['name']}")
    
    # Create all users including admin
    user_ids = create_users(org_id, org_config)
    
    # Find the admin user and update organization
    admin_id = None
    for user_id in user_ids:
        user = db.users.find_one({"_id": user_id})
        if user and user.get("role") == "org_admin":
            admin_id = user_id
            break
    
    if admin_id:
        db.organizations.update_one(
            {"_id": org_id},
            {"$set": {"admin_id": admin_id}}
        )
        print(f"✓ Updated organization with admin ID")
    
    return org_id


def create_super_admin():
    """Create a super admin user"""
    print("\n" + "="*60)
    print("CREATING SUPER ADMIN")
    print("="*60)
    
    # Check if super admin already exists
    existing_super_admin = db.users.find_one({"role": "super_admin"})
    if existing_super_admin:
        print(f"✓ Super admin already exists: {existing_super_admin.get('name')} ({existing_super_admin.get('email')})")
        return existing_super_admin['_id']
    
    # Create super admin user
    super_admin = User(
        _id=ObjectId(),
        email="superadmin@adrilly.com",
        phone_number="+919876543210",
        name="Super Administrator",
        role="super_admin",
        organization_id=None,  # Super admin doesn't belong to any organization
        status="active",
        password_hash=generate_password_hash("superadmin123"),  # Default password
        metadata={},
        email_verified=True,
        phone_verified=True
    )
    
    db.users.insert_one(super_admin.__dict__)
    print(f"✓ Created super admin: {super_admin.name} ({super_admin.email})")
    print(f"  Phone: {super_admin.phone_number}")
    print(f"  Password: superadmin123")
    
    return super_admin._id


def create_seed_data():
    """Create 3 organizations with their users and a super admin"""
    # Create super admin first
    super_admin_id = create_super_admin()
    
    org_configs = get_organization_configs()
    
    print("\n" + "="*60)
    print("CREATING 3 ORGANIZATIONS WITH USERS")
    print("="*60)
    
    created_orgs = []
    for org_config in org_configs:
        org_id = create_organization_with_users(org_config)
        created_orgs.append({
            'id': org_id,
            'name': org_config['name']
        })
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("Super Admin:")
    print(f"  Email: superadmin@adrilly.com")
    print(f"  Phone: +919876543210")
    print(f"  Password: superadmin123")
    print("\nOrganizations:")
    for i, org in enumerate(created_orgs, 1):
        print(f"{i}. {org['name']}")
    
    print("\n✓ Seed data creation completed!")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed data management script')
    parser.add_argument('action', choices=['create', 'clean-all', 'clean-seeded'],
                      help='Action to perform: create new data, clean all data, or clean only seeded data')
    
    args = parser.parse_args()
    
    try:
        # Test database connection
        client.admin.command('ping')
        print("Connected to MongoDB successfully!")
        
        if args.action == 'clean-all':
            setup_database(clean_mode='all')
        elif args.action == 'clean-seeded':
            setup_database(clean_mode='seeded')
        elif args.action == 'create':
            setup_database(clean_mode='seeded')  # Clean existing seed data before creating new
            create_seed_data()
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
