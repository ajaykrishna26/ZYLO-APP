
# backend/models/user.py
from datetime import datetime
import bcrypt
from bson import ObjectId
from db import get_users_collection

class User:
    """User model for authentication"""
    
    @staticmethod
    def create_user(email, password, name):
        """Create a new user with hashed password"""
        try:
            users = get_users_collection()
            
            # Check if user already exists
            existing = users.find_one({'email': email.lower()})
            if existing:
                return None, "Email already registered"
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            user_doc = {
                'email': email.lower(),
                'password_hash': password_hash,
                'name': name,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'login_count': 0
            }
            
            result = users.insert_one(user_doc)
            user_doc['_id'] = result.inserted_id
            return user_doc, None
        except Exception as e:
            print(f"[ERROR] Failed to create user: {e}")
            return None, "Failed to create account. Please try again."
    
    @staticmethod
    def find_by_email(email):
        """Find user by email with error handling"""
        try:
            users = get_users_collection()
            return users.find_one({'email': email.lower()})
        except Exception as e:
            print(f"[ERROR] Failed to find user by email: {e}")
            raise ConnectionError(f"Database error: {e}")
    
    @staticmethod
    def find_by_id(user_id):
        """Find user by ID with proper error handling"""
        try:
            users = get_users_collection()
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except Exception as e:
                    print(f"[ERROR] Invalid user ID format: {user_id} - {e}")
                    return None
            return users.find_one({'_id': user_id})
        except Exception as e:
            print(f"[ERROR] Database error finding user by ID: {e}")
            raise ConnectionError(f"Database error: {e}")
    
    @staticmethod
    def verify_password(user, password):
        """Verify user password"""
        if not user or 'password_hash' not in user:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), user['password_hash'])

    @staticmethod
    def update_login_activity(user_id):
        """Record login timestamp and increment login count"""
        try:
            users = get_users_collection()
            users.update_one(
                {'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id},
                {
                    '$set': {'last_login': datetime.utcnow()},
                    '$inc': {'login_count': 1}
                }
            )
        except Exception as e:
            print(f"[WARNING] Failed to update login activity: {e}")
            # Not critical - continue
    
    @staticmethod
    def update_password(user_id, new_password):
        """Update user password with error handling"""
        try:
            users = get_users_collection()
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            result = users.update_one(
                {'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id},
                {
                    '$set': {
                        'password_hash': password_hash,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[ERROR] Failed to update password: {e}")
            raise ConnectionError(f"Database error: {e}")
    
    @staticmethod
    def store_refresh_token(user_id, refresh_token, expires_at):
        """Store refresh token for user with error handling"""
        try:
            users = get_users_collection()
            result = users.update_one(
                {'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id},
                {
                    '$set': {
                        'refresh_token': refresh_token,
                        'refresh_token_expires': expires_at,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            if result.matched_count == 0:
                print(f"[ERROR] User not found when storing refresh token: {user_id}")
                return False
            return result.modified_count > 0
        except Exception as e:
            print(f"[ERROR] Failed to store refresh token: {e}")
            return False
    
    @staticmethod
    def get_refresh_token(user_id):
        """Get stored refresh token for user"""
        users = get_users_collection()
        user = users.find_one({'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id})
        if user and 'refresh_token' in user:
            return user.get('refresh_token'), user.get('refresh_token_expires')
        return None, None
    
    @staticmethod
    def validate_refresh_token(user_id, refresh_token):
        """Validate that stored refresh token matches and hasn't expired"""
        try:
            users = get_users_collection()
            user = users.find_one({'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id})
            
            if not user:
                print(f"[WARNING] User not found for token validation: {user_id}")
                return False
                
            if 'refresh_token' not in user:
                print(f"[WARNING] No refresh token stored for user: {user_id}")
                return False
            
            stored_token = user.get('refresh_token')
            expires_at = user.get('refresh_token_expires')
            
            # Check if token matches
            if stored_token != refresh_token:
                print(f"[WARNING] Refresh token mismatch for user: {user_id}")
                return False
            
            # Check if token has expired
            if expires_at and isinstance(expires_at, datetime):
                if datetime.utcnow() > expires_at:
                    print(f"[WARNING] Refresh token expired for user: {user_id}")
                    return False
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to validate refresh token: {e}")
            return False
    
    @staticmethod
    def revoke_refresh_token(user_id):
        """Revoke refresh token with error handling"""
        try:
            users = get_users_collection()
            result = users.update_one(
                {'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id},
                {
                    '$unset': {
                        'refresh_token': 1,
                        'refresh_token_expires': 1
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[ERROR] Failed to revoke refresh token: {e}")
            return False
    
    @staticmethod
    def to_dict(user):
        """Convert user document to dict (excluding password)"""
        if not user:
            return None
            
        def safe_iso(dt):
            if hasattr(dt, 'isoformat'):
                return dt.isoformat()
            elif isinstance(dt, str):
                return dt
            return None
            
        return {
            'id': str(user.get('_id', '')),
            'email': user.get('email', ''),
            'name': user.get('name', ''),
            'created_at': safe_iso(user.get('created_at')),
            'last_login': safe_iso(user.get('last_login')),
            'login_count': user.get('login_count', 0)
        }
