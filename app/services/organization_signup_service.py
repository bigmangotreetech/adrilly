from datetime import datetime, timedelta
from flask import current_app
from bson import ObjectId
from app.extensions import mongo
from app.models.organization import Organization
from app.models.user import User
from app.services.auth_service import AuthService
import re
from typing import Tuple, Dict, Any, Optional

class OrganizationSignupService:
    """Service for handling organization-specific user signups with shareable links"""
    
    @staticmethod
    def validate_signup_link(slug: str, token: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate a signup link and return organization details
        
        Args:
            slug: Organization's unique slug
            token: Security token from the URL
            
        Returns:
            Tuple of (is_valid, message, organization_data)
        """
        try:
            # Find organization by slug
            org_data = mongo.db.organizations.find_one({
                'signup_slug': slug,
                'is_active': True
            })
            
            if not org_data:
                return False, "Invalid signup link", None
            
            org = Organization.from_dict(org_data)
            
            # Check if signup is enabled
            if not org.signup_enabled:
                return False, "Signup is currently disabled for this organization", None
            
            # Verify token
            if not org.verify_signup_token(token):
                return False, "Invalid or expired signup link", None
            
            # Check subscription status
            if org.subscription_status != 'active':
                return False, "Organization subscription is not active", None
            
            return True, "Valid signup link", org_data
            
        except Exception as e:
            current_app.logger.error(f"Error validating signup link: {str(e)}")
            return False, "Error validating signup link", None
    
    @staticmethod
    def check_signup_rate_limit(organization_id: str) -> Tuple[bool, str]:
        """
        Check if organization has exceeded daily signup limit
        
        Args:
            organization_id: Organization's ID
            
        Returns:
            Tuple of (within_limit, message)
        """
        try:
            org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
            if not org_data:
                return False, "Organization not found"
            
            org = Organization.from_dict(org_data)
            
            # Count signups in last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            signup_count = mongo.db.users.count_documents({
                'organization_id': ObjectId(organization_id),
                'created_at': {'$gte': yesterday}
            })
            
            if signup_count >= org.max_signups_per_day:
                return False, f"Daily signup limit reached ({org.max_signups_per_day} signups per day)"
            
            return True, "Within signup limit"
            
        except Exception as e:
            current_app.logger.error(f"Error checking signup rate limit: {str(e)}")
            return False, "Error checking signup limit"
    
    @staticmethod
    def signup_with_center_code(
        slug: str, 
        token: str, 
        phone_number: str, 
        name: str, 
        center_code: str,
        email: str = None,
        password: str = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Complete signup process with center code verification
        
        Args:
            slug: Organization's unique slug
            token: Security token from URL
            phone_number: User's phone number
            name: User's full name
            center_code: 6-digit verification code
            email: Optional email address
            password: Optional password (if not provided, OTP-only login)
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            # Validate signup link
            is_valid, message, org_data = OrganizationSignupService.validate_signup_link(slug, token)
            if not is_valid:
                return False, message, None
            
            org = Organization.from_dict(org_data)
            
            # Verify center code
            if not org.verify_center_code(center_code):
                return False, "Invalid center code", None
            
            # Check rate limiting
            within_limit, limit_message = OrganizationSignupService.check_signup_rate_limit(str(org._id))
            if not within_limit:
                return False, limit_message, None
            
            # Validate phone number
            if not User.validate_phone_number(phone_number):
                return False, "Invalid phone number format", None
            
            # Normalize phone number
            temp_user = User(phone_number, 'temp')
            normalized_phone = temp_user._normalize_phone_number(phone_number)
            
            # Check if user already exists
            existing_user = mongo.db.users.find_one({'phone_number': normalized_phone})
            if existing_user:
                existing_user_obj = User.from_dict(existing_user)
                
                # If user exists but has no organization, assign them to this one
                if not existing_user_obj.organization_id:
                    mongo.db.users.update_one(
                        {'_id': existing_user['_id']},
                        {
                            '$set': {
                                'organization_id': org._id,
                                'name': name,
                                'email': email,
                                'updated_at': datetime.utcnow(),
                                'verification_status': 'verified'
                            }
                        }
                    )
                    
                    # Update user object
                    existing_user_obj.organization_id = org._id
                    existing_user_obj.name = name
                    existing_user_obj.email = email
                    existing_user_obj.verification_status = 'verified'
                    
                    return True, "User successfully assigned to organization", existing_user_obj.to_dict()
                
                # If user already belongs to this organization
                elif str(existing_user_obj.organization_id) == str(org._id):
                    return False, "User already belongs to this organization", None
                
                # If user belongs to different organization
                else:
                    return False, "Phone number already registered with another organization", None
            
            # Validate email if provided
            if email:
                is_valid_email, email_message = User.validate_email(email)
                if not is_valid_email:
                    return False, email_message, None
            
            # Validate password if provided
            if password:
                is_valid_password, password_message = User.validate_password(password)
                if not is_valid_password:
                    return False, password_message, None
            
            # Create new user
            new_user = User(
                phone_number=normalized_phone,
                name=name,
                role='student',  # Default role for signups
                password=password,
                organization_id=str(org._id)
            )
            
            # Set additional fields
            new_user.email = email
            new_user.verification_status = 'verified'  # Pre-verified through center code
            
            # Parse name into first_name and last_name if possible
            name_parts = name.strip().split(' ', 1)
            new_user.first_name = name_parts[0] if name_parts else ''
            new_user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Insert user into database
            result = mongo.db.users.insert_one(new_user.to_dict(include_sensitive=True))
            new_user._id = result.inserted_id
            
            current_app.logger.info(f"New user signup: {normalized_phone} for organization {org.name}")
            
            return True, "Signup successful", new_user.to_dict()
            
        except Exception as e:
            current_app.logger.error(f"Error in signup process: {str(e)}")
            return False, "Signup failed due to system error", None
    
    @staticmethod
    def get_organization_by_slug(slug: str) -> Optional[Dict]:
        """Get organization details by slug for signup page display"""
        try:
            org_data = mongo.db.organizations.find_one({
                'signup_slug': slug,
                'is_active': True
            })
            
            if org_data:
                # Return only public information
                return {
                    'name': org_data.get('name'),
                    'description': org_data.get('description'),
                    'logo_url': org_data.get('logo_url'),
                    'banner_url': org_data.get('banner_url'),
                    'activities': org_data.get('activities', []),
                    'contact_info': org_data.get('contact_info', {}),
                    'address': org_data.get('address', {})
                }
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error getting organization by slug: {str(e)}")
            return None
    
    @staticmethod
    def generate_new_signup_credentials(organization_id: str, admin_user_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Generate new signup credentials for security (admin only)
        
        Args:
            organization_id: Organization's ID
            admin_user_id: Admin user performing the action
            
        Returns:
            Tuple of (success, message, new_credentials)
        """
        try:
            # Verify admin permissions
            admin_user = mongo.db.users.find_one({'_id': ObjectId(admin_user_id)})
            if not admin_user or admin_user.get('role') not in ['super_admin', 'org_admin']:
                return False, "Insufficient permissions", None
            
            # Get organization
            org_data = mongo.db.organizations.find_one({'_id': ObjectId(organization_id)})
            if not org_data:
                return False, "Organization not found", None
            
            org = Organization.from_dict(org_data)
            
            # Check if admin can manage this organization
            if admin_user.get('role') != 'super_admin':
                if str(admin_user.get('organization_id')) != str(organization_id):
                    return False, "Cannot manage this organization", None
            
            # Generate new credentials
            org.regenerate_signup_credentials()
            
            # Update in database
            mongo.db.organizations.update_one(
                {'_id': ObjectId(organization_id)},
                {
                    '$set': {
                        'signup_slug': org.signup_slug,
                        'signup_token': org.signup_token,
                        'center_code': org.center_code,
                        'updated_at': org.updated_at
                    }
                }
            )
            
            new_credentials = {
                'signup_slug': org.signup_slug,
                'center_code': org.center_code,
                'signup_url': org.get_signup_url()
            }
            
            return True, "New signup credentials generated", new_credentials
            
        except Exception as e:
            current_app.logger.error(f"Error generating new signup credentials: {str(e)}")
            return False, "Error generating credentials", None
