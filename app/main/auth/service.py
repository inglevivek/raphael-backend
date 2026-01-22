"""
Authentication service layer for business logic.
✅ UPDATED: Returns User objects for cookie-based authentication
"""

import bcrypt
from app.main.auth.repository import AuthRepository
from app.models import User
from app.exceptions import (
    EmailAlreadyExistsException,
    InvalidCredentialsException
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for authentication business logic."""

    @staticmethod
    def register(email: str, password: str, name: str) -> User:
        """
        Register new user with hashed password.

        Args:
            email (str): User email
            password (str): Plain text password
            name (str): User name

        Returns:
            User: User model object (not dict!)

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

        logger.info(f"User registered successfully: {email} (UUID: {user.id})")

        # ✅ Return User object (route will create token and set cookie)
        return user

    @staticmethod
    def login(email: str, password: str) -> User:
        """
        Authenticate user.

        Args:
            email (str): User email
            password (str): Plain text password

        Returns:
            User: User model object (not dict!)

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

        logger.info(f"User logged in successfully: {email} (UUID: {user.id})")

        # ✅ Return User object (route will create token and set cookie)
        return user

    @staticmethod
    def get_user_by_id(user_id: str) -> User:
        """
        Fetch user by ID.

        Args:
            user_id (str): User ID from JWT token (UUID string)

        Returns:
            User: User model object

        Raises:
            NotFoundException: If user not found
        """
        # ✅ Return User object
        return AuthRepository.get_user_by_id(user_id)