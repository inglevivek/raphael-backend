"""
Authentication service layer for business logic.
"""
import bcrypt
from flask_jwt_extended import create_access_token
from app.main.auth.repository import AuthRepository
from app.exceptions import (
    EmailAlreadyExistsException,
    InvalidCredentialsException
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


class AuthService:
    """Service for authentication business logic."""
    
    @staticmethod
    def register(email: str, password: str, name: str) -> dict:
        """
        Register new user with hashed password.
        
        Args:
            email (str): User email
            password (str): Plain text password
            name (str): User name
        
        Returns:
            dict: {user: dict, token: str}
        
        Raises:
            EmailAlreadyExistsException: If email already registered
        """
        # Check if email exists
        if AuthRepository.email_exists(email):
            logger.warning(f"Registration attempt with existing email: {email}")
            raise EmailAlreadyExistsException(f"Email {email} is already registered")
        
        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        
        # Create user
        user = AuthRepository.create_user(email, password_hash, name)
        
        # Generate JWT token
        token = create_access_token(identity=str(user.id))
        
        logger.info(f"User registered successfully: {email}")
        return {
            'user': user.to_dict(),
            'token': token
        }
    
    @staticmethod
    def login(email: str, password: str) -> dict:
        """
        Authenticate user and generate token.
        
        Args:
            email (str): User email
            password (str): Plain text password
        
        Returns:
            dict: {user: dict, token: str}
        
        Raises:
            InvalidCredentialsException: If credentials are invalid
        """
        try:
            # Get user by email
            user = AuthRepository.get_user_by_email(email)
        except Exception:
            raise InvalidCredentialsException()
        
        # Verify password
        if not bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8')
        ):
            logger.warning(f"Invalid password attempt for: {email}")
            raise InvalidCredentialsException()
        
        # Generate JWT token
        token = create_access_token(identity=str(user.id))
        
        logger.info(f"User logged in successfully: {email}")
        return {
            'user': user.to_dict(),
            'token': token
        }
    
    @staticmethod
    def get_current_user(user_id: int) -> dict:
        """
        Fetch current user details.
        
        Args:
            user_id (int): User ID from JWT token
        
        Returns:
            dict: User data
        
        Raises:
            NotFoundException: If user not found
        """
        user = AuthRepository.get_user_by_id(user_id)
        return user.to_dict()
