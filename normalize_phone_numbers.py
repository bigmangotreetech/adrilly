#!/usr/bin/env python3
"""
Normalize phone numbers by removing + and +1 prefixes for consistency
"""

from app.app import create_app
from datetime import datetime
import re

def normalize_phone_numbers():
    """Find and normalize all phone numbers by removing + and +1 prefixes"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("🔍 Finding all users and their current phone numbers...")
        
        # Find all users
        all_users = list(mongo.db.users.find({}))
        
        if not all_users:
            print("❌ No users found in database")
            return False
        
        print(f"📊 Found {len(all_users)} users in database")
        
        # Analyze current phone number formats
        users_to_update = []
        already_normalized = []
        
        print("\n📱 Current phone number analysis:")
        print("-" * 50)
        
        for user in all_users:
            name = user.get('name', 'Unknown')
            current_phone = user.get('phone_number', '')
            
            if not current_phone:
                print(f"⚠️  {name}: NO PHONE NUMBER")
                continue
                
            # Normalize the phone number
            normalized_phone = normalize_phone(current_phone)
            
            print(f"📞 {name}: {current_phone}")
            
            if current_phone != normalized_phone:
                users_to_update.append({
                    'user': user,
                    'current_phone': current_phone,
                    'normalized_phone': normalized_phone
                })
                print(f"   ➤ Will update to: {normalized_phone}")
            else:
                already_normalized.append(user)
                print(f"   ✅ Already normalized")
        
        print(f"\n📊 ANALYSIS SUMMARY:")
        print(f"   • Total users: {len(all_users)}")
        print(f"   • Need normalization: {len(users_to_update)}")
        print(f"   • Already normalized: {len(already_normalized)}")
        
        if not users_to_update:
            print("\n✅ All phone numbers are already normalized!")
            return True
        
        # Show what will be updated
        print(f"\n🔧 PHONES TO BE UPDATED:")
        print("-" * 50)
        for item in users_to_update:
            user = item['user']
            print(f"📱 {user.get('name', 'Unknown')}")
            print(f"   From: {item['current_phone']}")
            print(f"   To:   {item['normalized_phone']}")
            print()
        
        # Check for potential duplicates after normalization
        normalized_phones = [item['normalized_phone'] for item in users_to_update]
        existing_normalized = [user.get('phone_number', '') for user in already_normalized]
        all_normalized = normalized_phones + existing_normalized
        
        duplicates = check_for_duplicates(all_normalized)
        if duplicates:
            print("⚠️  WARNING: Potential duplicate phone numbers after normalization:")
            for phone, count in duplicates.items():
                print(f"   📞 {phone} appears {count} times")
            print("\nContinuing with update... duplicates will need manual review.")
        
        # Perform the updates
        print(f"\n🔧 Updating {len(users_to_update)} phone numbers...")
        updated_count = 0
        
        for item in users_to_update:
            user = item['user']
            user_id = user['_id']
            new_phone = item['normalized_phone']
            
            try:
                result = mongo.db.users.update_one(
                    {'_id': user_id},
                    {
                        '$set': {
                            'phone_number': new_phone,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ Updated {user.get('name', 'Unknown')}: {new_phone}")
                else:
                    print(f"❌ Failed to update {user.get('name', 'Unknown')}")
                    
            except Exception as e:
                print(f"❌ Error updating {user.get('name', 'Unknown')}: {e}")
        
        print(f"\n📊 UPDATE SUMMARY:")
        print(f"   • Users processed: {len(users_to_update)}")
        print(f"   • Successfully updated: {updated_count}")
        print(f"   • Failed updates: {len(users_to_update) - updated_count}")
        
        if updated_count > 0:
            print(f"\n📋 NORMALIZATION RULES APPLIED:")
            print(f"   • Removed '+' prefix")
            print(f"   • Removed '+1' prefix") 
            print(f"   • Kept only digits")
            print(f"   • Preserved original number after country code removal")
        
        return True

def normalize_phone(phone_number):
    """
    Normalize a phone number by removing + and +1 prefixes
    """
    if not phone_number:
        return phone_number
    
    # Convert to string and strip whitespace
    phone = str(phone_number).strip()
    
    # Remove + prefix if present
    if phone.startswith('+'):
        phone = phone[1:]
    
    # Remove leading 1 if it's a US/Canada code (assuming 10-digit numbers)
    if phone.startswith('1') and len(phone) == 11:
        phone = phone[1:]
    
    # Keep only digits
    phone = re.sub(r'[^0-9]', '', phone)
    
    return phone

def check_for_duplicates(phone_list):
    """Check for duplicate phone numbers in a list"""
    phone_counts = {}
    for phone in phone_list:
        if phone:  # Skip empty phones
            phone_counts[phone] = phone_counts.get(phone, 0) + 1
    
    # Return only duplicates
    return {phone: count for phone, count in phone_counts.items() if count > 1}

def verify_normalization():
    """Verify the normalization by showing all current phone numbers"""
    app, _ = create_app()
    
    with app.app_context():
        from app.extensions import mongo
        
        print("\n🔍 VERIFICATION: Current phone numbers after normalization")
        print("=" * 60)
        
        all_users = list(mongo.db.users.find({}).sort('role', 1))
        
        # Group by role for better display
        users_by_role = {}
        for user in all_users:
            role = user.get('role', 'unknown')
            if role not in users_by_role:
                users_by_role[role] = []
            users_by_role[role].append(user)
        
        role_order = ['super_admin', 'org_admin', 'coach_admin', 'coach', 'student']
        
        for role in role_order:
            if role in users_by_role:
                users = users_by_role[role]
                role_name = role.replace('_', ' ').title()
                print(f"\n📱 {role_name.upper()} ({len(users)} users):")
                print("-" * 30)
                
                for user in users:
                    name = user.get('name', 'Unknown')
                    phone = user.get('phone_number', 'NO PHONE')
                    print(f"   {name}: {phone}")
        
        # Check for duplicates
        all_phones = [user.get('phone_number', '') for user in all_users if user.get('phone_number')]
        duplicates = check_for_duplicates(all_phones)
        
        print(f"\n📊 VERIFICATION SUMMARY:")
        print(f"   • Total users: {len(all_users)}")
        print(f"   • Users with phones: {len(all_phones)}")
        print(f"   • Duplicate phones: {len(duplicates)}")
        
        if duplicates:
            print(f"\n⚠️  DUPLICATE PHONE NUMBERS:")
            for phone, count in duplicates.items():
                print(f"   📞 {phone} (used {count} times)")
        else:
            print(f"\n✅ No duplicate phone numbers found!")

if __name__ == '__main__':
    try:
        print("🚀 Starting phone number normalization...")
        print("=" * 60)
        
        # Step 1: Normalize phone numbers
        success = normalize_phone_numbers()
        
        if success:
            # Step 2: Verify the results
            verify_normalization()
            
            print("\n" + "=" * 60)
            print("✅ Phone number normalization completed successfully!")
            print("📱 All phone numbers are now in consistent format (no + prefix)")
        else:
            print("\n❌ Phone number normalization failed!")
            
    except Exception as e:
        print(f"\n❌ Error during phone normalization: {e}")
        print("Make sure your Flask app and MongoDB are running.") 