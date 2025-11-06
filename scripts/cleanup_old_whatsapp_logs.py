#!/usr/bin/env python3
"""
Cleanup Old WhatsApp Logs
Cleans up old WhatsApp logs older than 90 days.
"""

import os
import sys
from datetime import datetime, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        
        app, _ = create_app()
        
        with app.app_context():
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            # Delete old message logs
            msg_result = mongo.db.whatsapp_logs.delete_many({
                'timestamp': {'$lt': cutoff_date}
            })
            
            # Delete old RSVP logs
            rsvp_result = mongo.db.rsvp_logs.delete_many({
                'timestamp': {'$lt': cutoff_date}
            })
            
            print(f"✅ Cleaned up {msg_result.deleted_count} WhatsApp message logs")
            print(f"   Cleaned up {rsvp_result.deleted_count} RSVP logs")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
