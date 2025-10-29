"""
Service for managing Botle Coins transactions
Handles awarding, redeeming, and tracking coin balances
"""

from datetime import datetime, timedelta
from bson import ObjectId
from flask import current_app
from app.extensions import mongo
from app.models.coin_transaction import CoinTransaction


class CoinService:
    """Service for managing Botle Coins"""
    
    @staticmethod
    def award_coins(user_id, amount, reason, description=None, reference_id=None, 
                    reference_type=None, created_by=None):
        """
        Award coins to a user and log the transaction
        
        Args:
            user_id: User to award coins to
            amount: Number of coins to award (positive integer)
            reason: Reason code (from CoinTransaction constants)
            description: Optional custom description
            reference_id: Optional reference to related object (class_id, etc.)
            reference_type: Type of reference object
            created_by: User who created this award (for manual awards)
        
        Returns:
            tuple: (success: bool, transaction_dict or error_message, new_balance)
        """
        try:
            if amount <= 0:
                return False, "Amount must be positive", 0
            
            user_id = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            
            # Get current user balance
            user = mongo.db.users.find_one({'_id': user_id})
            if not user:
                return False, "User not found", 0
            
            current_balance = user.get('botle_coins', 0)
            new_balance = current_balance + amount
            
            # Update user balance
            result = mongo.db.users.update_one(
                {'_id': user_id},
                {
                    '$set': {
                        'botle_coins': new_balance,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return False, "Failed to update user balance", current_balance
            
            # Create transaction log
            transaction = CoinTransaction(
                user_id=user_id,
                amount=amount,
                transaction_type=CoinTransaction.TYPE_EARNED,
                reason=reason,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                balance_before=current_balance,
                balance_after=new_balance,
                created_by=created_by
            )
            
            # Save transaction to database
            transaction_dict = transaction.to_dict()
            transaction_dict['user_id'] = user_id  # Keep as ObjectId in DB
            if reference_id:
                transaction_dict['reference_id'] = ObjectId(reference_id) if not isinstance(reference_id, ObjectId) else reference_id
            if created_by:
                transaction_dict['created_by'] = ObjectId(created_by) if not isinstance(created_by, ObjectId) else created_by
            
            insert_result = mongo.db.coin_transactions.insert_one(transaction_dict)
            transaction._id = insert_result.inserted_id
            
            current_app.logger.info(
                f"Awarded {amount} coins to user {user_id}. "
                f"Reason: {reason}. New balance: {new_balance}"
            )
            
            return True, transaction.to_dict(), new_balance
        
        except Exception as e:
            current_app.logger.error(f"Error awarding coins: {str(e)}")
            return False, str(e), 0
    
    @staticmethod
    def redeem_coins(user_id, amount, reason, description=None, reference_id=None, 
                     reference_type=None):
        """
        Redeem (deduct) coins from a user
        
        Args:
            user_id: User to redeem coins from
            amount: Number of coins to redeem (positive integer)
            reason: Reason code
            description: Optional custom description
            reference_id: Optional reference to related object
            reference_type: Type of reference object
        
        Returns:
            tuple: (success: bool, transaction_dict or error_message, new_balance)
        """
        try:
            if amount <= 0:
                return False, "Amount must be positive", 0
            
            user_id = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            
            # Get current user balance
            user = mongo.db.users.find_one({'_id': user_id})
            if not user:
                return False, "User not found", 0
            
            current_balance = user.get('botle_coins', 0)
            
            # Check if user has enough coins
            if current_balance < amount:
                return False, f"Insufficient coins. Current balance: {current_balance}", current_balance
            
            new_balance = current_balance - amount
            
            # Update user balance
            result = mongo.db.users.update_one(
                {'_id': user_id},
                {
                    '$set': {
                        'botle_coins': new_balance,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return False, "Failed to update user balance", current_balance
            
            # Create transaction log (negative amount for redemption)
            transaction = CoinTransaction(
                user_id=user_id,
                amount=-amount,  # Negative for redemption
                transaction_type=CoinTransaction.TYPE_REDEEMED,
                reason=reason,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                balance_before=current_balance,
                balance_after=new_balance
            )
            
            # Save transaction to database
            transaction_dict = transaction.to_dict()
            transaction_dict['user_id'] = user_id
            if reference_id:
                transaction_dict['reference_id'] = ObjectId(reference_id) if not isinstance(reference_id, ObjectId) else reference_id
            
            insert_result = mongo.db.coin_transactions.insert_one(transaction_dict)
            transaction._id = insert_result.inserted_id
            
            current_app.logger.info(
                f"Redeemed {amount} coins from user {user_id}. "
                f"Reason: {reason}. New balance: {new_balance}"
            )
            
            return True, transaction.to_dict(), new_balance
        
        except Exception as e:
            current_app.logger.error(f"Error redeeming coins: {str(e)}")
            return False, str(e), 0
    
    @staticmethod
    def check_weekly_attendance_reward(user_id):
        """
        Check if user has attended 4 classes in the past 7 days
        Award coins if eligible and not already rewarded this week
        
        Args:
            user_id: User to check
        
        Returns:
            tuple: (awarded: bool, message: str, coins_awarded: int)
        """
        try:
            user_id = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            
            # Get current week's date range (last 7 days)
            now = datetime.utcnow()
            week_start = now - timedelta(days=7)
            
            # Count attended classes in the past 7 days
            attended_count = mongo.db.attendance.count_documents({
                'student_id': user_id,
                'status': 'present',
                'created_at': {'$gte': week_start}
            })
            
            if attended_count < 4:
                return False, f"Not enough classes attended this week ({attended_count}/4)", 0
            
            # Check if already rewarded this week
            existing_reward = mongo.db.coin_transactions.find_one({
                'user_id': user_id,
                'reason': CoinTransaction.REASON_WEEKLY_ATTENDANCE,
                'created_at': {'$gte': week_start}
            })
            
            if existing_reward:
                return False, "Weekly attendance reward already claimed this week", 0
            
            # Award coins
            coins_to_award = 10
            success, result, new_balance = CoinService.award_coins(
                user_id=user_id,
                amount=coins_to_award,
                reason=CoinTransaction.REASON_WEEKLY_ATTENDANCE,
                description=f"Attended {attended_count} classes this week"
            )
            
            if success:
                return True, f"Earned {coins_to_award} coins for weekly attendance!", coins_to_award
            else:
                return False, result, 0
        
        except Exception as e:
            current_app.logger.error(f"Error checking weekly attendance: {str(e)}")
            return False, str(e), 0
    
    @staticmethod
    def get_user_transactions(user_id, limit=50, skip=0):
        """
        Get transaction history for a user
        
        Args:
            user_id: User ID
            limit: Number of transactions to return
            skip: Number of transactions to skip (for pagination)
        
        Returns:
            list: Transaction dictionaries
        """
        try:
            user_id = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            
            transactions = mongo.db.coin_transactions.find({
                'user_id': user_id
            }).sort('created_at', -1).skip(skip).limit(limit)
            
            transaction_list = []
            for trans in transactions:
                trans['_id'] = str(trans['_id'])
                trans['user_id'] = str(trans['user_id'])
                if trans.get('reference_id'):
                    trans['reference_id'] = str(trans['reference_id'])
                if trans.get('created_by'):
                    trans['created_by'] = str(trans['created_by'])
                transaction_list.append(trans)
            
            return transaction_list
        
        except Exception as e:
            current_app.logger.error(f"Error fetching transactions: {str(e)}")
            return []
    
    @staticmethod
    def get_user_balance(user_id):
        """
        Get current coin balance for a user
        
        Args:
            user_id: User ID
        
        Returns:
            int: Current balance
        """
        try:
            user_id = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            user = mongo.db.users.find_one({'_id': user_id})
            return user.get('botle_coins', 0) if user else 0
        except Exception as e:
            current_app.logger.error(f"Error getting user balance: {str(e)}")
            return 0

