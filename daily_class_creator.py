#!/usr/bin/env python3
"""
Daily Class Creation Script for botle

This script runs daily to automatically create classes for organizations based on their centers' schedules.
Each class is created with the appropriate center_id and organization_id.

Usage:
    python daily_class_creator.py [--date YYYY-MM-DD] [--org-id ORG_ID] [--days-ahead N]

Arguments:
    --date: Specific date to create classes for (default: tomorrow)
    --org-id: Create classes only for specific organization (default: all)
    --days-ahead: Number of days ahead to create classes (default: 7)
"""

import os
import sys
import argparse
from datetime import datetime, time, timedelta, timezone

from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from app.models.class_schedule import Class
from app.models.center import Center
from app.models.organization import Organization, Group
from app.models.user import User


class DailyClassCreator:
    """Service for creating daily classes based on center schedules"""
    
    def __init__(self):
        """Initialize the class creator with database connection"""
        self.mongo_uri = os.environ.get('MONGODB_URI')
        print(self.mongo_uri)
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client.adrilly
        
    
    def get_day_of_week(self, date):
        """Convert date to day of week string used in schedules"""
        # 0=Monday, 1=Tuesday, ..., 6=Sunday
        days = ['0', '1', '2', '3', '4', '5', '6']
        return days[date.weekday()]
    
    def get_active_organizations(self, org_id=None):
        """Get all active organizations or specific organization"""
        query = {'is_active': True, 'subscription_status': 'active'}
        if org_id:
            query['_id'] = ObjectId(org_id) if isinstance(org_id, str) else org_id
        
        # print db name
        print(self.db.name)
        return list(self.db.organizations.find(query))
    
    def get_organization_centers(self, org_id):
        """Get all active centers for an organization"""
        org_id_obj = ObjectId(org_id) if isinstance(org_id, str) else org_id
        return list(self.db.centers.find({
            'organization_id': org_id_obj,
            'is_active': True
        }))
    
    def get_center_schedules(self, center_id, day_of_week):
        """Get all schedules for a center on a specific day"""
        print(f"Getting schedules for center {center_id} on day {day_of_week}")
        return list(self.db.schedules.find({
            'center_id': ObjectId(center_id),
            'day_of_week': int(day_of_week)
        }))
    
    def get_time_slot(self, time_slot_id):
        """Get time slot details"""
        return self.db.time_slots.find_one({'_id': ObjectId(time_slot_id)})
    
    def get_activity(self, activity_id):
        """Get activity details"""
        return self.db.activities.find_one({'_id': ObjectId(activity_id)})
    
    def get_students_from_schedule(self, schedule_item, org_id):
        """Get students assigned to a schedule item"""
        student_ids = []
        group_ids = []
        
        # Convert org_id to ObjectId if it's a string
        org_id_obj = ObjectId(org_id) if isinstance(org_id, str) else org_id
        
        # Get directly assigned students from schedule
        if schedule_item.get('assigned_students'):
            for student_id in schedule_item['assigned_students']:
                print(f"Student ID: {student_id}")
                # Convert student_id to ObjectId if it's a string
                student_id_obj = ObjectId(student_id) if isinstance(student_id, str) else student_id
                # Verify student exists and belongs to organization
                student = self.db.users.find_one({
                    '_id': student_id_obj,
                })
                if student:
                    student_ids.append(student_id_obj)
                    print(f"    Added student: {student.get('name', 'Unknown')} ({student_id})")
        
        # Get students from groups if schedule has assigned groups
        if schedule_item.get('assigned_groups'):
            for group_id in schedule_item['assigned_groups']:
                # Convert group_id to ObjectId if it's a string
                group_id_obj = ObjectId(group_id) if isinstance(group_id, str) else group_id
                # Verify group exists and belongs to organization
                group = self.db.groups.find_one({
                    '_id': group_id_obj,
                    'organization_id': org_id_obj,
                    'is_active': True
                })
                if group:
                    group_ids.append(group_id_obj)
                    
                    # Also get individual students from this group for logging
                    group_students = list(self.db.users.find({
                        'groups': {'$in': [group_id_obj]},
                        'organization_id': org_id_obj,
                        'role': 'student',
                        'is_active': True
                    }))
                    print(f"    Added group: {group.get('name', 'Unknown')} with {len(group_students)} students")
        
        return student_ids, group_ids
    
    def class_already_exists(self, center_id, scheduled_at, activity_id):
        """Check if a class already exists for the given parameters"""
        # Check for existing class within 1 hour window to avoid duplicates
        
        existing = self.db.classes.find_one({
            'location.center_id': center_id,
            'scheduled_at': scheduled_at,
            'status': {'$in': ['scheduled', 'ongoing']}
        })
        
        return existing is not None

    def update_class_from_schedule(self, schedule_item_id, coach_id=None, student_ids=None, group_ids=None, activity_id=None, max_participants=None, notes=None):
        """Update future classes from a schedule item"""
        try:
            # Convert IDs to ObjectId
            schedule_item_id = ObjectId(schedule_item_id)
            update_fields = {
                'updated_at': datetime.utcnow()
            }

            # Handle coach update
            if coach_id is not None:
                update_fields['coach_id'] = ObjectId(coach_id) if coach_id else None

            # Handle student assignments
            if student_ids is not None:
                update_fields['student_ids'] = [ObjectId(sid) for sid in student_ids if sid]

            # Handle group assignments
            if group_ids is not None:
                update_fields['group_ids'] = [ObjectId(gid) for gid in group_ids if gid]

            # Handle max participants
            if max_participants is not None:
                update_fields['max_students'] = max_participants

            # Handle notes
            if notes is not None:
                update_fields['notes'] = notes

            # Handle activity change
            if activity_id is not None:
                activity = self.get_activity(activity_id)
                if activity:
                    # Update sport and title
                    center = self.db.centers.find_one({
                        '_id': {'$in': self.db.classes.distinct('location.center_id', {
                            'schedule_item_id': schedule_item_id
                        })}
                    })
                    if center:
                        update_fields['sport'] = activity.get('sport_type', activity.get('name'))
                        update_fields['title'] = f"{activity.get('name', 'Training Session')} - {center.get('name', 'Training Center')}"

            # Update all future classes for this schedule item
            result = self.db.classes.update_many(
                {
                    'schedule_item_id': schedule_item_id,
                    'scheduled_at': {'$gte': datetime.utcnow()},  # Only future classes
                    'status': {'$in': ['scheduled', 'ongoing']}  # Only active classes
                },
                {'$set': update_fields}
            )
            
            return result.modified_count
        except Exception as e:
            print(f"Error updating classes from schedule: {str(e)}")
            return 0
    
    def create_class_from_schedule(self, org_id, center, schedule_item, target_date):
        """Create a class from a schedule item for a specific date"""
        try:
            # Get time slot details
            time_slot = self.get_time_slot(schedule_item['time_slot_id'])
            if not time_slot:
                print(f"Warning: Time slot {schedule_item['time_slot_id']} not found")
                return None
            
            # Get activity details
            activity = None
            activity_name = "Training Session"
            sport = None
            
            if schedule_item.get('activity_id'):
                activity = self.get_activity(schedule_item['activity_id'])
                if activity:
                    activity_name = activity.get('name', 'Training Session')
                    sport = activity.get('sport_type', activity.get('name'))
            
            # Parse start time and create scheduled datetime
            start_time = time_slot.get('start_time', '')
            if isinstance(start_time, str):
                # Parse time string (format: "HH:MM")
                hour, minute = map(int, start_time.split(':'))
            else:
                # If it's already a time object
                hour, minute = start_time.hour, start_time.minute
            
            ist = timezone(timedelta(hours=5, minutes=30))

            scheduled_at = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute, tzinfo=ist))
            print('scheduled_at', scheduled_at)
            
            # Check if class already exists
            if self.class_already_exists(center['_id'], scheduled_at, schedule_item.get('activity_id')):
                print(f"Class already exists for {center['name']} at {scheduled_at}")
                return None
            
            # Get duration from time slot or default to 60 minutes
            duration_minutes = time_slot.get('duration_minutes', 60)
            if isinstance(duration_minutes, str):
                try:
                    duration_minutes = int(duration_minutes)
                except ValueError:
                    duration_minutes = 60
            
            # Create class title
            center_name = center.get('name', 'Training Center')
            title = f"{activity_name}"
            
            # Create location object
            location = {
                'center_id': center['_id'],
                'name': center_name,
                'address': center.get('address', {})
            }
            
            # Get coach ID (prefer from schedule, fallback to first center coach)
            coach_id = schedule_item.get('coach_id')
            if not coach_id and center.get('coaches'):
                coach_id = center['coaches'][0]  # Use first available coach
            
            # Get students and groups from schedule
            student_ids, group_ids = self.get_students_from_schedule(schedule_item, org_id)
            
            # Log student assignment info
            total_assigned = len(student_ids) + len(group_ids)
            if total_assigned > 0:
                print(f"    Assigning {len(student_ids)} direct students and {len(group_ids)} groups to class")
            else:
                print(f"    No students assigned to this schedule - creating empty class")
            
            # Create the class
            new_class = Class(
                title=title,
                organization_id=ObjectId(org_id),
                coach_id=ObjectId(coach_id) if coach_id else None,
                scheduled_at=scheduled_at,
                duration_minutes=duration_minutes,
                location=location,
                group_ids=group_ids,
                student_ids=student_ids,
                sport=sport,
                schedule_item_id=ObjectId(schedule_item['_id']),
                notes=f"Auto-generated from schedule on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                price=activity.get('price', 0)
            )

            print(new_class.to_dict())
            class_with_object_id = new_class.to_dict()
            class_with_object_id['organization_id'] = ObjectId(class_with_object_id['organization_id'])
            class_with_object_id['coach_id'] = ObjectId(class_with_object_id['coach_id'])
            class_with_object_id['group_ids'] = [ObjectId(gid) for gid in class_with_object_id['group_ids']]
            class_with_object_id['student_ids'] = [ObjectId(sid) for sid in class_with_object_id['student_ids']]
            if class_with_object_id.get('schedule_item_id'):
                class_with_object_id['schedule_item_id'] = ObjectId(class_with_object_id['schedule_item_id'])
            # Insert into database
            result = self.db.classes.insert_one(class_with_object_id)
            print(result)
            print('Price:',activity.get('price', 0))
            print(f"✅ Created class: {title} at {scheduled_at}")
            if total_assigned > 0:
                print(f"    📚 Class has {len(student_ids)} direct students and {len(group_ids)} groups assigned")
            return result.inserted_id
            
        except Exception as e:
            print(f"❌ Error creating class for {center.get('name', 'Unknown Center')}: {str(e)}")
            return None
    
    def create_classes_for_date(self, target_date, org_id=None):
        """Create all classes for a specific date"""
        day_of_week = self.get_day_of_week(target_date)
        created_classes = []
        
        print(f"\n🔄 Creating classes for {target_date.strftime('%A, %B %d, %Y')} ({day_of_week})")
        
        # Get organizations to process
        organizations = self.get_active_organizations(org_id)
        
        if not organizations:
            print("No active organizations found")
            return created_classes
        
        for org in organizations:
            org_id = org['_id']
            org_name = org.get('name', 'Unknown Organization')
            
            print(f"\n📋 Processing organization: {org_name}")
            
            # Get centers for this organization
            centers = self.get_organization_centers(org_id)
            
            if not centers:
                print(f"  No active centers found for {org_name}")
                continue
            
            for center in centers:
                center_id = center['_id']
                center_name = center.get('name', 'Unknown Center')
                
                print(f"  🏢 Processing center: {center_name} for center id: {center_id} and day of week: {day_of_week}")
                
                # Get schedules for this center and day
                schedules = self.get_center_schedules(center_id, day_of_week)
                
                if not schedules:
                    print(f"    No schedules found for {center_name} on {day_of_week}")
                    continue
                
                print(f"    Found {len(schedules)} schedule(s) for {day_of_week}")
                
                # Create classes for each schedule item
                for schedule_item in schedules:
                    class_id = self.create_class_from_schedule(org_id, center, schedule_item, target_date)
                    if class_id:
                        created_classes.append(class_id)
        
        return created_classes
    
    def create_classes_for_range(self, start_date, days_ahead=7, org_id=None):
        """Create classes for a range of days"""
        all_created_classes = []
        
        print(f"🚀 Starting class creation for {days_ahead} days ahead")
        print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {(start_date + timedelta(days=days_ahead-1)).strftime('%Y-%m-%d')}")
        
        for day_offset in range(days_ahead):
            target_date = start_date + timedelta(days=day_offset)
            created_classes = self.create_classes_for_date(target_date, org_id)
            all_created_classes.extend(created_classes)
        
        return all_created_classes
    
    def cleanup_old_classes(self, days_old=30):
        """Clean up old completed or cancelled classes"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = self.db.classes.delete_many({
            'status': {'$in': ['completed', 'cancelled']},
            'scheduled_at': {'$lt': cutoff_date}
        })
        
        if result.deleted_count > 0:
            print(f"🧹 Cleaned up {result.deleted_count} old classes")
        
        return result.deleted_count
    
    def get_statistics(self):
        """Get creation statistics"""
        total_orgs = self.db.organizations.count_documents({'is_active': True})
        total_centers = self.db.centers.count_documents({'is_active': True})
        total_schedules = self.db.schedules.count_documents({})
        total_students = self.db.users.count_documents({'role': 'student', 'is_active': True})
        total_groups = self.db.groups.count_documents({'is_active': True})
        
        # Classes in next 7 days
        next_week = datetime.utcnow() + timedelta(days=7)
        upcoming_classes = self.db.classes.count_documents({
            'scheduled_at': {'$gte': datetime.utcnow(), '$lte': next_week},
            'status': 'scheduled'
        })
        
        # Classes with students assigned
        classes_with_students = self.db.classes.count_documents({
            'scheduled_at': {'$gte': datetime.utcnow(), '$lte': next_week},
            'status': 'scheduled',
            '$or': [
                {'student_ids': {'$exists': True, '$ne': []}},
                {'group_ids': {'$exists': True, '$ne': []}}
            ]
        })
        
        return {
            'organizations': total_orgs,
            'centers': total_centers,
            'schedules': total_schedules,
            'students': total_students,
            'groups': total_groups,
            'upcoming_classes': upcoming_classes,
            'classes_with_students': classes_with_students
        }
    
    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()


def main():
    """Main function to run the class creator"""
    parser = argparse.ArgumentParser(description='Create daily classes from center schedules')
    parser.add_argument('--date', type=str, help='Specific date to create classes for (YYYY-MM-DD)')
    parser.add_argument('--org-id', type=str, help='Create classes only for specific organization ID')
    parser.add_argument('--days-ahead', type=int, default=7, help='Number of days ahead to create classes (default: 7)')
    parser.add_argument('--cleanup-days', type=int, default=30, help='Clean up classes older than N days (default: 30)')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    creator = None
    try:
        creator = DailyClassCreator()
        
        if args.stats:
            stats = creator.get_statistics()
            print("\n📊 System Statistics:")
            print(f"   Active Organizations: {stats['organizations']}")
            print(f"   Active Centers: {stats['centers']}")
            print(f"   Total Schedules: {stats['schedules']}")
            print(f"   Active Students: {stats['students']}")
            print(f"   Active Groups: {stats['groups']}")
            print(f"   Upcoming Classes (7 days): {stats['upcoming_classes']}")
            print(f"   Classes with students assigned: {stats['classes_with_students']}")
            return
        
        # Determine start date
        if args.date:
            try:
                start_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Error: Invalid date format. Use YYYY-MM-DD")
                return
        else:
            # Default to tomorrow
            start_date = (datetime.utcnow() + timedelta(days=1)).date()
        
        print(f"🏃‍♂️ botle Daily Class Creator")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show initial statistics
        stats = creator.get_statistics()
        print(f"\n📊 Current System State:")
        print(f"   Active Organizations: {stats['organizations']}")
        print(f"   Active Centers: {stats['centers']}")
        print(f"   Total Schedules: {stats['schedules']}")
        print(f"   Active Students: {stats['students']}")
        print(f"   Active Groups: {stats['groups']}")
        
        # Create classes
        created_classes = creator.create_classes_for_range(
            start_date=start_date,
            days_ahead=args.days_ahead,
            org_id=args.org_id
        )
        
        # Cleanup old classes
        if args.cleanup_days > 0:
            print(f"\n🧹 Cleaning up classes older than {args.cleanup_days} days...")
            cleaned_count = creator.cleanup_old_classes(args.cleanup_days)
        
        # Final summary
        print(f"\n✅ Class Creation Complete!")
        print(f"📈 Summary:")
        print(f"   Total classes created: {len(created_classes)}")
        if args.cleanup_days > 0:
            print(f"   Old classes cleaned up: {cleaned_count}")
        
        # Show updated statistics
        new_stats = creator.get_statistics()
        print(f"   Upcoming classes (7 days): {new_stats['upcoming_classes']}")
        print(f"   Classes with students assigned: {new_stats['classes_with_students']}")
        
        print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if creator:
            creator.close()
    
    return 0


if __name__ == '__main__':
    exit(main())
