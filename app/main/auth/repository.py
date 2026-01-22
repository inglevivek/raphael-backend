"""
Authentication repository layer for database operations.
"""
from typing import Union
from uuid import UUID
from app.models import User
from app import db
from app.exceptions import NotFoundException
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthRepository:
    """Repository for user-related database operations."""

    @staticmethod
    def get_user_by_email(email: str) -> User:
        """
        Fetch user by email address.

        Args:
            email (str): User email address

        Returns:
            User: User object

        Raises:
            NotFoundException: If user not found
        """
        user = User.query.filter_by(email=email).first()
        if not user:
            logger.warning(f"User not found with email: {email}")
            raise NotFoundException(f"User with email {email} not found")
        return user

    @staticmethod
    def get_user_by_id(user_id: Union[str, UUID]) -> User:
        """
        Fetch user by ID (UUID).

        Args:
            user_id (str | UUID): User ID (UUID string or UUID object)

        Returns:
            User: User object

        Raises:
            NotFoundException: If user not found
        """
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                logger.warning(f"Invalid UUID format: {user_id}")
                raise NotFoundException(f"User with ID {user_id} not found")

        user = User.query.get(user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise NotFoundException(f"User with ID {user_id} not found")
        return user

    @staticmethod
    def create_user(email: str, password_hash: str, name: str) -> User:
        """
        Create new user in database.

        Args:
            email (str): User email
            password_hash (str): Hashed password
            name (str): User name

        Returns:
            User: Created user object

        Raises:
            Exception: If database commit fails
        """
        try:
            user = User(
                email=email,
                password_hash=password_hash,
                name=name
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"Created user: {email} (ID: {user.id})")
            return user
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create user {email}: {str(e)}")
            raise

    @staticmethod
    def email_exists(email: str) -> bool:
        """
        Check if email is already registered.

        Args:
            email (str): Email address to check

        Returns:
            bool: True if email exists, False otherwise
        """
        return User.query.filter_by(email=email).first() is not None