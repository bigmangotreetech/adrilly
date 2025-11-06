from datetime import datetime, timedelta
from flask import current_app
from bson import ObjectId
from app.extensions import mongo
from app.models.class_schedule import Class
from app.models.user import User
from app.models.holiday import Holiday
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from typing import Tuple, List, Dict, Any, Optional

class CancellationService:
    """Service for handling class cancellations and notifications"""
    
    @staticmethod
    def cancel_class(
        class_id: str, 
        reason: str, 
        cancelled_by: str, 
        cancellation_type: str = 'manual',
        refund_required: bool = False,
        send_notifications: bool = True,
        replacement_class_id: str = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Cancel a class with proper workflow
        
        Args:
            class_id: ID of the class to cancel
            reason: Reason for cancellation
            cancelled_by: User ID who is cancelling
            cancellation_type: Type of cancellation (manual, weather, facility, holiday, emergency)
            refund_required: Whether refund is needed
            send_notifications: Whether to send notifications to students
            replacement_class_id: Optional ID of replacement class
            
        Returns:
            Tuple of (success, message, class_data)
        """
        try:
            # Get the class
            class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_data:
                return False, "Class not found", None
            
            class_obj = Class.from_dict(class_data)
            
            # Check if class can be cancelled
            if not class_obj.can_be_cancelled():
                return False, f"Class cannot be cancelled (status: {class_obj.status})", None
            
            # Get the user cancelling
            user_data = mongo.db.users.find_one({'_id': ObjectId(cancelled_by)})
            if not user_data:
                return False, "User not found", None
            
            user = User.from_dict(user_data)
            
            # Check permissions
            if not CancellationService._can_user_cancel_class(user, class_obj):
                return False, "Insufficient permissions to cancel this class", None
            
            # Cancel the class
            class_obj.cancel_class(reason, cancelled_by, cancellation_type, refund_required)
            
            # Set replacement class if provided
            if replacement_class_id:
                class_obj.replacement_class_id = ObjectId(replacement_class_id)
            
            # Update in database
            update_data = {
                'status': class_obj.status,
                'cancellation_reason': class_obj.cancellation_reason,
                'cancelled_by': class_obj.cancelled_by,
                'cancelled_at': class_obj.cancelled_at,
                'cancellation_type': class_obj.cancellation_type,
                'refund_required': class_obj.refund_required,
                'updated_at': class_obj.updated_at
            }
            
            if replacement_class_id:
                update_data['replacement_class_id'] = class_obj.replacement_class_id
            
            mongo.db.classes.update_one(
                {'_id': ObjectId(class_id)},
                {'$set': update_data}
            )
            
            # Send notifications if requested
            if send_notifications:
                notification_success = CancellationService._send_cancellation_notifications(
                    class_obj, user, replacement_class_id
                )
                
                if notification_success:
                    mongo.db.classes.update_one(
                        {'_id': ObjectId(class_id)},
                        {'$set': {'notification_sent': True}}
                    )
            
            # Update attendance records to cancelled
            mongo.db.attendance.update_many(
                {'class_id': ObjectId(class_id)},
                {'$set': {
                    'status': 'class_cancelled',
                    'updated_at': datetime.utcnow()
                }}
            )
            
            current_app.logger.info(f"Class {class_id} cancelled by {user.name} ({cancelled_by}): {reason}")
            
            return True, "Class cancelled successfully", class_obj.to_dict()
            
        except Exception as e:
            current_app.logger.error(f"Error cancelling class: {str(e)}")
            return False, "Error cancelling class", None
    
    @staticmethod
    def bulk_cancel_classes(
        class_ids: List[str],
        reason: str,
        cancelled_by: str,
        cancellation_type: str = 'bulk',
        refund_required: bool = False,
        send_notifications: bool = True
    ) -> Tuple[bool, str, Dict]:
        """
        Cancel multiple classes at once
        
        Args:
            class_ids: List of class IDs to cancel
            reason: Reason for cancellation
            cancelled_by: User ID who is cancelling
            cancellation_type: Type of cancellation
            refund_required: Whether refunds are needed
            send_notifications: Whether to send notifications
            
        Returns:
            Tuple of (success, message, results_dict)
        """
        try:
            results = {
                'successful': [],
                'failed': [],
                'total': len(class_ids)
            }
            
            for class_id in class_ids:
                success, message, class_data = CancellationService.cancel_class(
                    class_id=class_id,
                    reason=reason,
                    cancelled_by=cancelled_by,
                    cancellation_type=cancellation_type,
                    refund_required=refund_required,
                    send_notifications=send_notifications
                )
                
                if success:
                    results['successful'].append({
                        'class_id': class_id,
                        'class_title': class_data.get('title') if class_data else 'Unknown'
                    })
                else:
                    results['failed'].append({
                        'class_id': class_id,
                        'error': message
                    })
            
            success_count = len(results['successful'])
            fail_count = len(results['failed'])
            
            if success_count == len(class_ids):
                return True, f"All {success_count} classes cancelled successfully", results
            elif success_count > 0:
                return True, f"{success_count} classes cancelled, {fail_count} failed", results
            else:
                return False, f"Failed to cancel all {fail_count} classes", results
                
        except Exception as e:
            current_app.logger.error(f"Error in bulk cancellation: {str(e)}")
            return False, "Error in bulk cancellation", {'successful': [], 'failed': [], 'total': 0}
    
    @staticmethod
    def cancel_classes_for_holiday(
        organization_id: str,
        holiday_date: datetime,
        cancelled_by: str,
        send_notifications: bool = True
    ) -> Tuple[bool, str, Dict]:
        """
        Cancel all classes on a holiday
        
        Args:
            organization_id: Organization ID
            holiday_date: Date of the holiday
            cancelled_by: User ID cancelling the classes
            send_notifications: Whether to send notifications
            
        Returns:
            Tuple of (success, message, results_dict)
        """
        try:
            # Find all classes on the holiday date
            start_of_day = holiday_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = holiday_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            classes_cursor = mongo.db.classes.find({
                'organization_id': ObjectId(organization_id),
                'scheduled_at': {
                    '$gte': start_of_day,
                    '$lte': end_of_day
                },
                'status': {'$in': ['scheduled', 'ongoing']}
            })
            
            class_ids = [str(class_data['_id']) for class_data in classes_cursor]
            
            if not class_ids:
                return True, "No classes found on this holiday", {'successful': [], 'failed': [], 'total': 0}
            
            # Get holiday name for the reason
            holiday_name = holiday_date.strftime('%B %d, %Y')
            reason = f"Holiday closure - {holiday_name}"
            
            return CancellationService.bulk_cancel_classes(
                class_ids=class_ids,
                reason=reason,
                cancelled_by=cancelled_by,
                cancellation_type='holiday',
                refund_required=False,  # Usually no refund for holidays
                send_notifications=send_notifications
            )
            
        except Exception as e:
            current_app.logger.error(f"Error cancelling classes for holiday: {str(e)}")
            return False, "Error cancelling classes for holiday", {'successful': [], 'failed': [], 'total': 0}
    
    @staticmethod
    def get_cancellation_stats(organization_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get cancellation statistics for an organization"""
        try:
            pipeline = [
                {
                    '$match': {
                        'organization_id': ObjectId(organization_id),
                        'status': 'cancelled',
                        'cancelled_at': {
                            '$gte': start_date,
                            '$lte': end_date
                        }
                    }
                },
                {
                    '$group': {
                        '_id': '$cancellation_type',
                        'count': {'$sum': 1},
                        'refunds_required': {
                            '$sum': {'$cond': ['$refund_required', 1, 0]}
                        }
                    }
                }
            ]
            
            results = list(mongo.db.classes.aggregate(pipeline))
            
            stats = {
                'total_cancelled': sum(r['count'] for r in results),
                'by_type': {r['_id']: r for r in results},
                'total_refunds_required': sum(r.get('refunds_required', 0) for r in results),
                'period': {
                    'start': start_date,
                    'end': end_date
                }
            }
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting cancellation stats: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _can_user_cancel_class(user: User, class_obj: Class) -> bool:
        """Check if user has permission to cancel the class"""
        # Super admin can cancel any class
        if user.role == 'super_admin':
            return True
        
        # Must be in same organization
        if str(user.organization_id) != str(class_obj.organization_id):
            return False
        
        # Org admin can cancel any class in their org
        if user.role == 'org_admin':
            return True
        
        # Center admin can cancel classes
        if user.role == 'center_admin':
            return True
        
        # Coach can cancel their own classes
        if user.role == 'coach' and str(user._id) == str(class_obj.coach_id):
            return True
        
        return False
    
    @staticmethod
    def _send_cancellation_notifications(
        class_obj: Class, 
        cancelled_by_user: User, 
        replacement_class_id: str = None
    ) -> bool:
        """Send WhatsApp notifications about class cancellation"""
        try:
            whatsapp_service = EnhancedWhatsAppService()
            
            # Get all students for this class
            student_ids = class_obj.get_all_student_ids()
            
            # Get group members if any groups are assigned
            if class_obj.group_ids:
                group_students = mongo.db.users.find({
                    'groups': {'$in': [str(gid) for gid in class_obj.group_ids]},
                    'role': 'student',
                    'is_active': True
                })
                for student in group_students:
                    if ObjectId(student['_id']) not in student_ids:
                        student_ids.append(ObjectId(student['_id']))
            
            # Get replacement class info if available
            replacement_info = None
            if replacement_class_id:
                replacement_data = mongo.db.classes.find_one({'_id': ObjectId(replacement_class_id)})
                if replacement_data:
                    replacement_class = Class.from_dict(replacement_data)
                    replacement_info = {
                        'title': replacement_class.title,
                        'scheduled_at': replacement_class.scheduled_at,
                        'location': replacement_class.location
                    }
            
            # Get location string
            location_str = class_obj.location.get('name', 'TBD') if class_obj.location else 'TBD'
            
            notification_count = 0
            
            # Send notifications to each student
            for student_id in student_ids:
                student_data = mongo.db.users.find_one({'_id': student_id})
                if student_data and student_data.get('phone_number'):
                    student = User.from_dict(student_data)
                    
                    success, _ = whatsapp_service.send_class_cancellation_notification(
                        phone_number=student.phone_number,
                        student_name=student.name,
                        class_title=class_obj.title,
                        scheduled_at=class_obj.scheduled_at,
                        location=location_str,
                        cancellation_reason=class_obj.cancellation_reason,
                        cancelled_by=cancelled_by_user.name,
                        replacement_info=replacement_info
                    )
                    
                    if success:
                        notification_count += 1
            
            current_app.logger.info(f"Sent {notification_count} cancellation notifications for class {class_obj._id}")
            return notification_count > 0
            
        except Exception as e:
            current_app.logger.error(f"Error sending cancellation notifications: {str(e)}")
            return False
    
    @staticmethod
    def _create_cancellation_message(
        student_name: str, 
        class_obj: Class, 
        cancelled_by: str, 
        replacement_info: Dict = None
    ) -> str:
        """Create cancellation notification message"""
        date_str = class_obj.scheduled_at.strftime('%B %d, %Y')
        time_str = class_obj.scheduled_at.strftime('%I:%M %p')
        location_str = class_obj.location.get('name', 'TBD') if class_obj.location else 'TBD'
        
        # Check if it's short notice
        is_short_notice = class_obj.requires_short_notice_alert(24)
        
        message = f"""
🚫 *Class Cancelled*

Hi {student_name},

{"⚠️ SHORT NOTICE: " if is_short_notice else ""}Your {class_obj.title} class has been cancelled.

📅 *Date:* {date_str}
⏰ *Time:* {time_str}
📍 *Location:* {location_str}

*Reason:* {class_obj.cancellation_reason}
*Cancelled by:* {cancelled_by}
        """.strip()
        
        if replacement_info:
            repl_date = replacement_info['scheduled_at'].strftime('%B %d, %Y')
            repl_time = replacement_info['scheduled_at'].strftime('%I:%M %p')
            repl_location = replacement_info['location'].get('name', 'TBD') if replacement_info['location'] else 'TBD'
            
            message += f"""

🔄 *Replacement Class Scheduled:*
📅 *New Date:* {repl_date}
⏰ *New Time:* {repl_time}
📍 *Location:* {repl_location}
            """
        elif class_obj.refund_required:
            message += "\n\n💰 *Refund will be processed within 3-5 business days.*"
        
        message += "\n\nFor any questions, please contact your coach or the admin office."
        
        return message
