from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from app.extensions import mongo
from flask import current_app, request
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import re
import hashlib
import hmac
import jwt
import os
from bson import ObjectId
import ipaddress
from email_validator import validate_email, EmailNotValidError

class SecurityService:
    """Enterprise-grade security service with comprehensive protection"""
    
    def __init__(self):
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 30
        self.password_history_count = 5
        self.session_timeout_minutes = 120
        self.jwt_algorithm = 'HS256'
        
        # Security policies
        self.password_policy = {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_digits': True,
            'require_special_chars': True,
            'max_length': 128
        }
        
        # Rate limiting thresholds
        self.rate_limits = {
            'login': {'requests': 10, 'window': 300},  # 10 attempts per 5 minutes
            'api': {'requests': 100, 'window': 60},    # 100 requests per minute
            'password_reset': {'requests': 3, 'window': 3600},  # 3 attempts per hour
            'otp': {'requests': 5, 'window': 300}      # 5 OTP requests per 5 minutes
        }
        
        # Trusted IP ranges (can be configured)
        self.trusted_ip_ranges = [
            # Add your trusted IP ranges here
            # '10.0.0.0/8',
            # '172.16.0.0/12',
            # '192.168.0.0/16'
        ]
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password against security policy"""
        errors = []
        
        if len(password) < self.password_policy['min_length']:
            errors.append(f"Password must be at least {self.password_policy['min_length']} characters long")
        
        if len(password) > self.password_policy['max_length']:
            errors.append(f"Password must not exceed {self.password_policy['max_length']} characters")
        
        if self.password_policy['require_uppercase'] and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.password_policy['require_lowercase'] and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.password_policy['require_digits'] and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if self.password_policy['require_special_chars'] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Check for common patterns
        if password.lower() in ['password', '123456', 'qwerty', 'abc123', 'password123']:
            errors.append("Password is too common and easily guessable")
        
        # Check for sequential characters
        if re.search(r'(012|123|234|345|456|567|678|789|abc|bcd|cde|def)', password.lower()):
            errors.append("Password should not contain sequential characters")
        
        return len(errors) == 0, errors
    
    def generate_secure_password(self, length: int = 12) -> str:
        """Generate a secure random password"""
        import string
        
        # Ensure we have at least one character from each required category
        password_chars = []
        
        if self.password_policy['require_uppercase']:
            password_chars.append(secrets.choice(string.ascii_uppercase))
        
        if self.password_policy['require_lowercase']:
            password_chars.append(secrets.choice(string.ascii_lowercase))
        
        if self.password_policy['require_digits']:
            password_chars.append(secrets.choice(string.digits))
        
        if self.password_policy['require_special_chars']:
            password_chars.append(secrets.choice('!@#$%^&*()'))
        
        # Fill the rest with random characters
        all_chars = string.ascii_letters + string.digits + '!@#$%^&*()'
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password_chars)
        return ''.join(password_chars)
    
    def hash_password_secure(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with secure algorithm and salt"""
        if not salt:
            salt = secrets.token_hex(32)
        
        # Use PBKDF2 with high iteration count
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 100,000 iterations
        )
        
        return password_hash.hex(), salt
    
    def verify_password_secure(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify password against stored hash"""
        password_hash, _ = self.hash_password_secure(password, salt)
        return hmac.compare_digest(password_hash, stored_hash)
    
    def check_password_history(self, user_id: str, new_password: str) -> bool:
        """Check if password was used recently"""
        try:
            user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
            if not user_data:
                return True  # User not found, allow password
            
            password_history = user_data.get('password_history', [])
            
            for old_password_data in password_history[-self.password_history_count:]:
                if self.verify_password_secure(
                    new_password, 
                    old_password_data['hash'], 
                    old_password_data['salt']
                ):
                    return False  # Password was used recently
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error checking password history: {str(e)}")
            return True  # Allow password on error
    
    def update_password_history(self, user_id: str, password_hash: str, salt: str):
        """Update user's password history"""
        try:
            new_password_entry = {
                'hash': password_hash,
                'salt': salt,
                'changed_at': datetime.utcnow()
            }
            
            mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$push': {
                        'password_history': {
                            '$each': [new_password_entry],
                            '$slice': -self.password_history_count  # Keep only last N passwords
                        }
                    }
                }
            )
            
        except Exception as e:
            current_app.logger.error(f"Error updating password history: {str(e)}")
    
    def check_account_lockout(self, identifier: str) -> Tuple[bool, Optional[datetime]]:
        """Check if account is locked due to failed login attempts"""
        try:
            lockout_data = mongo.db.account_lockouts.find_one({'identifier': identifier})
            
            if not lockout_data:
                return False, None
            
            lockout_until = lockout_data.get('locked_until')
            if lockout_until and lockout_until > datetime.utcnow():
                return True, lockout_until
            
            # Lockout expired, remove it
            mongo.db.account_lockouts.delete_one({'identifier': identifier})
            return False, None
            
        except Exception as e:
            current_app.logger.error(f"Error checking account lockout: {str(e)}")
            return False, None
    
    def record_failed_login(self, identifier: str, ip_address: str):
        """Record failed login attempt and implement lockout if needed"""
        try:
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=30)
            
            # Count recent failed attempts
            failed_attempts = mongo.db.login_attempts.count_documents({
                'identifier': identifier,
                'success': False,
                'timestamp': {'$gte': window_start}
            })
            
            # Record this attempt
            mongo.db.login_attempts.insert_one({
                'identifier': identifier,
                'ip_address': ip_address,
                'success': False,
                'timestamp': now,
                'user_agent': request.headers.get('User-Agent', '')
            })
            
            # Check if we need to lock the account
            if failed_attempts >= self.max_login_attempts - 1:
                lockout_until = now + timedelta(minutes=self.lockout_duration_minutes)
                
                mongo.db.account_lockouts.update_one(
                    {'identifier': identifier},
                    {
                        '$set': {
                            'identifier': identifier,
                            'locked_until': lockout_until,
                            'locked_at': now,
                            'failed_attempts': failed_attempts + 1
                        }
                    },
                    upsert=True
                )
                
                # Log security event
                self.log_security_event(
                    'account_locked',
                    {'identifier': identifier, 'ip_address': ip_address, 'attempts': failed_attempts + 1}
                )
            
        except Exception as e:
            current_app.logger.error(f"Error recording failed login: {str(e)}")
    
    def record_successful_login(self, identifier: str, ip_address: str, user_id: str):
        """Record successful login and clear lockout if exists"""
        try:
            now = datetime.utcnow()
            
            # Record successful login
            mongo.db.login_attempts.insert_one({
                'identifier': identifier,
                'ip_address': ip_address,
                'success': True,
                'timestamp': now,
                'user_agent': request.headers.get('User-Agent', ''),
                'user_id': user_id
            })
            
            # Clear any existing lockout
            mongo.db.account_lockouts.delete_one({'identifier': identifier})
            
            # Update user's last login
            mongo.db.users.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'last_login': now,
                        'last_login_ip': ip_address
                    }
                }
            )
            
        except Exception as e:
            current_app.logger.error(f"Error recording successful login: {str(e)}")
    
    def check_rate_limit(self, identifier: str, limit_type: str) -> Tuple[bool, int]:
        """Check if request is within rate limits"""
        try:
            if limit_type not in self.rate_limits:
                return True, 0
            
            limit_config = self.rate_limits[limit_type]
            window_start = datetime.utcnow() - timedelta(seconds=limit_config['window'])
            
            # Count recent requests
            request_count = mongo.db.rate_limits.count_documents({
                'identifier': identifier,
                'limit_type': limit_type,
                'timestamp': {'$gte': window_start}
            })
            
            if request_count >= limit_config['requests']:
                return False, limit_config['requests'] - request_count
            
            # Record this request
            mongo.db.rate_limits.insert_one({
                'identifier': identifier,
                'limit_type': limit_type,
                'timestamp': datetime.utcnow(),
                'ip_address': request.remote_addr if request else None
            })
            
            return True, limit_config['requests'] - request_count - 1
            
        except Exception as e:
            current_app.logger.error(f"Error checking rate limit: {str(e)}")
            return True, 0
    
    def validate_email_security(self, email: str) -> Tuple[bool, List[str]]:
        """Validate email with security considerations"""
        errors = []
        
        try:
            # Basic email validation
            validated_email = validate_email(email)
            email = validated_email.email
            
            # Check for suspicious patterns
            suspicious_patterns = [
                r'[+].*[+]',  # Multiple plus signs
                r'\.{2,}',    # Multiple consecutive dots
                r'^\.|\.$',   # Starting or ending with dot
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, email):
                    errors.append("Email format appears suspicious")
                    break
            
            # Check against disposable email providers
            disposable_domains = [
                '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
                'tempmail.org', 'throwaway.email', 'yopmail.com'
            ]
            
            domain = email.split('@')[1].lower()
            if domain in disposable_domains:
                errors.append("Disposable email addresses are not allowed")
            
        except EmailNotValidError as e:
            errors.append(f"Invalid email format: {str(e)}")
        
        return len(errors) == 0, errors
    
    def sanitize_input(self, input_data: str, input_type: str = 'text') -> str:
        """Sanitize user input to prevent injection attacks"""
        if not isinstance(input_data, str):
            return str(input_data)
        
        # Remove null bytes
        sanitized = input_data.replace('\x00', '')
        
        if input_type == 'text':
            # Basic text sanitization
            sanitized = re.sub(r'[<>"\']', '', sanitized)
            sanitized = sanitized.strip()
        
        elif input_type == 'phone':
            # Phone number sanitization
            sanitized = re.sub(r'[^\d\+\-\(\)\s]', '', sanitized)
        
        elif input_type == 'name':
            # Name sanitization
            sanitized = re.sub(r'[^a-zA-Z\s\-\.]', '', sanitized)
            sanitized = sanitized.strip()
        
        elif input_type == 'alphanumeric':
            # Alphanumeric only
            sanitized = re.sub(r'[^a-zA-Z0-9]', '', sanitized)
        
        return sanitized[:1000]  # Limit length to prevent DoS
    
    def validate_ip_address(self, ip_address: str) -> bool:
        """Validate if IP address is from trusted range"""
        if not self.trusted_ip_ranges:
            return True  # No restrictions if no ranges defined
        
        try:
            user_ip = ipaddress.ip_address(ip_address)
            
            for ip_range in self.trusted_ip_ranges:
                if user_ip in ipaddress.ip_network(ip_range):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def generate_secure_token(self, purpose: str, user_id: str = None, 
                            expires_in: int = 3600) -> Tuple[str, str]:
        """Generate secure token for various purposes"""
        token_id = secrets.token_urlsafe(32)
        
        payload = {
            'token_id': token_id,
            'purpose': purpose,
            'issued_at': datetime.utcnow().timestamp(),
            'expires_at': (datetime.utcnow() + timedelta(seconds=expires_in)).timestamp()
        }
        
        if user_id:
            payload['user_id'] = user_id
        
        secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
        token = jwt.encode(payload, secret_key, algorithm=self.jwt_algorithm)
        
        # Store token in database for revocation capability
        mongo.db.security_tokens.insert_one({
            'token_id': token_id,
            'purpose': purpose,
            'user_id': user_id,
            'issued_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=expires_in),
            'is_revoked': False
        })
        
        return token, token_id
    
    def verify_secure_token(self, token: str, purpose: str) -> Tuple[bool, Optional[Dict]]:
        """Verify secure token"""
        try:
            secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
            payload = jwt.decode(token, secret_key, algorithms=[self.jwt_algorithm])
            
            # Check purpose
            if payload.get('purpose') != purpose:
                return False, None
            
            # Check if token is revoked
            token_data = mongo.db.security_tokens.find_one({
                'token_id': payload.get('token_id'),
                'is_revoked': False
            })
            
            if not token_data:
                return False, None
            
            # Check expiration
            if datetime.utcnow() > token_data['expires_at']:
                return False, None
            
            return True, payload
            
        except jwt.InvalidTokenError:
            return False, None
        except Exception as e:
            current_app.logger.error(f"Error verifying token: {str(e)}")
            return False, None
    
    def revoke_token(self, token_id: str):
        """Revoke a security token"""
        try:
            mongo.db.security_tokens.update_one(
                {'token_id': token_id},
                {'$set': {'is_revoked': True, 'revoked_at': datetime.utcnow()}}
            )
        except Exception as e:
            current_app.logger.error(f"Error revoking token: {str(e)}")
    
    def log_security_event(self, event_type: str, details: Dict):
        """Log security-related events for monitoring"""
        try:
            security_event = {
                'event_type': event_type,
                'details': details,
                'timestamp': datetime.utcnow(),
                'ip_address': request.remote_addr if request else None,
                'user_agent': request.headers.get('User-Agent', '') if request else None,
                'severity': self._get_event_severity(event_type)
            }
            
            mongo.db.security_events.insert_one(security_event)
            
            # Alert on high-severity events
            if security_event['severity'] == 'high':
                self._send_security_alert(security_event)
            
        except Exception as e:
            current_app.logger.error(f"Error logging security event: {str(e)}")
    
    def _get_event_severity(self, event_type: str) -> str:
        """Determine severity level of security event"""
        high_severity_events = [
            'account_locked', 'suspicious_login', 'unauthorized_access',
            'data_breach_attempt', 'privilege_escalation'
        ]
        
        medium_severity_events = [
            'failed_login', 'password_change', 'token_revoked',
            'rate_limit_exceeded'
        ]
        
        if event_type in high_severity_events:
            return 'high'
        elif event_type in medium_severity_events:
            return 'medium'
        else:
            return 'low'
    
    def _send_security_alert(self, security_event: Dict):
        """Send alert for high-severity security events"""
        # This could integrate with email, Slack, or other alerting systems
        current_app.logger.critical(f"HIGH SEVERITY SECURITY EVENT: {security_event}")
    
    def cleanup_expired_tokens(self):
        """Clean up expired security tokens"""
        try:
            result = mongo.db.security_tokens.delete_many({
                'expires_at': {'$lt': datetime.utcnow()}
            })
            return result.deleted_count
        except Exception as e:
            current_app.logger.error(f"Error cleaning up expired tokens: {str(e)}")
            return 0
    
    def cleanup_old_login_attempts(self, days_to_keep: int = 30):
        """Clean up old login attempts"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            result = mongo.db.login_attempts.delete_many({
                'timestamp': {'$lt': cutoff_date}
            })
            return result.deleted_count
        except Exception as e:
            current_app.logger.error(f"Error cleaning up login attempts: {str(e)}")
            return 0
    
    def get_security_report(self, days: int = 7) -> Dict:
        """Generate security report for the specified period"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Login attempts analysis
            login_stats = list(mongo.db.login_attempts.aggregate([
                {'$match': {'timestamp': {'$gte': start_date}}},
                {
                    '$group': {
                        '_id': '$success',
                        'count': {'$sum': 1}
                    }
                }
            ]))
            
            # Security events analysis
            security_events = list(mongo.db.security_events.aggregate([
                {'$match': {'timestamp': {'$gte': start_date}}},
                {
                    '$group': {
                        '_id': {'event_type': '$event_type', 'severity': '$severity'},
                        'count': {'$sum': 1}
                    }
                }
            ]))
            
            # Rate limiting events
            rate_limit_events = list(mongo.db.rate_limits.aggregate([
                {'$match': {'timestamp': {'$gte': start_date}}},
                {
                    '$group': {
                        '_id': '$limit_type',
                        'count': {'$sum': 1}
                    }
                }
            ]))
            
            # Account lockouts
            lockouts = mongo.db.account_lockouts.count_documents({
                'locked_at': {'$gte': start_date}
            })
            
            return {
                'period_days': days,
                'login_statistics': {item['_id']: item['count'] for item in login_stats},
                'security_events': security_events,
                'rate_limit_events': {item['_id']: item['count'] for item in rate_limit_events},
                'account_lockouts': lockouts,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating security report: {str(e)}")
            return {'error': str(e)}

# Global security service instance
security_service = SecurityService()
