"""
Authentication routes for user registration and login.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.main.auth.service import AuthService
from app.schemas import RegisterSchema, LoginSchema
from app.utils.decorators import handle_errors, validate_schema
from app.utils.logger import get_logger


logger = get_logger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
@handle_errors
@validate_schema(RegisterSchema)
def register():
    """
    Register new user endpoint.
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "password123",
            "name": "John Doe"
        }
    
    Returns:
        tuple: (response, status_code)
        - 201: User created successfully
        - 400: Validation error
        - 409: Email already exists
    """
    data = request.validated_data
    result = AuthService.register(
        email=data['email'],
        password=data['password'],
        name=data['name']
    )
    return jsonify(result), 201


@auth_bp.route('/login', methods=['POST'])
@handle_errors
@validate_schema(LoginSchema)
def login():
    """
    User login endpoint.
    
    Request Body:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    
    Returns:
        tuple: (response, status_code)
        - 200: Login successful
        - 401: Invalid credentials
    """
    data = request.validated_data
    result = AuthService.login(
        email=data['email'],
        password=data['password']
    )
    return jsonify(result), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
@handle_errors
def get_me():
    """
    Get current user details endpoint.
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        tuple: (response, status_code)
        - 200: User details retrieved
        - 401: Invalid/missing token
    """
    user_id = get_jwt_identity()
    user = AuthService.get_current_user(user_id)
    return jsonify(user), 200
