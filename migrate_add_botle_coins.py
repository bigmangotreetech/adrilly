"""
Migration script to add botle_coins field to all existing users
This script adds the botle_coins field with default value 0 to all users in the database
"""

from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_add_botle_coins():
    """Add botle_coins field to all users"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        db_name = os.getenv('MONGO_DB_NAME', 'coaching_center')
        
        print(f"Connecting to MongoDB: {mongo_uri}")
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        # Get users collection
        users_collection = db.users
        
        # Count total users
        total_users = users_collection.count_documents({})
        print(f"\nTotal users in database: {total_users}")
        
        # Count users without botle_coins field
        users_without_coins = users_collection.count_documents({'botle_coins': {'$exists': False}})
        print(f"Users without botle_coins field: {users_without_coins}")
        
        if users_without_coins == 0:
            print("\n✅ All users already have botle_coins field. No migration needed.")
            return
        
        # Ask for confirmation
        print("\n⚠️  This will add botle_coins: 0 to all users without this field.")
        confirmation = input("Do you want to proceed? (yes/no): ").strip().lower()
        
        if confirmation != 'yes':
            print("Migration cancelled.")
            return
        
        # Update all users without botle_coins field
        result = users_collection.update_many(
            {'botle_coins': {'$exists': False}},
            {
                '$set': {
                    'botle_coins': 0,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        print(f"\n✅ Migration completed successfully!")
        print(f"   - Users updated: {result.modified_count}")
        print(f"   - Users matched: {result.matched_count}")
        
        # Verify the migration
        remaining = users_collection.count_documents({'botle_coins': {'$exists': False}})
        if remaining == 0:
            print("\n✅ All users now have botle_coins field!")
        else:
            print(f"\n⚠️  Warning: {remaining} users still don't have botle_coins field")
        
        # Show sample of updated users
        print("\nSample of updated users:")
        sample_users = users_collection.find({'botle_coins': 0}).limit(5)
        for user in sample_users:
            print(f"  - {user.get('name', 'Unknown')} ({user.get('role', 'unknown')}) - Botle Coins: {user.get('botle_coins', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if 'client' in locals():
            client.close()
            print("\nDatabase connection closed.")

if __name__ == '__main__':
    print("=" * 60)
    print("Botle Coins Migration Script")
    print("=" * 60)
    print("\nThis script will add the 'botle_coins' field to all users")
    print("who don't have it, with a default value of 0.")
    print("\nBotle Coins System:")
    print("  - 1 coin = ₹1")
    print("  - Users earn coins for attending classes, achievements, etc.")
    print("  - Coins can be redeemed for rewards")
    print()
    
    migrate_add_botle_coins()

