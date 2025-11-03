#!/usr/bin/env python3
"""Check current indexes"""
from app.app import create_app
from app.extensions import mongo

app, _ = create_app()
with app.app_context():
    print("Current indexes on users collection:")
    for idx in mongo.db.users.list_indexes():
        print(f"  Name: {idx.get('name')}")
        print(f"  Keys: {idx.get('key')}")
        print(f"  Unique: {idx.get('unique', False)}")
        print(f"  Sparse: {idx.get('sparse', False)}")
        print("  ---")

