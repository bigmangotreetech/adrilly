import os
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from flask import current_app
from app.extensions import mongo
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService

class WhatsAppVerificationService:
    """
    Service for handling WhatsApp-based verification codes
    """
    
    def __init__(self):
        self.code_expiry_minutes = current_app.config.get('VERIFICATION_CODE_EXPIRY', 600) // 60
        self.code_length = current_app.config.get('VERIFICATION_CODE_LENGTH', 6)
        self.whatsapp_service = EnhancedWhatsAppService()
        
    def generate_verification_code(self) -> str:
        """Generate a random numeric verification code"""
        return ''.join(random.choices(string.digits, k=self.code_length))
    
    def send_verification_code(self, phone_number: str) -> Tuple[bool, str, Optional[str]]:
        """
        Send verification code via WhatsApp
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Tuple of (success, message, verification_code)
        """
        try:
            # Generate verification code
            verification_code = self.generate_verification_code()
            expires_at = datetime.utcnow() + timedelta(minutes=self.code_expiry_minutes)
            
            # Store verification code
            verification_data = {
                'phone_number': phone_number,
                'code': verification_code,
                'expires_at': expires_at,
                'created_at': datetime.utcnow(),
                'verified': False,
                'attempts': 0
            }
            
            # Save to database
            mongo.db.whatsapp_verifications.update_one(
                {'phone_number': phone_number},
                {'$set': verification_data},
                upsert=True
            )
            
            # Prepare WhatsApp message
            message = (
                f"Your Adrilly verification code is: {verification_code}\n\n"
                f"This code will expire in {self.code_expiry_minutes} minutes.\n"
                "Do not share this code with anyone."
            )
            
            # Send via WhatsApp
            success, send_message = self.whatsapp_service.send_message(
                phone_number=phone_number,
                message=message
            )
            
            if success:
                return True, "Verification code sent successfully", verification_code
            else:
                return False, f"Failed to send verification code: {send_message}", None
                
        except Exception as e:
            current_app.logger.error(f"Error sending WhatsApp verification code: {str(e)}")
            return False, f"Failed to send verification code: {str(e)}", None
    
    def verify_code(self, phone_number: str, code: str) -> Tuple[bool, str]:
        """
        Verify the provided code
        
        Args:
            phone_number: User's phone number
            code: Verification code to verify
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get verification record
            verification = mongo.db.whatsapp_verifications.find_one({
                'phone_number': phone_number,
                'verified': False
            })
            
            if not verification:
                return False, "No pending verification found"
                
            # Check if code has expired
            if verification['expires_at'] < datetime.utcnow():
                return False, "Verification code has expired"
                
            # Check attempts
            if verification['attempts'] >= 3:
                return False, "Too many verification attempts"
                
            # Update attempts
            mongo.db.whatsapp_verifications.update_one(
                {'_id': verification['_id']},
                {'$inc': {'attempts': 1}}
            )
            
            # Verify code
            if verification['code'] != code:
                return False, "Invalid verification code"
                
            # Mark as verified
            mongo.db.whatsapp_verifications.update_one(
                {'_id': verification['_id']},
                {
                    '$set': {
                        'verified': True,
                        'verified_at': datetime.utcnow()
                    }
                }
            )
            
            return True, "Code verified successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error verifying WhatsApp code: {str(e)}")
            return False, f"Verification failed: {str(e)}"
    
    def get_verification_status(self, phone_number: str) -> Dict:
        """
        Get the current verification status for a phone number
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Dictionary containing verification status
        """
        verification = mongo.db.whatsapp_verifications.find_one({
            'phone_number': phone_number
        })
        
        if not verification:
            return {
                'status': 'not_found',
                'verified': False,
                'attempts': 0
            }
            
        return {
            'status': 'verified' if verification['verified'] else 'pending',
            'verified': verification['verified'],
            'attempts': verification['attempts'],
            'expires_at': verification['expires_at']
        }
