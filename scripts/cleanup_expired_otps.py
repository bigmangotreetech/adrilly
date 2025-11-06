#!/usr/bin/env python3
"""
Cleanup Expired OTPs
Cleans up expired OTP codes from the database.
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        
        app, _ = create_app()
        
        with app.app_context():
            now = datetime.utcnow()
            
            result = mongo.db.users.update_many(
                {
                    'otp_expires_at': {'$lt': now},
                    'otp_code': {'$ne': None}
                },
                {
                    '$set': {
                        'otp_code': None,
                        'otp_expires_at': None,
                        'updated_at': now
                    }
                }
            )
            
            print(f"✅ Cleaned up {result.modified_count} expired OTPs")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
