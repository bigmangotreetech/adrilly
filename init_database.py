#!/usr/bin/env python3
"""
Database initialization script for Adrilly sports coaching system
This script ensures that MongoDB database and all required collections exist
"""

import os
import sys
from app.app import create_app
from app.extensions import mongo, verify_database_connection, ensure_collection_exists

def init_database():
    """Initialize database with all required collections and indexes"""
    print("🚀 Initializing Adrilly Sports Coaching Database")
    print("=" * 50)
    
    # Create Flask app context
    app, _ = create_app()
    
    with app.app_context():
        # Ensure mongo is properly initialized
        try:
            if not hasattr(mongo, 'db') or mongo.db is None:
                print("❌ MongoDB extension not properly initialized")
                print("   Check your MONGODB_URI configuration")
                return False
        except NotImplementedError:
            # mongo.db exists but doesn't support boolean testing
            pass
        
        # Step 1: Verify database connection
        print("1️⃣ Verifying database connection...")
        success, message = verify_database_connection()
        if not success:
            print(f"❌ {message}")
            print("\n💡 Tips to fix database connection:")
            print("   • Ensure MongoDB is running")
            print("   • Check MONGODB_URI in your .env file")
            print("   • Verify network connectivity to your MongoDB server")
            return False
        print(f"✅ {message}")
        
        # Step 2: Create required collections
        print("\n2️⃣ Creating required collections...")
        required_collections = [
            'users',
            'organizations', 
            'groups',
            'classes',
            'attendance',
            'rubrics',
            'progress',
            'payments',
            'payment_plans',
            'equipment'
        ]
        
        collections_created = 0
        collections_existed = 0
        
        for collection_name in required_collections:
            success, message = ensure_collection_exists(collection_name)
            if success:
                if "Created" in message:
                    collections_created += 1
                    print(f"✨ {message}")
                else:
                    collections_existed += 1
                    print(f"✅ {message}")
            else:
                print(f"❌ {message}")
                return False
        
        print(f"\n📊 Collections Summary:")
        print(f"   • Created: {collections_created}")
        print(f"   • Already existed: {collections_existed}")
        print(f"   • Total: {len(required_collections)}")
        
        # Step 3: Create database indexes for optimal performance
        print("\n3️⃣ Creating database indexes...")
        try:
            # Users collection indexes
            mongo.db.users.create_index("phone_number", unique=True)
            mongo.db.users.create_index("organization_id")
            mongo.db.users.create_index([("role", 1), ("organization_id", 1)])
            mongo.db.users.create_index("created_by")
            print("✅ Users collection indexes created")
            
            # Organizations collection indexes
            mongo.db.organizations.create_index("owner_id")
            mongo.db.organizations.create_index("name")
            print("✅ Organizations collection indexes created")
            
            # Classes collection indexes
            mongo.db.classes.create_index([("organization_id", 1), ("scheduled_at", 1)])
            mongo.db.classes.create_index("coach_id")
            mongo.db.classes.create_index([("status", 1), ("scheduled_at", 1)])
            print("✅ Classes collection indexes created")
            
            # Attendance collection indexes
            mongo.db.attendance.create_index([("class_id", 1), ("student_id", 1)], unique=True)
            mongo.db.attendance.create_index("organization_id")
            mongo.db.attendance.create_index("created_at")
            print("✅ Attendance collection indexes created")
            
            # Payments collection indexes
            mongo.db.payments.create_index([("student_id", 1), ("organization_id", 1)])
            mongo.db.payments.create_index([("status", 1), ("due_date", 1)])
            mongo.db.payments.create_index("created_by")
            print("✅ Payments collection indexes created")
            
            # Groups collection indexes
            mongo.db.groups.create_index([("organization_id", 1), ("coach_id", 1)])
            mongo.db.groups.create_index("sport")
            print("✅ Groups collection indexes created")
            
            # Equipment collection indexes
            mongo.db.equipment.create_index([("organization_id", 1), ("status", 1)])
            mongo.db.equipment.create_index("owner_id")
            mongo.db.equipment.create_index([("category", 1), ("condition", 1)])
            print("✅ Equipment collection indexes created")
            
            # Progress tracking indexes
            mongo.db.progress.create_index([("student_id", 1), ("rubric_id", 1)])
            mongo.db.progress.create_index("organization_id")
            print("✅ Progress collection indexes created")
            
            # Rubrics indexes
            mongo.db.rubrics.create_index([("organization_id", 1), ("sport", 1)])
            print("✅ Rubrics collection indexes created")
            
            # Payment plans indexes
            mongo.db.payment_plans.create_index([("organization_id", 1), ("student_id", 1)])
            mongo.db.payment_plans.create_index("status")
            print("✅ Payment plans collection indexes created")
            
        except Exception as e:
            print(f"⚠️ Warning: Some indexes may not have been created: {e}")
            print("   This is normal if indexes already exist")
        
        print("\n🎉 Database initialization completed successfully!")
        print("=" * 50)
        print("\n📝 Next Steps:")
        print("   1. Run 'python seed_data.py' to populate with sample data")
        print("   2. Run 'python run.py' to start the application")
        print("   3. Test the API endpoints")
        
        return True

def check_environment():
    """Check if required environment variables are set"""
    print("🔍 Checking environment configuration...")
    
    # Check if we have a MongoDB URI
    mongodb_uri = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URI')
    if not mongodb_uri:
        print("⚠️ Warning: No MONGODB_URI found in environment")
        print("   Using default: mongodb://localhost:27017/sports_coaching")
    else:
        # Don't print the full URI for security, just confirm it exists
        if 'localhost' in mongodb_uri:
            print("✅ Found local MongoDB configuration")
        else:
            print("✅ Found remote MongoDB configuration")
    
    return True

if __name__ == '__main__':
    print("Adrilly Sports Coaching - Database Initialization")
    print("=" * 50)
    
    # Check environment first
    if not check_environment():
        sys.exit(1)
    
    # Initialize database
    success = init_database()
    
    if success:
        print("\n✅ Database initialization successful!")
        sys.exit(0)
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1) 