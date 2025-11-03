#!/usr/bin/env python3
"""
Enhanced seed data script for multi-tenant sports coaching system
"""

from datetime import datetime, timedelta, date
from app.app import create_app
from app.models.user import User
from app.models.organization import Organization, Group
from app.models.class_schedule import Class
from app.models.progress import Rubric
from app.models.payments import Payment
from app.models.equipment import Equipment
import pymongo
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

def ensure_database_and_collections():
    """Ensure database and collections exist, create if they don't"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        # Ensure mongo is properly initialized
        try:
            if not hasattr(mongo, 'db') or mongo.db is None:
                print("❌ MongoDB extension not properly initialized")
                return False
        except NotImplementedError:
            # mongo.db exists but doesn't support boolean testing
            pass
        
        try:
            # Test database connection
            mongo.db.command('ping')
            print("✅ Database connection successful")
            
            # Define all required collections
            required_collections = [
                'users', 'organizations', 'groups', 'classes', 
                'attendance', 'rubrics', 'progress', 'payments', 
                'equipment', 'payment_plans'
            ]
            
            # Get existing collections
            existing_collections = mongo.db.list_collection_names()
            print(f"📂 Existing collections: {existing_collections}")
            
            # Create missing collections
            for collection_name in required_collections:
                if collection_name not in existing_collections:
                    mongo.db.create_collection(collection_name)
                    print(f"✨ Created collection: {collection_name}")
                else:
                    print(f"✅ Collection exists: {collection_name}")
            
            # Create indexes for better performance
            print("🔍 Creating database indexes...")
            
            # Users collection indexes
            # Drop existing non-sparse indexes if they exist
            try:
                mongo.db.users.drop_index("phone_number_1")
            except Exception:
                pass
            try:
                mongo.db.users.drop_index("email_1")
            except Exception:
                pass
            
            # Create sparse indexes for email and phone_number to allow multiple NULLs
            mongo.db.users.create_index("phone_number", unique=True, sparse=True)
            mongo.db.users.create_index("email", unique=True, sparse=True)
            mongo.db.users.create_index("organization_id")
            mongo.db.users.create_index([("role", 1), ("organization_id", 1)])
            
            # Organizations collection indexes
            mongo.db.organizations.create_index("owner_id")
            
            # Classes collection indexes
            mongo.db.classes.create_index([("organization_id", 1), ("scheduled_at", 1)])
            mongo.db.classes.create_index("coach_id")
            
            # Attendance collection indexes
            mongo.db.attendance.create_index([("class_id", 1), ("student_id", 1)], unique=True)
            mongo.db.attendance.create_index("organization_id")
            
            # Payments collection indexes
            mongo.db.payments.create_index([("student_id", 1), ("organization_id", 1)])
            mongo.db.payments.create_index([("status", 1), ("due_date", 1)])
            
            # Groups collection indexes
            mongo.db.groups.create_index([("organization_id", 1), ("coach_id", 1)])
            
            # Equipment collection indexes
            mongo.db.equipment.create_index([("organization_id", 1), ("status", 1)])
            mongo.db.equipment.create_index("owner_id")
            
            print("✅ Database indexes created successfully")
            
            return True
            
        except ServerSelectionTimeoutError:
            print("❌ Error: Could not connect to MongoDB server")
            print("   Please ensure MongoDB is running and accessible")
            return False
        except OperationFailure as e:
            print(f"❌ Database operation failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error initializing database: {e}")
            return False

def create_seed_data():
    """Create comprehensive sample data for multi-tenant testing"""
    # First ensure database and collections exist
    print("🔧 Initializing database and collections...")
    if not ensure_database_and_collections():
        print("❌ Database initialization failed. Exiting.")
        return False
    
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        try:
        # Clear existing data
            print("\n🧹 Clearing existing data...")
        collections = ['users', 'organizations', 'groups', 'classes', 'attendance', 
                      'rubrics', 'progress', 'payments', 'equipment']
        for collection in collections:
                result = mongo.db[collection].delete_many({})
                print(f"   Cleared {result.deleted_count} documents from {collection}")
        
        # Create Super Administrator
            print("\n👑 Creating super administrator...")
        super_admin = User(
            phone_number='+1000000000',
            name='Super Administrator',
            role='super_admin',
            password='superadmin123'
        )
        super_admin.verification_status = 'verified'
        result = mongo.db.users.insert_one(super_admin.to_dict(include_sensitive=True))
        super_admin._id = result.inserted_id
        
        # Create Organization 1 - Elite Sports Academy
        print("Creating Elite Sports Academy...")
        org1 = Organization(
            name="Elite Sports Academy",
            owner_id=None,  # Will be set after creating admin
            contact_info={
                'email': 'admin@elitesports.com',
                'phone': '+1234567890'
            },
            address={
                'street': '123 Sports Complex Road',
                'city': 'Sports City',
                'state': 'SC',
                'zip': '12345'
            },
            sports=['football', 'basketball', 'tennis']
        )
        result = mongo.db.organizations.insert_one(org1.to_dict())
        org1._id = result.inserted_id
        org1_id = str(org1._id)
        
        # Create Organization 1 Admin
        print("Creating Elite Sports Academy admin...")
        org1_admin = User(
            phone_number='+1234567890',
            name='Elite Academy Admin',
            role='org_admin',
            password='admin123',
            organization_id=org1_id,
            created_by=str(super_admin._id)
        )
        org1_admin.verification_status = 'verified'
        result = mongo.db.users.insert_one(org1_admin.to_dict(include_sensitive=True))
        org1_admin._id = result.inserted_id
        
        # Update organization owner
        mongo.db.organizations.update_one(
            {'_id': org1._id},
            {'$set': {'owner_id': org1_admin._id}}
        )
        
        # Create Organization 2 - Champions Training Center
        print("Creating Champions Training Center...")
        org2 = Organization(
            name="Champions Training Center",
            owner_id=None,
            contact_info={
                'email': 'info@champions.com',
                'phone': '+1987654321'
            },
            address={
                'street': '456 Champions Blvd',
                'city': 'Champion City',
                'state': 'CC',
                'zip': '54321'
            },
            sports=['swimming', 'athletics', 'boxing']
        )
        result = mongo.db.organizations.insert_one(org2.to_dict())
        org2._id = result.inserted_id
        org2_id = str(org2._id)
        
        # Create Organization 2 Admin
        print("Creating Champions Training Center admin...")
        org2_admin = User(
            phone_number='+1987654321',
            name='Champions Admin',
            role='org_admin',
            password='admin456',
            organization_id=org2_id,
            created_by=str(super_admin._id)
        )
        org2_admin.verification_status = 'verified'
        result = mongo.db.users.insert_one(org2_admin.to_dict(include_sensitive=True))
        org2_admin._id = result.inserted_id
        
        # Update organization owner
        mongo.db.organizations.update_one(
            {'_id': org2._id},
            {'$set': {'owner_id': org2_admin._id}}
        )
        
        # Create users for Organization 1 (Elite Sports Academy)
        print("Creating users for Elite Sports Academy...")
        
        # Coach Admin
        coach_admin1 = User(
            phone_number='+1234567891',
            name='Senior Coach Smith',
            role='coach_admin',
            password='coach123',
            organization_id=org1_id,
            profile_data={
                'specialization': 'Football & Basketball',
                'experience_years': 8,
                'certifications': ['UEFA Level 2', 'Basketball Coaching License']
            },
            created_by=str(org1_admin._id)
        )
        coach_admin1.verification_status = 'verified'
        result = mongo.db.users.insert_one(coach_admin1.to_dict(include_sensitive=True))
        coach_admin1._id = result.inserted_id
        
        # Regular Coaches
        coaches1 = []
        coach_data = [
            {
                'phone': '+1234567892',
                'name': 'Coach Johnson',
                'specialization': 'Football',
                'experience': 5
            },
            {
                'phone': '+1234567893',
                'name': 'Coach Williams',
                'specialization': 'Basketball',
                'experience': 4
            },
            {
                'phone': '+1234567894',
                'name': 'Coach Brown',
                'specialization': 'Tennis',
                'experience': 6
            }
        ]
        
        for i, coach_info in enumerate(coach_data):
            coach = User(
                phone_number=coach_info['phone'],
                name=coach_info['name'],
                role='coach',
                password=f'coach{123+i}',
                organization_id=org1_id,
                profile_data={
                    'specialization': coach_info['specialization'],
                    'experience_years': coach_info['experience']
                },
                created_by=str(coach_admin1._id)
            )
            coach.verification_status = 'verified'
            result = mongo.db.users.insert_one(coach.to_dict(include_sensitive=True))
            coach._id = result.inserted_id
            coaches1.append(coach)
        
        # Create groups for Organization 1
        print("Creating groups for Elite Sports Academy...")
        groups1 = []
        group_data = [
            {
                'name': 'Beginners Football',
                'sport': 'football',
                'level': 'beginner',
                'coach': coaches1[0],
                'max_students': 15
            },
            {
                'name': 'Advanced Football',
                'sport': 'football',
                'level': 'advanced',
                'coach': coach_admin1,
                'max_students': 12
            },
            {
                'name': 'Basketball Juniors',
                'sport': 'basketball',
                'level': 'intermediate',
                'coach': coaches1[1],
                'max_students': 20
            },
            {
                'name': 'Tennis Basics',
                'sport': 'tennis',
                'level': 'beginner',
                'coach': coaches1[2],
                'max_students': 10
            }
        ]
        
        for group_info in group_data:
            group = Group(
                name=group_info['name'],
                organization_id=org1_id,
                coach_id=str(group_info['coach']._id),
                sport=group_info['sport'],
                level=group_info['level'],
                description=f"{group_info['level'].title()} level {group_info['sport']} training",
                max_students=group_info['max_students']
            )
            result = mongo.db.groups.insert_one(group.to_dict())
            group._id = result.inserted_id
            groups1.append(group)
        
        # Create students for Organization 1
        print("Creating students for Elite Sports Academy...")
        students1 = []
        for i in range(12):
            # Distribute students across groups
            assigned_groups = [str(groups1[i % len(groups1)]._id)]
            if i < 6:  # Some students in multiple groups
                assigned_groups.append(str(groups1[(i + 1) % len(groups1)]._id))
            
            student = User(
                phone_number=f'+123456780{i:02d}',
                name=f'Student {i+1}',
                role='student',
                organization_id=org1_id,
                groups=assigned_groups,
                profile_data={
                    'age': 16 + (i % 8),
                    'emergency_contact': f'+123456789{i:02d}',
                    'medical_info': 'No known allergies' if i % 3 == 0 else 'Asthma' if i % 3 == 1 else 'None',
                    'parent_name': f'Parent {i+1}',
                    'join_date': (datetime.utcnow() - timedelta(days=30+i*5)).isoformat()
                },
                created_by=str(coach_admin1._id)
            )
            student.verification_status = 'verified'
            result = mongo.db.users.insert_one(student.to_dict())
            student._id = result.inserted_id
            students1.append(student)
        
        # Create users for Organization 2 (Champions Training Center)
        print("Creating users for Champions Training Center...")
        
        # Coach Admin
        coach_admin2 = User(
            phone_number='+1987654322',
            name='Head Coach Martinez',
            role='coach_admin',
            password='coach789',
            organization_id=org2_id,
            profile_data={
                'specialization': 'Swimming & Athletics',
                'experience_years': 10,
                'certifications': ['Swimming Instructor Level 3', 'Athletics Coach']
            },
            created_by=str(org2_admin._id)
        )
        coach_admin2.verification_status = 'verified'
        result = mongo.db.users.insert_one(coach_admin2.to_dict(include_sensitive=True))
        coach_admin2._id = result.inserted_id
        
        # Regular Coaches for Org 2
        coaches2 = []
        coach_data2 = [
            {
                'phone': '+1987654323',
                'name': 'Coach Taylor',
                'specialization': 'Swimming',
                'experience': 7
            },
            {
                'phone': '+1987654324',
                'name': 'Coach Davis',
                'specialization': 'Athletics',
                'experience': 5
            }
        ]
        
        for i, coach_info in enumerate(coach_data2):
            coach = User(
                phone_number=coach_info['phone'],
                name=coach_info['name'],
                role='coach',
                password=f'coach{456+i}',
                organization_id=org2_id,
                profile_data={
                    'specialization': coach_info['specialization'],
                    'experience_years': coach_info['experience']
                },
                created_by=str(coach_admin2._id)
            )
            coach.verification_status = 'verified'
            result = mongo.db.users.insert_one(coach.to_dict(include_sensitive=True))
            coach._id = result.inserted_id
            coaches2.append(coach)
        
        # Create groups for Organization 2
        groups2 = []
        group_data2 = [
            {
                'name': 'Swimming Beginners',
                'sport': 'swimming',
                'level': 'beginner',
                'coach': coaches2[0],
                'max_students': 8
            },
            {
                'name': 'Track & Field',
                'sport': 'athletics',
                'level': 'intermediate',
                'coach': coaches2[1],
                'max_students': 15
            }
        ]
        
        for group_info in group_data2:
            group = Group(
                name=group_info['name'],
                organization_id=org2_id,
                coach_id=str(group_info['coach']._id),
                sport=group_info['sport'],
                level=group_info['level'],
                description=f"{group_info['level'].title()} level {group_info['sport']} training",
                max_students=group_info['max_students']
            )
            result = mongo.db.groups.insert_one(group.to_dict())
            group._id = result.inserted_id
            groups2.append(group)
        
        # Create students for Organization 2
        students2 = []
        for i in range(8):
            assigned_groups = [str(groups2[i % len(groups2)]._id)]
            
            student = User(
                phone_number=f'+198765432{i:02d}',
                name=f'Champion Student {i+1}',
                role='student',
                organization_id=org2_id,
                groups=assigned_groups,
                profile_data={
                    'age': 18 + (i % 6),
                    'emergency_contact': f'+198765499{i:02d}',
                    'medical_info': 'Cleared for all activities',
                    'parent_name': f'Champion Parent {i+1}',
                    'join_date': (datetime.utcnow() - timedelta(days=20+i*3)).isoformat()
                },
                created_by=str(coach_admin2._id)
            )
            student.verification_status = 'verified'
            result = mongo.db.users.insert_one(student.to_dict())
            student._id = result.inserted_id
            students2.append(student)
        
        # Create classes for both organizations
        print("Creating sample classes...")
        now = datetime.utcnow()
        
        # Classes for Organization 1
        classes1_data = [
            {
                'title': 'Football Skills Training',
                'coach': coaches1[0],
                'group': groups1[0],
                'scheduled_at': now + timedelta(hours=2),
                'sport': 'football'
            },
            {
                'title': 'Advanced Football Tactics',
                'coach': coach_admin1,
                'group': groups1[1],
                'scheduled_at': now + timedelta(days=1, hours=3),
                'sport': 'football'
            },
            {
                'title': 'Basketball Fundamentals',
                'coach': coaches1[1],
                'group': groups1[2],
                'scheduled_at': now + timedelta(days=2),
                'sport': 'basketball'
            },
            {
                'title': 'Tennis Basics Session',
                'coach': coaches1[2],
                'group': groups1[3],
                'scheduled_at': now - timedelta(days=1),
                'sport': 'tennis',
                'status': 'completed'
            }
        ]
        
        for class_info in classes1_data:
            new_class = Class(
                title=class_info['title'],
                organization_id=ObjectId(org1_id),
                coach_id=ObjectId(class_info['coach']._id),
                scheduled_at=class_info['scheduled_at'],
                duration_minutes=90,
                location={'name': 'Main Training Ground', 'address': '123 Sports Complex Road'},
                group_ids=[ObjectId(class_info['group']._id)],
                sport=class_info['sport'],
                level=class_info['group'].level,
                notes='Regular training session'
            )
            if 'status' in class_info:
                new_class.status = class_info['status']
            
            result = mongo.db.classes.insert_one(new_class.to_dict())
            new_class._id = result.inserted_id
        
        # Classes for Organization 2
        classes2_data = [
            {
                'title': 'Swimming Technique Workshop',
                'coach': coaches2[0],
                'group': groups2[0],
                'scheduled_at': now + timedelta(hours=4),
                'sport': 'swimming'
            },
            {
                'title': 'Track Training Session',
                'coach': coaches2[1],
                'group': groups2[1],
                'scheduled_at': now + timedelta(days=1, hours=2),
                'sport': 'athletics'
            }
        ]
        
        for class_info in classes2_data:
            new_class = Class(
                title=class_info['title'],
                organization_id=ObjectId(org2_id),
                coach_id=ObjectId(class_info['coach']._id),
                scheduled_at=class_info['scheduled_at'],
                duration_minutes=120,
                location={'name': 'Champions Pool & Track', 'address': '456 Champions Blvd'},
                group_ids=[ObjectId(class_info['group']._id)],
                sport=class_info['sport'],
                level=class_info['group'].level,
                notes='Intensive training'
            )
            
            result = mongo.db.classes.insert_one(new_class.to_dict())
            new_class._id = result.inserted_id
        
        # Create rubrics for both organizations
        print("Creating progress rubrics...")
        
        # Rubrics for Organization 1
        rubrics1 = ['Football Skills', 'Basketball Skills', 'Tennis Skills']
        for rubric_name in rubrics1:
            sport = rubric_name.split()[0].lower()
            rubric = Rubric(
                name=f'{rubric_name} Assessment',
                organization_id=ObjectId(org1_id),
                sport=sport
            )
            result = mongo.db.rubrics.insert_one(rubric.to_dict())
        
        # Rubrics for Organization 2  
        rubrics2 = ['Swimming Technique', 'Athletics Performance']
        for rubric_name in rubrics2:
            sport = rubric_name.split()[0].lower()
            rubric = Rubric(
                name=f'{rubric_name} Assessment',
                organization_id=ObjectId(org2_id),
                sport=sport
            )
            result = mongo.db.rubrics.insert_one(rubric.to_dict())
        
        # Create sample payments
        print("Creating sample payments...")
        
        # Payments for Organization 1 students
        for i, student in enumerate(students1[:6]):
            payment = Payment(
                student_id=str(student._id),
                organization_id=ObjectId(org1_id),
                amount=150.0,
                description='Monthly Training Fee - February 2024',
                due_date=date.today() + timedelta(days=5),
                payment_type='monthly'
            )
            payment.created_by = org1_admin._id
            
            if i < 2:  # Mark some as paid
                payment.mark_paid(
                    amount=150.0,
                    payment_method='bank_transfer',
                    reference=f'TXN{1000+i}',
                    marked_by=str(org1_admin._id)
                )
            elif i < 4:  # Some overdue
                payment.due_date = date.today() - timedelta(days=5)
                payment.status = 'overdue'
                payment.late_fee = 15.0
            
            mongo.db.payments.insert_one(payment.to_dict())
        
        # Payments for Organization 2 students
        for i, student in enumerate(students2[:4]):
            payment = Payment(
                student_id=str(student._id),
                organization_id=ObjectId(org2_id),
                amount=200.0,
                description='Monthly Training Fee - February 2024',
                due_date=date.today() + timedelta(days=10),
                payment_type='monthly'
            )
            payment.created_by = org2_admin._id
            
            if i < 1:  # Mark one as paid
                payment.mark_paid(
                    amount=200.0,
                    payment_method='cash',
                    reference=f'CASH{2000+i}',
                    marked_by=str(org2_admin._id)
                )
            
            mongo.db.payments.insert_one(payment.to_dict())
        
        # Create sample equipment listings
        print("Creating sample equipment listings...")
        
        # Equipment for Organization 1
        equipment1_data = [
            {
                'title': 'Wilson Football - Size 5',
                'description': 'Professional quality football in excellent condition. Used for only 6 months.',
                'price': 25.0,
                'owner': students1[0],
                'category': 'balls',
                'condition': 'excellent'
            },
            {
                'title': 'Nike Basketball Shoes - Size 10',
                'description': 'High-top basketball shoes, great for court play.',
                'price': 85.0,
                'owner': students1[1],
                'category': 'footwear',
                'condition': 'good'
            },
            {
                'title': 'Tennis Racket - Wilson Pro Staff',
                'description': 'Professional tennis racket with new strings.',
                'price': 120.0,
                'owner': coaches1[2],
                'category': 'equipment',
                'condition': 'excellent'
            }
        ]
        
        for equip_info in equipment1_data:
            equipment = Equipment(
                title=equip_info['title'],
                description=equip_info['description'],
                price=equip_info['price'],
                owner_id=str(equip_info['owner']._id),
                organization_id=ObjectId(org1_id),
                category=equip_info['category'],
                condition=equip_info['condition'],
                images=[f'https://example.com/{equip_info["category"]}.jpg'],
                contact_info={'phone': equip_info['owner'].phone_number},
                location='Sports City',
                negotiable=True
            )
            mongo.db.equipment.insert_one(equipment.to_dict())
        
        # Equipment for Organization 2
        equipment2_data = [
            {
                'title': 'Swimming Goggles - Speedo',
                'description': 'Anti-fog swimming goggles, barely used.',
                'price': 15.0,
                'owner': students2[0],
                'category': 'accessories',
                'condition': 'excellent'
            },
            {
                'title': 'Running Spikes - Size 9',
                'description': 'Track and field spikes for sprinting.',
                'price': 75.0,
                'owner': students2[1],
                'category': 'footwear',
                'condition': 'good'
            }
        ]
        
        for equip_info in equipment2_data:
            equipment = Equipment(
                title=equip_info['title'],
                description=equip_info['description'],
                price=equip_info['price'],
                owner_id=str(equip_info['owner']._id),
                organization_id=ObjectId(org2_id),
                category=equip_info['category'],
                condition=equip_info['condition'],
                images=[f'https://example.com/{equip_info["category"]}.jpg'],
                contact_info={'phone': equip_info['owner'].phone_number},
                location='Champion City',
                negotiable=True
            )
            mongo.db.equipment.insert_one(equipment.to_dict())
        
        print("\n" + "="*60)
        print("🎉 MULTI-TENANT SEED DATA CREATED SUCCESSFULLY!")
        print("="*60)
        print("\n📞 LOGIN CREDENTIALS:")
        print("="*30)
        print(f"🔧 Super Admin: {super_admin.phone_number} / superadmin123")
        print(f"   (Can create organizations and manage everything)")
        print()
        print("🏟️  ELITE SPORTS ACADEMY:")
        print(f"   👑 Org Admin: {org1_admin.phone_number} / admin123")
        print(f"   👨‍🏫 Coach Admin: {coach_admin1.phone_number} / coach123")
        print(f"   🏃‍♂️ Coach (Football): {coaches1[0].phone_number} / coach123")
        print(f"   🏀 Coach (Basketball): {coaches1[1].phone_number} / coach124")
        print(f"   🎾 Coach (Tennis): {coaches1[2].phone_number} / coach125")
        print(f"   🎓 Students: +123456780XX (12 students)")
        print()
        print("🏊 CHAMPIONS TRAINING CENTER:")
        print(f"   👑 Org Admin: {org2_admin.phone_number} / admin456")
        print(f"   👨‍🏫 Coach Admin: {coach_admin2.phone_number} / coach789")
        print(f"   🏊‍♂️ Swimming Coach: {coaches2[0].phone_number} / coach456")
        print(f"   🏃‍♂️ Athletics Coach: {coaches2[1].phone_number} / coach457")
        print(f"   🎓 Students: +19876543XX (8 students)")
        print()
        print("📊 CREATED DATA:")
        print(f"   • 2 Organizations")
        print(f"   • 21 Users (1 super admin, 2 org admins, 2 coach admins, 5 coaches, 20 students)")
        print(f"   • 6 Groups")
        print(f"   • 6 Classes (some past, some future)")
        print(f"   • 4 Progress Rubrics")
        print(f"   • 10 Payment Records")
        print(f"   • 5 Equipment Listings")
        print("="*60)
            return True
            
        except Exception as e:
            print(f"❌ An unexpected error occurred during seed data creation: {e}")
            return False

if __name__ == '__main__':
    success = create_seed_data()
    if success:
        print("\n✅ Seed data creation completed successfully!")
    else:
        print("\n❌ Seed data creation failed!")
        exit(1) 