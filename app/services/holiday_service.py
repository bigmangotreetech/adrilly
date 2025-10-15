from datetime import datetime, date
from bson import ObjectId
from flask import current_app
from app.extensions import mongo
from app.models.holiday import Holiday
from app.models.org_holiday import OrgHoliday

class HolidayService:
    """Service class for managing holidays and organization holiday associations"""
    
    @staticmethod
    def get_organization_holidays(organization_id, year=None, include_inactive=False):
        """
        Get all holidays for an organization (both master holidays they've imported 
        and their custom holidays)
        
        Returns populated holiday data with organization-specific overrides
        """
        try:
            org_id = ObjectId(organization_id)
            current_year = year or datetime.now().year
            next_year = current_year + 1

            current_year_date = datetime(current_year, 1, 1)
            next_year_date = datetime(next_year, 1, 1)
            
            # Build aggregation pipeline to get organization holidays with populated data
            pipeline = [
                # Match organization holidays
                {
                    '$match': {
                        'organization_id': org_id,
                        'is_active': True if not include_inactive else {'$in': [True, False]}
                    }
                },
                # Lookup the master holiday data
                {
                    '$lookup': {
                        'from': 'holidays',
                        'localField': 'holiday_id',
                        'foreignField': '_id',
                        'as': 'holiday_data'
                    }
                },
                # Unwind the holiday data
                {
                    '$unwind': '$holiday_data'
                },
                # Filter by year
                {
                    '$match': {
                        'holiday_data.date_observed': {'$gte': current_year_date, '$lte': next_year_date}
                    }
                },
                # Project the final structure
                {
                    '$project': {
                        '_id': 1,
                        'holiday_id': 1,
                        'organization_id': 1,
                        'is_active': 1,
                        'custom_name': 1,
                        'custom_description': 1,
                        'affects_scheduling': 1,
                        'created_by': 1,
                        'notes': 1,
                        'created_at': 1,
                        'updated_at': 1,
                        'imported_at': 1,
                        # Holiday data
                        'name': {'$ifNull': ['$custom_name', '$holiday_data.name']},
                        'description': {'$ifNull': ['$custom_description', '$holiday_data.description']},
                        'date_observed': '$holiday_data.date_observed',
                        'country_code': '$holiday_data.country_code',
                        'is_public_holiday': '$holiday_data.is_public_holiday',
                        'locations': '$holiday_data.locations',
                        'holiday_types': '$holiday_data.holiday_types',
                        'source': '$holiday_data.source',
                        'year': '$holiday_data.year',
                        'api_data': '$holiday_data.api_data'
                    }
                },
                # Sort by date
                {
                    '$sort': {'date_observed': 1}
                }
            ]
            
            holidays = list(mongo.db.org_holidays.aggregate(pipeline))
            
            # Convert ObjectIds to strings for frontend
            for holiday in holidays:
                holiday['_id'] = str(holiday['_id'])
                holiday['holiday_id'] = str(holiday['holiday_id'])
                holiday['organization_id'] = str(holiday['organization_id'])
                if holiday.get('created_by'):
                    holiday['created_by'] = str(holiday['created_by'])
            
            return holidays
            
        except Exception as e:
            current_app.logger.error(f"Error getting organization holidays: {str(e)}")
            return []
    
    @staticmethod
    def get_master_holidays(year=None, country_code='IN'):
        """Get master holidays (available for import by organizations)"""
        try:
            current_year = year or datetime.now().year
            next_year = current_year + 1

            current_year_date = datetime(current_year, 1, 1)
            next_year_date = datetime(next_year, 1, 1)

            query = {
                'date_observed': {'$gte': current_year_date, '$lte': next_year_date}
            }
            
            holidays = list(mongo.db.holidays.find(query).sort('date_observed', 1))
            # Convert ObjectIds to strings
            for holiday in holidays:
                holiday['_id'] = str(holiday['_id'])
            
            return holidays
            
        except Exception as e:
            current_app.logger.error(f"Error getting master holidays: {str(e)}")
            return []
    
    @staticmethod
    def get_available_holidays_for_org(organization_id, year=None):
        """Get master holidays that organization hasn't imported yet"""
        try:
            org_id = ObjectId(organization_id)
            current_year = year or datetime.now().year
            
            # Get all master holidays
            master_holidays = HolidayService.get_master_holidays(year=current_year)
            
            # Get already imported holiday IDs
            imported_holiday_ids = set()
            org_holidays = mongo.db.org_holidays.find({
                'organization_id': org_id
            }, {'holiday_id': 1})
            
            for org_holiday in org_holidays:
                imported_holiday_ids.add(str(org_holiday['holiday_id']))
            
            # Filter out already imported holidays
            available_holidays = [
                holiday for holiday in master_holidays 
                if holiday['_id'] not in imported_holiday_ids
            ]
            
            return available_holidays
            
        except Exception as e:
            current_app.logger.error(f"Error getting available holidays: {str(e)}")
            return []
    
    @staticmethod
    def import_holidays_to_organization(organization_id, holiday_ids, created_by=None):
        """Import selected master holidays to organization"""
        try:
            org_id = ObjectId(organization_id)
            imported_count = 0
            errors = []
            
            for holiday_id in holiday_ids:
                try:
                    # Check if holiday exists in master collection
                    master_holiday = mongo.db.holidays.find_one({'_id': ObjectId(holiday_id)})
                    if not master_holiday:
                        errors.append(f"Holiday {holiday_id} not found in master collection")
                        continue
                    
                    # Check if already imported
                    existing = mongo.db.org_holidays.find_one({
                        'organization_id': org_id,
                        'holiday_id': ObjectId(holiday_id)
                    })
                    
                    if existing:
                        errors.append(f"Holiday '{master_holiday.get('name', holiday_id)}' already imported")
                        continue
                    
                    # Create organization holiday association
                    org_holiday = OrgHoliday(
                        holiday_id=holiday_id,
                        organization_id=organization_id,
                        created_by=created_by,
                        affects_scheduling=True
                    )
                    
                    result = mongo.db.org_holidays.insert_one(org_holiday.to_dict())
                    if result.inserted_id:
                        imported_count += 1
                        current_app.logger.info(f"Imported holiday {master_holiday.get('name')} to organization {organization_id}")
                    
                except Exception as e:
                    errors.append(f"Error importing holiday {holiday_id}: {str(e)}")
            
            return {
                'imported_count': imported_count,
                'errors': errors,
                'success': imported_count > 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Error importing holidays: {str(e)}")
            return {
                'imported_count': 0,
                'errors': [str(e)],
                'success': False
            }
    
    @staticmethod
    def create_custom_holiday(organization_id, name, date_observed, description=None, 
                            affects_scheduling=True, created_by=None):
        """Create a custom holiday for an organization"""
        try:
            org_id = ObjectId(organization_id)
            
            # First create the master holiday entry
            master_holiday = Holiday(
                name=name,
                date_observed=date_observed,
                description=description,
                country_code='IN',
                is_public_holiday=False,  # Custom holidays are not public
                source='custom',
                affects_scheduling=affects_scheduling
            )
            master_holiday.created_by = ObjectId(created_by) if created_by else None
            
            # Insert master holiday
            master_result = mongo.db.holidays.insert_one(master_holiday.to_dict())
            master_holiday._id = master_result.inserted_id
            
            # Create organization association
            org_holiday = OrgHoliday(
                holiday_id=master_holiday._id,
                organization_id=organization_id,
                created_by=created_by,
                affects_scheduling=affects_scheduling
            )
            
            org_result = mongo.db.org_holidays.insert_one(org_holiday.to_dict())
            org_holiday._id = org_result.inserted_id
            
            current_app.logger.info(f"Created custom holiday '{name}' for organization {organization_id}")
            
            return {
                'success': True,
                'master_holiday': master_holiday.to_dict(),
                'org_holiday': org_holiday.to_dict()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error creating custom holiday: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def remove_holiday_from_organization(organization_id, org_holiday_id):
        """Remove a holiday from an organization (soft delete)"""
        try:
            org_id = ObjectId(organization_id)
            
            result = mongo.db.org_holidays.update_one(
                {
                    '_id': ObjectId(org_holiday_id),
                    'organization_id': org_id
                },
                {
                    '$set': {
                        'is_active': False,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                current_app.logger.info(f"Removed holiday {org_holiday_id} from organization {organization_id}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Holiday not found or already removed'}
            
        except Exception as e:
            current_app.logger.error(f"Error removing holiday: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def update_organization_holiday(organization_id, org_holiday_id, **updates):
        """Update organization-specific holiday settings"""
        try:
            org_id = ObjectId(organization_id)
            
            # Prepare update data
            update_data = {
                'updated_at': datetime.utcnow()
            }
            
            allowed_fields = ['custom_name', 'custom_description', 'affects_scheduling', 'is_active', 'notes']
            for field in allowed_fields:
                if field in updates:
                    update_data[field] = updates[field]
            
            result = mongo.db.org_holidays.update_one(
                {
                    '_id': ObjectId(org_holiday_id),
                    'organization_id': org_id
                },
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                current_app.logger.info(f"Updated holiday {org_holiday_id} for organization {organization_id}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Holiday not found'}
            
        except Exception as e:
            current_app.logger.error(f"Error updating holiday: {str(e)}")
            return {'success': False, 'error': str(e)}
