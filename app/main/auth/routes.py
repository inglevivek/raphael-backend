"""
Simple authentication routes with password verification.
"""

from flask import Blueprint, request, jsonify
from app.exceptions.api_error import APIErrorException
from app.main.auth.service import AuthService


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user."""
    try:
        data = request.get_json()

        if not all(k in data for k in ['email', 'password', 'name']):
            raise APIErrorException('Email, password, and name are required', 400)

        user = AuthService.register(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )

        return jsonify({
            'user': user.to_dict(),
            'message': 'Registration successful'
        }), 201

    except APIErrorException as e:
        raise e
    except Exception as e:
        raise APIErrorException(f'Registration failed: {str(e)}', 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user - verify password matches database."""
    try:
        data = request.get_json()

        if not all(k in data for k in ['email', 'password']):
            raise APIErrorException('Email and password are required', 400)

        user = AuthService.login(
            email=data['email'],
            password=data['password']
        )

        return jsonify({
            'user': user.to_dict(),
            'message': 'Login successful'
        }), 200

    except APIErrorException as e:
        raise e
    except Exception as e:
        raise APIErrorException(f'Login failed: {str(e)}', 500)
