import os
import json
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService


class EmailVerificationService:
    """Service for sending verification codes via email or saving to tmp files"""
    
    def __init__(self):
        self.verification_method = current_app.config.get('VERIFICATION_METHOD', 'tmp')
        self.aws_region = current_app.config.get('AWS_REGION', 'us-east-1')
        self.from_email = current_app.config.get('SES_FROM_EMAIL', 'noreply@adrilly.com')
        self.code_expiry_minutes = current_app.config.get('VERIFICATION_CODE_EXPIRY', 600) // 60
        self.code_length = current_app.config.get('VERIFICATION_CODE_LENGTH', 6)
        
        # Initialize AWS SES client if using email method
        if self.verification_method == 'email':
            self._init_ses_client()
    
    def _init_ses_client(self):
        """Initialize AWS SES client"""
        try:
            aws_access_key = current_app.config.get('AWS_ACCESS_KEY_ID')
            aws_secret_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')
            
            if aws_access_key and aws_secret_key:
                self.ses_client = boto3.client(
                    'ses',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=self.aws_region
                )
                current_app.logger.info("AWS SES client initialized successfully")
            else:
                # Try using default AWS credentials (IAM role, etc.)
                self.ses_client = boto3.client('ses', region_name=self.aws_region)
                current_app.logger.info("AWS SES client initialized with default credentials")
                
        except NoCredentialsError:
            current_app.logger.error("AWS credentials not found")
            self.ses_client = None
        except Exception as e:
            current_app.logger.error(f"Failed to initialize AWS SES client: {str(e)}")
            self.ses_client = None
    
    def generate_verification_code(self) -> str:
        """Generate a random verification code"""
        return ''.join(random.choices(string.digits, k=self.code_length))
    
    def send_verification_code(self, phone_number: str, email: str, user_name: str = None) -> Tuple[bool, str, str]:
        """
        Send verification code to user's email
        
        Args:
            phone_number: User's phone number (for identification)
            email: User's email address
            user_name: User's name for personalization
            
        Returns:
            Tuple of (success, message, verification_code)
        """
        try:
            print(f"Sending verification code to email: {email}")
            # Generate verification code
            verification_code = self.generate_verification_code()
            expires_at = datetime.utcnow() + timedelta(minutes=self.code_expiry_minutes)
            
            if self.verification_method == 'email':
                success, message = self._send_email(email, verification_code, user_name)
            # elif self.verification_method == 'whatsapp':
            #     success, message = self._send_whatsapp(phone_number, verification_code)
            else:
                success, message = self._save_to_tmp(phone_number, verification_code, email, expires_at)
            
            if success:
                return True, message, verification_code
            else:
                return False, message, None
                
        except Exception as e:
            current_app.logger.error(f"Error sending verification code: {str(e)}")
            return False, f"Failed to send verification code: {str(e)}", None
    
    def _send_email(self, email: str, verification_code: str, user_name: str = None) -> Tuple[bool, str]:
        """Send verification code via AWS SES"""
        try:
            if not self.ses_client:
                return False, "Email service not configured"
            
            # Prepare email content
            subject = "Your botle Verification Code"
            
            # HTML email template
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Verification Code</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 0;
                        background-color: #0f0f0f;
                        color: #ffffff;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 40px 20px;
                    }}
                    .card {{
                        background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
                        border-radius: 16px;
                        padding: 40px;
                        border: 1px solid #00ff88;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                    }}
                    .logo {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo h1 {{
                        font-size: 2.5rem;
                        font-weight: 700;
                        margin: 0;
                        background: linear-gradient(135deg, #ffffff 0%, #00ff88 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    .code-container {{
                        text-align: center;
                        margin: 30px 0;
                        padding: 30px;
                        background: rgba(0, 255, 136, 0.1);
                        border: 2px solid #00ff88;
                        border-radius: 12px;
                    }}
                    .verification-code {{
                        font-size: 2.5rem;
                        font-weight: 700;
                        color: #00ff88;
                        letter-spacing: 0.3em;
                        margin: 0;
                        font-family: 'Courier New', monospace;
                    }}
                    .message {{
                        color: #cccccc;
                        font-size: 1rem;
                        line-height: 1.6;
                        margin-bottom: 20px;
                    }}
                    .footer {{
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #333333;
                        font-size: 0.85rem;
                        color: #888888;
                        text-align: center;
                    }}
                    .warning {{
                        background: rgba(255, 170, 0, 0.1);
                        border: 1px solid #ffaa00;
                        border-radius: 8px;
                        padding: 15px;
                        margin: 20px 0;
                        color: #ffaa00;
                        font-size: 0.9rem;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="card">
                        <div class="logo">
                            <h1>botle</h1>
                        </div>
                        
                        <p class="message">
                            Hello{f" {user_name}" if user_name else ""},
                        </p>
                        
                        <p class="message">
                            You requested to log in to your botle Sports Coaching account. 
                            Use the verification code below to complete your login:
                        </p>
                        
                        <div class="code-container">
                            <p class="verification-code">{verification_code}</p>
                        </div>
                        
                        <div class="warning">
                            <strong>Security Notice:</strong> This code will expire in {self.code_expiry_minutes} minutes. 
                            If you didn't request this code, please ignore this email.
                        </div>
                        
                        <p class="message">
                            Simply enter this code in the verification step of your login process.
                        </p>
                        
                        <div class="footer">
                            <p>
                                This is an automated message from botle Sports Coaching Management.<br>
                                If you have any questions, please contact our support team.
                            </p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text version
            text_body = f"""
            Hello{f" {user_name}" if user_name else ""},
            
            You requested to log in to your botle Sports Coaching account.
            
            Your verification code is: {verification_code}
            
            This code will expire in {self.code_expiry_minutes} minutes.
            
            If you didn't request this code, please ignore this email.
            
            ---
            botle Sports Coaching Management
            """
            
            # Send email
            response = self.ses_client.send_email(
                Destination={'ToAddresses': [email]},
                Message={
                    'Body': {
                        'Html': {'Charset': 'UTF-8', 'Data': html_body},
                        'Text': {'Charset': 'UTF-8', 'Data': text_body}
                    },
                    'Subject': {'Charset': 'UTF-8', 'Data': subject}
                },
                Source=self.from_email
            )
            
            current_app.logger.info(f"Verification email sent to {email}, MessageId: {response['MessageId']}")
            return True, f"Verification code sent to {email}"
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            current_app.logger.error(f"AWS SES error ({error_code}): {error_message}")
            
            if error_code == 'MessageRejected':
                return False, "Email address is not verified or blocked"
            elif error_code == 'MailFromDomainNotVerified':
                return False, "Email domain not verified"
            else:
                return False, f"Email service error: {error_message}"
                
        except Exception as e:
            current_app.logger.error(f"Unexpected error sending email: {str(e)}")
            return False, f"Failed to send email: {str(e)}"
    
    def _send_whatsapp(self, phone_number: str, verification_code: str) -> Tuple[bool, str]:
        """Send verification code via WhatsApp"""
        try:
            enhanced_whatsapp_service = EnhancedWhatsAppService()
            enhanced_whatsapp_service.send_otp_to_logged_in_user(phone_number, verification_code)
            return True, "Verification code sent to WhatsApp"
        except Exception as e:
            current_app.logger.error(f"Error sending verification code via WhatsApp: {str(e)}")
            return False, f"Failed to send verification code via WhatsApp: {str(e)}"
    
    def _save_to_tmp(self, phone_number: str, verification_code: str, email: str, expires_at: datetime) -> Tuple[bool, str]:
        """Save verification code to tmp file for development/testing"""
        try:
            # Create tmp directory if it doesn't exist
            tmp_dir = os.path.join(os.getcwd(), 'tmp', 'verification_codes')
            os.makedirs(tmp_dir, exist_ok=True)
            
            # Clean phone number for filename
            clean_phone = phone_number.replace('+', '').replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
            
            # Create verification data
            verification_data = {
                'phone_number': phone_number,
                'email': email,
                'verification_code': verification_code,
                'expires_at': expires_at.isoformat(),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Save to file
            filename = f"verification_{clean_phone}.json"
            filepath = os.path.join(tmp_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(verification_data, f, indent=2)
            
            current_app.logger.info(f"Verification code saved to {filepath}")
            return True, f"Verification code saved to tmp file: {filename}"
            
        except Exception as e:
            current_app.logger.error(f"Error saving verification code to tmp: {str(e)}")
            return False, f"Failed to save verification code: {str(e)}"
    
    def get_verification_code_from_tmp(self, phone_number: str) -> Optional[Dict]:
        """Get verification code from tmp file (for development/testing)"""
        try:
            # Clean phone number for filename
            clean_phone = phone_number.replace('+', '').replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
            
            tmp_dir = os.path.join(os.getcwd(), 'tmp', 'verification_codes')
            filename = f"verification_{clean_phone}.json"
            filepath = os.path.join(tmp_dir, filename)
            
            if not os.path.exists(filepath):
                return None
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Check if expired
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.utcnow() > expires_at:
                # Remove expired file
                os.remove(filepath)
                return None
            
            return data
            
        except Exception as e:
            current_app.logger.error(f"Error reading verification code from tmp: {str(e)}")
            return None
    
    def cleanup_expired_tmp_files(self):
        """Clean up expired verification code files"""
        try:
            tmp_dir = os.path.join(os.getcwd(), 'tmp', 'verification_codes')
            if not os.path.exists(tmp_dir):
                return
            
            current_time = datetime.utcnow()
            cleaned_count = 0
            
            for filename in os.listdir(tmp_dir):
                if filename.startswith('verification_') and filename.endswith('.json'):
                    filepath = os.path.join(tmp_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                        
                        expires_at = datetime.fromisoformat(data['expires_at'])
                        if current_time > expires_at:
                            os.remove(filepath)
                            cleaned_count += 1
                    except:
                        # Remove corrupted files
                        try:
                            os.remove(filepath)
                            cleaned_count += 1
                        except:
                            pass
            
            if cleaned_count > 0:
                current_app.logger.info(f"Cleaned up {cleaned_count} expired verification files")
                
        except Exception as e:
            current_app.logger.error(f"Error cleaning up tmp files: {str(e)}")
    
    def verify_ses_configuration(self) -> Dict[str, any]:
        """Verify AWS SES configuration and return status"""
        if self.verification_method != 'email':
            return {
                'configured': True,
                'method': 'tmp',
                'message': 'Using tmp file method for verification codes'
            }
        
        if not self.ses_client:
            return {
                'configured': False,
                'method': 'email',
                'error': 'AWS SES client not initialized'
            }
        
        try:
            # Test SES configuration
            response = self.ses_client.get_send_quota()
            
            return {
                'configured': True,
                'method': 'email',
                'send_quota': response.get('Max24HourSend', 0),
                'sent_last_24h': response.get('SentLast24Hours', 0),
                'send_rate': response.get('MaxSendRate', 0),
                'from_email': self.from_email,
                'region': self.aws_region
            }
            
        except Exception as e:
            return {
                'configured': False,
                'method': 'email',
                'error': str(e)
            } 