#!/usr/bin/env python3
"""Test user creation to debug the issue"""
from app.app import create_app
from app.extensions import mongo
from app.models.user import User
from bson import ObjectId

app, _ = create_app()
with app.app_context():
    # Test creating a user with only phone (no email)
    try:
        test_user = User(
            phone_number="9998887776",
            name="Test User",
            email=None,  # Explicitly None
            role="student"
        )
        
        user_dict = test_user.to_dict(include_sensitive=True)
        print("User dict before MongoDB operations:")
        print(f"  email: {repr(user_dict.get('email'))}")
        print(f"  phone_number: {repr(user_dict.get('phone_number'))}")
        print(f"  email type: {type(user_dict.get('email'))}")
        print(f"  phone_number type: {type(user_dict.get('phone_number'))}")
        
        # Check if email field exists at all
        if 'email' in user_dict:
            print(f"  email field EXISTS in dict: {user_dict['email']}")
        else:
            print("  email field DOES NOT EXIST in dict")
            
        # Remove email field if it's None to test sparse index behavior
        if user_dict.get('email') is None:
            user_dict.pop('email', None)
            print("  Removed email field from dict (None value)")
        
        if user_dict.get('phone_number') is None:
            user_dict.pop('phone_number', None)
            print("  Removed phone_number field from dict (None value)")
        
        print("\nUser dict after cleanup:")
        print(f"  email in dict: {'email' in user_dict}")
        print(f"  phone_number in dict: {'phone_number' in user_dict}")
        
        # Check existing users with null email
        null_email_count = mongo.db.users.count_documents({'email': None})
        print(f"\nExisting users with email: None: {null_email_count}")
        
        null_phone_count = mongo.db.users.count_documents({'phone_number': None})
        print(f"Existing users with phone_number: None: {null_phone_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

