#!/usr/bin/env python3
"""Clean up existing users by removing email/phone fields when they are None"""
from app.app import create_app
from app.extensions import mongo

app, _ = create_app()
with app.app_context():
    print("Cleaning up users with None email/phone fields...")
    
    # Find users with email: None and remove the field
    result_email = mongo.db.users.update_many(
        {'email': None},
        {'$unset': {'email': ''}}
    )
    print(f"Removed 'email' field from {result_email.modified_count} users")
    
    # Find users with phone_number: None and remove the field  
    result_phone = mongo.db.users.update_many(
        {'phone_number': None},
        {'$unset': {'phone_number': ''}}
    )
    print(f"Removed 'phone_number' field from {result_phone.modified_count} users")
    
    # Also clean up empty strings
    result_email_empty = mongo.db.users.update_many(
        {'email': ''},
        {'$unset': {'email': ''}}
    )
    print(f"Removed empty 'email' field from {result_email_empty.modified_count} users")
    
    result_phone_empty = mongo.db.users.update_many(
        {'phone_number': ''},
        {'$unset': {'phone_number': ''}}
    )
    print(f"Removed empty 'phone_number' field from {result_phone_empty.modified_count} users")
    
    print("Cleanup completed!")

