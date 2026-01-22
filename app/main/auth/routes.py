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
    unset_jwt_cookies
)
from app.exceptions.api_error import APIErrorException
from app.main.auth.service import AuthService
from app.exceptions import APIErrorException


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


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

        # ✅ Set JWT in HTTP-only cookie
        set_access_cookies(response, access_token)

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

        # ✅ Set JWT in HTTP-only cookie
        set_access_cookies(response, access_token)

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