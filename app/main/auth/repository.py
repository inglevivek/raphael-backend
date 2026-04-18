"""
Authentication repository layer for database operations.
Migrated from Flask-SQLAlchemy to plain SQLAlchemy 2.0 session patterns.
"""
from typing import Union, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from app.models import User
from app.database import SessionLocal
from app.exceptions import NotFoundException
from app.utils.logger import get_logger
from sqlalchemy.exc import IntegrityError
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
        with SessionLocal() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if not user:
                logger.warning(f"User not found with email: {email}")
                raise NotFoundException(f"User with email {email} not found")
            session.expunge(user)
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
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                logger.warning(f"Invalid UUID format: {user_id}")
                raise NotFoundException(f"User with ID {user_id} not found")

        with SessionLocal() as session:
            user = session.get(User, user_id)
            if not user:
                logger.warning(f"User not found with ID: {user_id}")
                raise NotFoundException(f"User with ID {user_id} not found")
            session.expunge(user)
            return user

    @staticmethod
    def get_user_by_auth0_id(auth0_user_id: str) -> Optional[User]:
        """
        Fetch user by Auth0 user ID (sub claim).

        Args:
            auth0_user_id (str): Auth0 user ID

        Returns:
            User: User object or None if not found
        """
        with SessionLocal() as session:
            user = session.execute(
                select(User).where(User.auth0_user_id == auth0_user_id)
            ).scalar_one_or_none()
            if user:
                logger.debug(f"Found user by Auth0 ID: {auth0_user_id}")
                session.expunge(user)
            else:
                logger.debug(f"No user found with Auth0 ID: {auth0_user_id}")
            return user

    @staticmethod
    def create_user(email: str, password_hash: str, name: str,
                    auth0_user_id: Optional[str] = None,
                    picture: Optional[str] = None,
                    email_verified: bool = False) -> User:
        """
        Create new user in database.

        Args:
            email (str): User email
            password_hash (str): Hashed password
            name (str): User name
            auth0_user_id (str, optional): Auth0 user ID for linking
            picture (str, optional): Profile picture URL from Auth0
            email_verified (bool): Email verification status

        Returns:
            User: Created user object
        """
        try:
            with SessionLocal() as session:
                user = User(
                    email=email,
                    password_hash=password_hash,
                    name=name,
                    auth0_user_id=auth0_user_id,
                    picture=picture,
                    email_verified=email_verified,
                    last_login_at=datetime.now(timezone.utc)
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.info(f"Created user: {email} (UUID: {user.id}, Auth0: {auth0_user_id})")
                session.expunge(user)
                return user
        except Exception as e:
            logger.error(f"Failed to create user {email}: {str(e)}")
            raise

    @staticmethod
    def sync_user_from_auth0(auth0_user_id: str, email: str, name: str,
                          password_hash: Optional[str] = None,
                          picture: Optional[str] = None,
                          email_verified: bool = False) -> User:
        try:
            with SessionLocal() as session:
                user = session.execute(
                    select(User).where(User.auth0_user_id == auth0_user_id)
                ).scalar_one_or_none()

                if user:
                    logger.info(f"Syncing existing user: {email} (Auth0: {auth0_user_id})")
                    user.email = email
                    user.name = name
                    if password_hash:
                        user.password_hash = password_hash
                    if picture:
                        user.picture = picture
                    user.email_verified = email_verified
                    user.last_login_at = datetime.now(timezone.utc)
                    user.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    session.refresh(user)
                    session.expunge(user)
                    logger.info(f"Updated user {email} from Auth0")
                    return user
                else:
                    logger.info(f"Creating new user from Auth0: {email}")
                    user = User(
                        email=email,
                        password_hash=password_hash or '',
                        name=name,
                        auth0_user_id=auth0_user_id,
                        picture=picture,
                        email_verified=email_verified,
                        last_login_at=datetime.now(timezone.utc)
                    )
                    session.add(user)
                    try:
                        session.commit()
                    except IntegrityError:
                        # Race condition: another request inserted first — fetch and return it
                        session.rollback()
                        logger.warning(f"Race condition on insert for {auth0_user_id} — fetching existing")
                        user = session.execute(
                            select(User).where(User.auth0_user_id == auth0_user_id)
                        ).scalar_one()
                        session.expunge(user)
                        return user

                    session.refresh(user)
                    session.expunge(user)
                    logger.info(f"Created new user {email} from Auth0")
                    return user

        except Exception as e:
            logger.error(f"Failed to sync user from Auth0: {str(e)}")
            raise

    @staticmethod
    def update_last_login(user_id: Union[str, UUID]) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id (str | UUID): User ID
        """
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                return
        try:
            with SessionLocal() as session:
                user = session.get(User, user_id)
                if user:
                    user.last_login_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.debug(f"Updated last login for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to update last login: {str(e)}")

    @staticmethod
    def email_exists(email: str) -> bool:
        """
        Check if email is already registered.

        Args:
            email (str): Email address to check

        Returns:
            bool: True if email exists, False otherwise
        """
        with SessionLocal() as session:
            return session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none() is not None

    @staticmethod
    def auth0_user_exists(auth0_user_id: str) -> bool:
        """
        Check if Auth0 user ID already exists in database.

        Args:
            auth0_user_id (str): Auth0 user ID

        Returns:
            bool: True if exists, False otherwise
        """
        with SessionLocal() as session:
            return session.execute(
                select(User).where(User.auth0_user_id == auth0_user_id)
            ).scalar_one_or_none() is not None
