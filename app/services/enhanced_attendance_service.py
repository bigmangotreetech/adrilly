from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from app.extensions import mongo
from app.models.attendance import Attendance, AttendanceSummary
from app.models.class_schedule import Class
from app.models.user import User
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from bson import ObjectId
from flask import current_app
import statistics

class EnhancedAttendanceService:
    """Enhanced attendance service with comprehensive tracking and analytics"""
    
    def __init__(self):
        self.whatsapp_service = EnhancedWhatsAppService()
    
    def create_attendance_records_for_class(self, class_id: str) -> Tuple[bool, str, int]:
        """Create attendance records for all students in a class"""
        try:
            # Get class details
            class_data = mongo.db.classes.find_one({'_id': ObjectId(class_id)})
            if not class_data:
                return False, "Class not found", 0
            
            class_obj = Class.from_dict(class_data)
            
            # Get all enrolled students
            enrolled_students = []
            
            # Direct enrollments
            if class_obj.student_ids:
                direct_students = list(mongo.db.users.find({
                    '_id': {'$in': class_obj.student_ids},
                    'is_active': True
                }))
                enrolled_students.extend(direct_students)
            
            # Group enrollments
            if class_obj.group_ids:
                group_students = list(mongo.db.users.find({
                    'groups': {'$in': [str(gid) for gid in class_obj.group_ids]},
                    'is_active': True
                }))
                enrolled_students.extend(group_students)
            
            # Remove duplicates
            unique_students = {str(s['_id']): s for s in enrolled_students}.values()
            
            created_count = 0
            for student_data in unique_students:
                # Check if attendance record already exists
                existing = mongo.db.attendance.find_one({
                    'class_id': ObjectId(class_id),
                    'student_id': ObjectId(student_data['_id'])
                })
                
                if not existing:
                    attendance = Attendance(
                        class_id=class_id,
                        student_id=str(student_data['_id']),
                        status='pending'
                    )
                    
                    # Set class size for analytics
                    attendance.class_size_that_day = len(unique_students)
                    
                    result = mongo.db.attendance.insert_one(attendance.to_dict())
                    created_count += 1
            
            return True, f"Created {created_count} attendance records", created_count
            
        except Exception as e:
            current_app.logger.error(f"Error creating attendance records: {str(e)}")
            return False, str(e), 0
    
    def auto_mark_attendance_from_rsvp(self, class_id: str) -> Tuple[bool, str, Dict]:
        """Auto-mark attendance based on WhatsApp RSVP responses"""
        try:
            # Get all attendance records for the class with RSVP responses
            attendance_records = list(mongo.db.attendance.find({
                'class_id': ObjectId(class_id),
                'rsvp_response': {'$exists': True, '$ne': None}
            }))
            
            results = {
                'total_rsvp_responses': len(attendance_records),
                'auto_marked_present': 0,
                'auto_marked_absent': 0,
                'pending': 0
            }
            
            for record_data in attendance_records:
                attendance = Attendance.from_dict(record_data)
                
                if attendance.rsvp_response == 'yes' and attendance.status == 'pending':
                    attendance.status = 'present'
                    attendance.auto_marked = True
                    attendance.verification_method = 'whatsapp_rsvp'
                    results['auto_marked_present'] += 1
                elif attendance.rsvp_response == 'no' and attendance.status == 'pending':
                    attendance.status = 'absent'
                    attendance.auto_marked = True
                    attendance.verification_method = 'whatsapp_rsvp'
                    results['auto_marked_absent'] += 1
                else:
                    results['pending'] += 1
                    continue
                
                # Update in database
                mongo.db.attendance.update_one(
                    {'_id': attendance._id},
                    {'$set': attendance.to_dict()}
                )
            
            return True, f"Auto-marked {results['auto_marked_present']} present, {results['auto_marked_absent']} absent", results
            
        except Exception as e:
            current_app.logger.error(f"Error auto-marking attendance: {str(e)}")
            return False, str(e), {}
    
    def bulk_update_attendance(self, attendance_updates: List[Dict], updated_by: str) -> Tuple[bool, str, Dict]:
        """Bulk update attendance records"""
        try:
            results = {
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            for update in attendance_updates:
                try:
                    attendance_id = update.get('attendance_id')
                    new_status = update.get('status')
                    
                    attendance_data = mongo.db.attendance.find_one({'_id': ObjectId(attendance_id)})
                    if not attendance_data:
                        results['failed'] += 1
                        results['errors'].append(f"Attendance {attendance_id} not found")
                        continue
                    
                    attendance = Attendance.from_dict(attendance_data)
                    
                    # Update basic status
                    attendance.status = new_status
                    attendance.marked_by = ObjectId(updated_by)
                    attendance.updated_at = datetime.utcnow()
                    
                    # Update additional fields if provided
                    if 'check_in_time' in update:
                        attendance.check_in_time = update['check_in_time']
                    if 'participation_score' in update:
                        attendance.participation_score = update['participation_score']
                    if 'behavior_notes' in update:
                        attendance.behavior_notes = update['behavior_notes']
                    if 'equipment_brought' in update:
                        attendance.equipment_brought = update['equipment_brought']
                    if 'dress_code_compliant' in update:
                        attendance.dress_code_compliant = update['dress_code_compliant']
                    if 'homework_completed' in update:
                        attendance.homework_completed = update['homework_completed']
                    if 'notes' in update:
                        attendance.notes = update['notes']
                    
                    # Save to database
                    mongo.db.attendance.update_one(
                        {'_id': attendance._id},
                        {'$set': attendance.to_dict()}
                    )
                    
                    results['successful'] += 1
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error updating {attendance_id}: {str(e)}")
            
            return True, f"Updated {results['successful']} records successfully", results
            
        except Exception as e:
            current_app.logger.error(f"Error bulk updating attendance: {str(e)}")
            return False, str(e), {}
    
    def generate_attendance_analytics(self, organization_id: str, period_days: int = 30) -> Dict:
        """Generate comprehensive attendance analytics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=period_days)
            
            # Overall attendance statistics
            overall_stats = self._get_overall_attendance_stats(organization_id, start_date)
            
            # Attendance trends
            attendance_trends = self._get_attendance_trends(organization_id, start_date)
            
            # Student performance analysis
            student_performance = self._get_student_performance_analysis(organization_id, start_date)
            
            # Class-wise analysis
            class_analysis = self._get_class_wise_analysis(organization_id, start_date)
            
            # At-risk students
            at_risk_students = self._identify_at_risk_students(organization_id, start_date)
            
            # RSVP effectiveness
            rsvp_effectiveness = self._analyze_rsvp_effectiveness(organization_id, start_date)
            
            return {
                'period_days': period_days,
                'overall_stats': overall_stats,
                'attendance_trends': attendance_trends,
                'student_performance': student_performance,
                'class_analysis': class_analysis,
                'at_risk_students': at_risk_students,
                'rsvp_effectiveness': rsvp_effectiveness,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating attendance analytics: {str(e)}")
            return {'error': str(e)}
    
    def generate_student_attendance_report(self, student_id: str, period_days: int = 30) -> Dict:
        """Generate detailed attendance report for a specific student"""
        try:
            start_date = datetime.utcnow() - timedelta(days=period_days)
            
            # Get student details
            student_data = mongo.db.users.find_one({'_id': ObjectId(student_id)})
            if not student_data:
                return {'error': 'Student not found'}
            
            student = User.from_dict(student_data)
            
            # Get attendance records
            attendance_records = list(mongo.db.attendance.find({
                'student_id': ObjectId(student_id),
                'created_at': {'$gte': start_date}
            }).sort('created_at', -1))
            
            # Calculate statistics
            total_classes = len(attendance_records)
            present_count = sum(1 for r in attendance_records if r.get('status') == 'present')
            absent_count = sum(1 for r in attendance_records if r.get('status') == 'absent')
            late_count = sum(1 for r in attendance_records if r.get('status') == 'late')
            
            attendance_rate = (present_count / total_classes * 100) if total_classes > 0 else 0
            
            # Participation scores
            participation_scores = [r.get('participation_score') for r in attendance_records 
                                  if r.get('participation_score') is not None]
            avg_participation = statistics.mean(participation_scores) if participation_scores else None
            
            # Equipment and preparation tracking
            equipment_records = [r for r in attendance_records if r.get('equipment_brought') is not None]
            equipment_compliance = (sum(1 for r in equipment_records if r.get('equipment_brought')) / 
                                  len(equipment_records) * 100) if equipment_records else None
            
            # Recent trends
            recent_records = attendance_records[:5]  # Last 5 classes
            recent_attendance_rate = (sum(1 for r in recent_records if r.get('status') == 'present') / 
                                    len(recent_records) * 100) if recent_records else 0
            
            # RSVP analysis
            rsvp_records = [r for r in attendance_records if r.get('rsvp_response') is not None]
            rsvp_accuracy = self._calculate_rsvp_accuracy(rsvp_records) if rsvp_records else None
            
            return {
                'student': {
                    'id': str(student._id),
                    'name': student.name,
                    'phone_number': student.phone_number
                },
                'period_days': period_days,
                'summary': {
                    'total_classes': total_classes,
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'late_count': late_count,
                    'attendance_rate': round(attendance_rate, 2),
                    'recent_attendance_rate': round(recent_attendance_rate, 2)
                },
                'performance': {
                    'average_participation_score': round(avg_participation, 2) if avg_participation else None,
                    'equipment_compliance_rate': round(equipment_compliance, 2) if equipment_compliance else None
                },
                'rsvp_analysis': {
                    'total_rsvp_responses': len(rsvp_records),
                    'rsvp_accuracy': round(rsvp_accuracy, 2) if rsvp_accuracy else None
                },
                'recent_records': [
                    {
                        'date': r.get('created_at'),
                        'status': r.get('status'),
                        'participation_score': r.get('participation_score'),
                        'rsvp_response': r.get('rsvp_response')
                    }
                    for r in recent_records
                ],
                'is_at_risk': self._is_student_at_risk(attendance_records),
                'recommendations': self._generate_student_recommendations(attendance_records)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating student attendance report: {str(e)}")
            return {'error': str(e)}
    
    def send_attendance_follow_ups(self, class_id: str) -> Tuple[bool, str, Dict]:
        """Send follow-up messages for attendance issues"""
        try:
            # Get attendance records that need follow-up
            follow_up_records = list(mongo.db.attendance.find({
                'class_id': ObjectId(class_id),
                'follow_up_required': True
            }))
            
            results = {
                'total_follow_ups': len(follow_up_records),
                'messages_sent': 0,
                'failed': 0
            }
            
            for record_data in follow_up_records:
                attendance = Attendance.from_dict(record_data)
                
                # Get student details
                student_data = mongo.db.users.find_one({'_id': attendance.student_id})
                if not student_data or not student_data.get('phone_number'):
                    results['failed'] += 1
                    continue
                
                student = User.from_dict(student_data)
                
                # Create follow-up message
                follow_up_message = self._create_follow_up_message(attendance, student)
                
                # Send message
                success, message_id = self.whatsapp_service.send_twilio_message(
                    to_number=student.phone_number,
                    message=follow_up_message,
                    message_type='attendance_follow_up'
                )
                
                if success:
                    results['messages_sent'] += 1
                    # Mark follow-up as sent
                    mongo.db.attendance.update_one(
                        {'_id': attendance._id},
                        {'$set': {'follow_up_required': False, 'updated_at': datetime.utcnow()}}
                    )
                else:
                    results['failed'] += 1
            
            return True, f"Sent {results['messages_sent']} follow-up messages", results
            
        except Exception as e:
            current_app.logger.error(f"Error sending attendance follow-ups: {str(e)}")
            return False, str(e), {}
    
    def _get_overall_attendance_stats(self, organization_id: str, start_date: datetime) -> Dict:
        """Get overall attendance statistics"""
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$status',
                    'count': {'$sum': 1}
                }
            }
        ]
        
        results = list(mongo.db.attendance.aggregate(pipeline))
        return {result['_id']: result['count'] for result in results}
    
    def _get_attendance_trends(self, organization_id: str, start_date: datetime) -> List[Dict]:
        """Get attendance trends over time"""
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': {
                        'year': {'$year': '$created_at'},
                        'month': {'$month': '$created_at'},
                        'day': {'$dayOfMonth': '$created_at'}
                    },
                    'total': {'$sum': 1},
                    'present': {'$sum': {'$cond': [{'$eq': ['$status', 'present']}, 1, 0]}},
                    'absent': {'$sum': {'$cond': [{'$eq': ['$status', 'absent']}, 1, 0]}},
                    'late': {'$sum': {'$cond': [{'$eq': ['$status', 'late']}, 1, 0]}}
                }
            },
            {'$sort': {'_id.year': 1, '_id.month': 1, '_id.day': 1}}
        ]
        
        return list(mongo.db.attendance.aggregate(pipeline))
    
    def _get_student_performance_analysis(self, organization_id: str, start_date: datetime) -> List[Dict]:
        """Get student performance analysis"""
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$student_id',
                    'total_classes': {'$sum': 1},
                    'present_count': {'$sum': {'$cond': [{'$eq': ['$status', 'present']}, 1, 0]}},
                    'late_count': {'$sum': {'$cond': [{'$eq': ['$status', 'late']}, 1, 0]}},
                    'avg_participation': {'$avg': '$participation_score'},
                    'auto_marked_count': {'$sum': {'$cond': ['$auto_marked', 1, 0]}}
                }
            },
            {
                '$addFields': {
                    'attendance_rate': {
                        '$multiply': [
                            {'$divide': ['$present_count', '$total_classes']},
                            100
                        ]
                    }
                }
            },
            {'$sort': {'attendance_rate': -1}}
        ]
        
        return list(mongo.db.attendance.aggregate(pipeline))
    
    def _get_class_wise_analysis(self, organization_id: str, start_date: datetime) -> List[Dict]:
        """Get class-wise attendance analysis"""
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$class_id',
                    'class_title': {'$first': {'$arrayElemAt': ['$class_info.title', 0]}},
                    'total_students': {'$sum': 1},
                    'present_count': {'$sum': {'$cond': [{'$eq': ['$status', 'present']}, 1, 0]}},
                    'absent_count': {'$sum': {'$cond': [{'$eq': ['$status', 'absent']}, 1, 0]}},
                    'avg_participation': {'$avg': '$participation_score'}
                }
            },
            {
                '$addFields': {
                    'attendance_rate': {
                        '$multiply': [
                            {'$divide': ['$present_count', '$total_students']},
                            100
                        ]
                    }
                }
            },
            {'$sort': {'attendance_rate': -1}}
        ]
        
        return list(mongo.db.attendance.aggregate(pipeline))
    
    def _identify_at_risk_students(self, organization_id: str, start_date: datetime) -> List[Dict]:
        """Identify students who are at risk based on attendance patterns"""
        # Get students with low attendance rates or concerning patterns
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': '$student_id',
                    'total_classes': {'$sum': 1},
                    'present_count': {'$sum': {'$cond': [{'$eq': ['$status', 'present']}, 1, 0]}},
                    'absent_count': {'$sum': {'$cond': [{'$eq': ['$status', 'absent']}, 1, 0]}},
                    'late_count': {'$sum': {'$cond': [{'$eq': ['$status', 'late']}, 1, 0]}},
                    'avg_participation': {'$avg': '$participation_score'},
                    'recent_absences': {
                        '$sum': {
                            '$cond': [
                                {
                                    '$and': [
                                        {'$eq': ['$status', 'absent']},
                                        {'$gte': ['$created_at', start_date]}
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    }
                }
            },
            {
                '$addFields': {
                    'attendance_rate': {
                        '$multiply': [
                            {'$divide': ['$present_count', '$total_classes']},
                            100
                        ]
                    }
                }
            },
            {
                '$match': {
                    '$or': [
                        {'attendance_rate': {'$lt': 70}},  # Less than 70% attendance
                        {'recent_absences': {'$gte': 3}},  # 3+ recent absences
                        {'avg_participation': {'$lt': 3}}  # Low participation scores
                    ]
                }
            },
            {'$sort': {'attendance_rate': 1}}
        ]
        
        return list(mongo.db.attendance.aggregate(pipeline))
    
    def _analyze_rsvp_effectiveness(self, organization_id: str, start_date: datetime) -> Dict:
        """Analyze effectiveness of RSVP system"""
        pipeline = [
            {
                '$lookup': {
                    'from': 'classes',
                    'localField': 'class_id',
                    'foreignField': '_id',
                    'as': 'class_info'
                }
            },
            {
                '$match': {
                    'class_info.organization_id': ObjectId(organization_id),
                    'created_at': {'$gte': start_date},
                    'rsvp_response': {'$exists': True, '$ne': None}
                }
            },
            {
                '$group': {
                    '_id': '$rsvp_response',
                    'count': {'$sum': 1},
                    'actual_present': {
                        '$sum': {'$cond': [{'$eq': ['$status', 'present']}, 1, 0]}
                    },
                    'avg_response_time': {'$avg': '$reminder_response_time'}
                }
            }
        ]
        
        rsvp_stats = list(mongo.db.attendance.aggregate(pipeline))
        
        # Calculate accuracy
        total_rsvp = sum(stat['count'] for stat in rsvp_stats)
        accurate_predictions = 0
        
        for stat in rsvp_stats:
            if stat['_id'] == 'yes':
                accurate_predictions += stat['actual_present']
            elif stat['_id'] == 'no':
                accurate_predictions += (stat['count'] - stat['actual_present'])
        
        accuracy = (accurate_predictions / total_rsvp * 100) if total_rsvp > 0 else 0
        
        return {
            'total_rsvp_responses': total_rsvp,
            'accuracy_percentage': round(accuracy, 2),
            'response_breakdown': rsvp_stats
        }
    
    def _calculate_rsvp_accuracy(self, rsvp_records: List[Dict]) -> float:
        """Calculate RSVP accuracy for a student"""
        accurate_count = 0
        
        for record in rsvp_records:
            rsvp = record.get('rsvp_response')
            actual = record.get('status')
            
            if (rsvp == 'yes' and actual == 'present') or (rsvp == 'no' and actual == 'absent'):
                accurate_count += 1
        
        return (accurate_count / len(rsvp_records) * 100) if rsvp_records else 0
    
    def _is_student_at_risk(self, attendance_records: List[Dict]) -> bool:
        """Determine if a student is at risk"""
        if len(attendance_records) < 3:
            return False
        
        # Check recent attendance (last 5 classes)
        recent_records = attendance_records[:5]
        recent_present = sum(1 for r in recent_records if r.get('status') == 'present')
        recent_rate = recent_present / len(recent_records)
        
        # Check overall attendance
        total_present = sum(1 for r in attendance_records if r.get('status') == 'present')
        overall_rate = total_present / len(attendance_records)
        
        # Check participation scores
        participation_scores = [r.get('participation_score') for r in attendance_records 
                              if r.get('participation_score') is not None]
        avg_participation = statistics.mean(participation_scores) if participation_scores else 5
        
        return recent_rate < 0.6 or overall_rate < 0.7 or avg_participation < 3
    
    def _generate_student_recommendations(self, attendance_records: List[Dict]) -> List[str]:
        """Generate recommendations for student improvement"""
        recommendations = []
        
        if len(attendance_records) < 3:
            return ["Continue attending classes regularly"]
        
        # Analyze patterns
        total_classes = len(attendance_records)
        present_count = sum(1 for r in attendance_records if r.get('status') == 'present')
        late_count = sum(1 for r in attendance_records if r.get('status') == 'late')
        
        attendance_rate = present_count / total_classes
        late_rate = late_count / total_classes
        
        if attendance_rate < 0.8:
            recommendations.append("Improve attendance rate - aim for 90% or higher")
        
        if late_rate > 0.2:
            recommendations.append("Work on punctuality - arrive 10 minutes before class starts")
        
        # Check participation
        participation_scores = [r.get('participation_score') for r in attendance_records 
                              if r.get('participation_score') is not None]
        if participation_scores:
            avg_participation = statistics.mean(participation_scores)
            if avg_participation < 3:
                recommendations.append("Increase class participation and engagement")
        
        # Check equipment compliance
        equipment_records = [r for r in attendance_records if r.get('equipment_brought') is not None]
        if equipment_records:
            equipment_rate = sum(1 for r in equipment_records if r.get('equipment_brought')) / len(equipment_records)
            if equipment_rate < 0.8:
                recommendations.append("Remember to bring required equipment to class")
        
        if not recommendations:
            recommendations.append("Keep up the excellent work!")
        
        return recommendations
    
    def _create_follow_up_message(self, attendance: Attendance, student: User) -> str:
        """Create follow-up message based on attendance status"""
        if attendance.status == 'absent':
            message = f"""
Hi {student.name}! 👋

We missed you in today's class. We hope everything is okay! 

If you're facing any challenges or need to discuss anything, please don't hesitate to reach out to us.

Take care and we look forward to seeing you in the next class! 💪
            """.strip()
        
        elif attendance.status == 'late':
            message = f"""
Hi {student.name}! 👋

We noticed you arrived a bit late to today's class. No worries - it happens! 

💡 Tip: Try to arrive 10 minutes early to get the most out of your training session.

Keep up the great work! 💪
            """.strip()
        
        else:
            message = f"""
Hi {student.name}! 👋

Thanks for attending today's class! We hope you enjoyed it.

If you have any feedback or questions about today's session, feel free to reach out.

See you next time! 💪
            """.strip()
        
        return message
