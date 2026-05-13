# backend/routes/auth_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from datetime import timedelta, datetime
from models.user import User
from routes.auth_middleware import jwt_required_custom
import logging
import uuid

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        # Validation
        if not email or not password or not name:
            return jsonify({
                'success': False,
                'error': 'Email, password, and name are required'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 6 characters'
            }), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Create user
        user, error = User.create_user(email, password, name)
        
        if error:
            return jsonify({'success': False, 'error': error}), 409
        
        # Create access token (7 days)
        access_token = create_access_token(
            identity=str(user['_id']),
            expires_delta=timedelta(days=7)
        )
        
        # Create refresh token (30 days)
        refresh_token = str(uuid.uuid4())
        refresh_expires = datetime.utcnow() + timedelta(days=30)
        
        # Store refresh token with validation
        token_stored = User.store_refresh_token(str(user['_id']), refresh_token, refresh_expires)
        if not token_stored:
            logger.warning(f"Failed to store refresh token for user: {user['_id']}")
            # Continue anyway - token still valid, just not persisted for refresh
            # User will need to re-login if session is cleared
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'user': User.to_dict(user),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 7 * 24 * 60 * 60  # 7 days in seconds
        }), 201
        
    except ConnectionError as db_error:
        logger.error(f"Database connection error during registration: {str(db_error)}")
        return jsonify({
            'success': False, 
            'error': 'Database service temporarily unavailable. Please try again in a moment.'
        }), 503
    except Exception as e:
        logger.error(f"Unexpected registration error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Registration failed. Please try again.'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        try:
            # Find user
            user = User.find_by_email(email)
            
            if not user or not User.verify_password(user, password):
                return jsonify({
                    'success': False,
                    'error': 'Invalid email or password'
                }), 401
            
            # Record login activity
            try:
                User.update_login_activity(user['_id'])
            except Exception as activity_error:
                logger.warning(f"Failed to record login activity: {activity_error}")
                # Continue anyway - not critical
            
            # Create access token (7 days)
            access_token = create_access_token(
                identity=str(user['_id']),
                expires_delta=timedelta(days=7)
            )
            
            # Create refresh token (30 days)
            refresh_token = str(uuid.uuid4())
            refresh_expires = datetime.utcnow() + timedelta(days=30)
            
            # Store refresh token with validation
            token_stored = User.store_refresh_token(str(user['_id']), refresh_token, refresh_expires)
            if not token_stored:
                logger.warning(f"Failed to store refresh token for user: {user['_id']}")
                # Continue anyway - token still valid, just not persisted for refresh
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': User.to_dict(user),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': 7 * 24 * 60 * 60  # 7 days in seconds
            }), 200
            
        except ConnectionError as db_error:
            logger.error(f"Database connection error during login: {str(db_error)}")
            return jsonify({
                'success': False, 
                'error': 'Database service temporarily unavailable. Please try again in a moment.'
            }), 503
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Login failed. Please check your connection and try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected login error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Login failed. Please try again.'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required_custom
def get_current_user():
    """Get current authenticated user info"""
    try:
        user_id = get_jwt_identity()
        user = User.find_by_id(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': User.to_dict(user)
        }), 200
        
    except ConnectionError as e:
        print(f"[ERROR] Database error: {e}")
        return jsonify({
            'success': False, 
            'error': 'Database connection error. Please ensure MongoDB is running.'
        }), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Get user failed: {e}")
        return jsonify({'success': False, 'error': 'Failed to get user'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user (client-side token removal)"""
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset user password - requires old password"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        user_id = data.get('user_id', '')
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not user_id or not old_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'user_id, old_password, and new_password are required'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 6 characters'
            }), 400
        
        # Find user and verify old password
        user = User.find_by_id(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        if not User.verify_password(user, old_password):
            return jsonify({
                'success': False,
                'error': 'Old password is incorrect'
            }), 401
        
        # Update password
        if User.update_password(user_id, new_password):
            return jsonify({
                'success': True,
                'message': 'Password updated successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update password'
            }), 500
        
    except Exception as e:
        print(f"[ERROR] Password reset failed: {e}")
        return jsonify({'success': False, 'error': 'Password reset failed'}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Forgot password - reset by email (for demo, just validates email exists)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Find user by email
        user = User.find_by_email(email)
        if not user:
            # For security, don't reveal if email exists
            return jsonify({
                'success': True,
                'message': 'If account exists, password reset instructions have been sent'
            }), 200
        
        # TODO: Send password reset email in production
        # For now, in development, we'll return a reset code
        import secrets
        reset_code = secrets.token_urlsafe(32)
        
        return jsonify({
            'success': True,
            'message': 'Password reset instructions sent to email',
            'reset_code': reset_code,  # In production, don't return this
            'user_id': str(user['_id'])
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Forgot password failed: {e}")
        return jsonify({'success': False, 'error': 'Forgot password request failed'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh_access_token():
    """Refresh access token using refresh token
    
    Request body:
    {
        "user_id": "user_id",
        "refresh_token": "refresh_token"
    }
    
    Response:
    {
        "success": true,
        "access_token": "new_access_token",
        "expires_in": 604800
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        user_id = data.get('user_id', '')
        refresh_token = data.get('refresh_token', '')
        
        if not user_id or not refresh_token:
            return jsonify({
                'success': False,
                'error': 'user_id and refresh_token are required'
            }), 400
        
        # Validate refresh token
        if not User.validate_refresh_token(user_id, refresh_token):
            return jsonify({
                'success': False,
                'error': 'Invalid or expired refresh token. Please log in again.'
            }), 401
        
        # Generate new access token (7 days)
        new_access_token = create_access_token(
            identity=user_id,
            expires_delta=timedelta(days=7)
        )
        
        logger.info(f"[AUTH] Refreshed token for user: {user_id}")
        
        return jsonify({
            'success': True,
            'access_token': new_access_token,
            'expires_in': 7 * 24 * 60 * 60  # 7 days in seconds
        }), 200
        
    except ConnectionError as db_error:
        logger.error(f"Database error during token refresh: {str(db_error)}")
        return jsonify({
            'success': False,
            'error': 'Database service temporarily unavailable. Please try again.'
        }), 503
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Token refresh failed. Please try again.'
        }), 500


@auth_bp.route('/logout-all', methods=['POST'])
@jwt_required_custom
def logout_all():
    """Logout user from all devices by revoking refresh token"""
    try:
        user_id = get_jwt_identity()
        User.revoke_refresh_token(user_id)
        
        logger.info(f"[AUTH] User logged out from all devices: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Logged out from all devices'
        }), 200
        
    except Exception as e:
        logger.error(f"Logout all error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500