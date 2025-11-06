#!/usr/bin/env python3
"""
Generate WhatsApp Analytics
Generates daily WhatsApp analytics reports for organizations.
"""

import os
import sys
from datetime import datetime, timedelta
from bson import ObjectId

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    try:
        from app.app import create_app
        from app.extensions import mongo
        from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
        
        app, _ = create_app()
        
        with app.app_context():
            whatsapp_service = EnhancedWhatsAppService()
            organizations = mongo.db.organizations.find({'is_active': True})
            
            results = {'organizations_processed': 0, 'reports_generated': 0}
            
            for org_data in organizations:
                org_id = str(org_data['_id'])
                org_name = org_data.get('name', 'Unknown')
                
                analytics = whatsapp_service.get_messaging_analytics(org_id, days=7)
                
                if analytics:
                    report = {
                        'organization_id': ObjectId(org_id),
                        'organization_name': org_name,
                        'period_start': datetime.utcnow() - timedelta(days=7),
                        'period_end': datetime.utcnow(),
                        'analytics': analytics,
                        'generated_at': datetime.utcnow()
                    }
                    
                    mongo.db.whatsapp_analytics_reports.insert_one(report)
                    results['reports_generated'] += 1
                
                results['organizations_processed'] += 1
            
            print(f"✅ Generated {results['reports_generated']} analytics reports")
            print(f"   Processed {results['organizations_processed']} organizations")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

