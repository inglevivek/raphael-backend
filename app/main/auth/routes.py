"""
Authentication routes with JWT Cookie Support.
✅ WORKS WITH: Updated service.py that returns User objects
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    get_csrf_token
)
from app.exceptions.api_error import APIErrorException
from app.main.auth.service import AuthService
from app.exceptions import APIErrorException


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user and set JWT cookie."""
    try:
        data = request.get_json()

        if not all(k in data for k in ['email', 'password', 'name']):
            raise APIErrorException('Email, password, and name are required', 400)

        # ✅ Service returns User object
        user = AuthService.register(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )

        # ✅ Create token from User object
        access_token = create_access_token(identity=str(user.id))

        # ✅ Convert to dict for JSON response
        response = jsonify({
            'user': user.to_dict(),
            'message': 'Registration successful'
        })

        # ✅ Set JWT in HTTP-only cookie (CSRF token is automatically included in cookie)
        set_access_cookies(response, access_token)
        
        # ✅ Include CSRF token in response header for frontend to read
        # The token can be extracted from the encoded JWT or read from the csrf_access_token cookie
        # Frontend should read from X-CSRF-TOKEN header or csrf_access_token cookie
        try:
            csrf_token = get_csrf_token(access_token)
            response.headers['X-CSRF-TOKEN'] = csrf_token
        except Exception:
            # If CSRF extraction fails, frontend can still get it from /api/auth/csrf-token endpoint
            pass

        return response, 201

    except APIErrorException as e:
        raise e
    except Exception as e:
        raise APIErrorException(f'Registration failed: {str(e)}', 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and set JWT cookie."""
    try:
        data = request.get_json()

        if not all(k in data for k in ['email', 'password']):
            raise APIErrorException('Email and password are required', 400)

        # ✅ Service returns User object
        user = AuthService.login(
            email=data['email'],
            password=data['password']
        )

        # ✅ Create token from User object
        access_token = create_access_token(identity=str(user.id))

        # ✅ Convert to dict for JSON response
        response = jsonify({
            'user': user.to_dict(),
            'message': 'Login successful'
        })

        # ✅ Set JWT in HTTP-only cookie (CSRF token is automatically included in cookie)
        set_access_cookies(response, access_token)
        
        # ✅ Include CSRF token in response header for frontend to read
        # The token can be extracted from the encoded JWT or read from the csrf_access_token cookie
        # Frontend should read from X-CSRF-TOKEN header or csrf_access_token cookie
        try:
            csrf_token = get_csrf_token(access_token)
            response.headers['X-CSRF-TOKEN'] = csrf_token
        except Exception:
            # If CSRF extraction fails, frontend can still get it from /api/auth/csrf-token endpoint
            pass

        return response, 200

    except APIErrorException as e:
        raise e
    except Exception as e:
        raise APIErrorException(f'Login failed: {str(e)}', 500)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current authenticated user."""
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(user_id)

        return jsonify(user.to_dict()), 200

    except APIErrorException as e:
        raise e
    except Exception as e:
        raise APIErrorException(f'Failed to get user: {str(e)}', 500)


@auth_bp.route('/csrf-token', methods=['GET'])
@jwt_required()
def get_csrf_token_endpoint():
    """
    Get CSRF token for authenticated requests.
    
    This endpoint returns the CSRF token that must be included
    in the X-CSRF-TOKEN header for state-changing operations
    (POST, PUT, DELETE) when using cookie-based authentication.
    
    Returns:
        tuple: (response, status_code)
        - 200: CSRF token
        - 401: Unauthorized
    """
    try:
        csrf_token = get_csrf_token()
        response = jsonify({'csrf_token': csrf_token})
        return response, 200
    except Exception as e:
        raise APIErrorException(f'Failed to get CSRF token: {str(e)}', 500)


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user by clearing JWT cookie."""
    try:
        response = jsonify({'message': 'Logout successful'})
        unset_jwt_cookies(response)
        return response, 200

    except Exception as e:
        raise APIErrorException(f'Logout failed: {str(e)}', 500)


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required()
def refresh():
    """Refresh JWT token."""
    try:
        user_id = get_jwt_identity()
        access_token = create_access_token(identity=user_id)

        response = jsonify({'message': 'Token refreshed successfully'})
        set_access_cookies(response, access_token)

        return response, 200

    except Exception as e:
        raise APIErrorException(f'Token refresh failed: {str(e)}', 500)