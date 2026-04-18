"""
Authentication service layer for business logic.
Primary auth goes through Auth0. Legacy password methods kept as fallback.
"""
import bcrypt
from typing import Dict, Any
from app.main.auth.repository import AuthRepository
from app.models import User
from app.exceptions import (
    EmailAlreadyExistsException,
    InvalidCredentialsException,
    NotFoundException
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:

    @staticmethod
    def register(email: str, password: str, name: str) -> User:
        """Register new user with hashed password. Fallback if Auth0 is down."""
        if AuthRepository.email_exists(email):
            logger.warning(f"Registration attempt with existing email: {email}")
            raise EmailAlreadyExistsException(f"Email {email} is already registered")

        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        user = AuthRepository.create_user(email, password_hash, name)
        logger.info(f"User registered (legacy): {email} (UUID: {user.id})")
        return user

    @staticmethod
    def login(email: str, password: str) -> User:
        """Authenticate user with password. Fallback if Auth0 is down."""
        try:
            user = AuthRepository.get_user_by_email(email)
        except Exception:
            raise InvalidCredentialsException()

        if not bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8')
        ):
            logger.warning(f"Invalid password attempt for: {email}")
            raise InvalidCredentialsException()

        AuthRepository.update_last_login(user.id)
        logger.info(f"User logged in (legacy): {email} (UUID: {user.id})")
        return user

    @staticmethod
    def process_auth0_login(auth0_claims: Dict[str, Any]) -> User:
        """
        Process Auth0 JWT claims and upsert user into local database.
        Primary login method for all Auth0-based authentication.

        Access tokens from Google OAuth2 via Auth0 do NOT include email
        by default — all claims are handled defensively.
        """
        auth0_user_id = auth0_claims.get('sub')

        # sub is the only truly required claim — everything else is derived
        if not auth0_user_id:
            logger.error(f"Missing sub claim in token: {auth0_claims}")
            raise ValueError("Invalid Auth0 claims: missing sub")

        # Email: present in ID tokens, absent in raw Google access tokens
        email = (
            auth0_claims.get('email')
            or auth0_claims.get('https://raphael.app/email')
        )
        if not email:
            # Stable placeholder — same user always gets same placeholder email
            email = f"{auth0_user_id.replace('|', '_')}@oauth.raphael.local"
            logger.warning(
                f"No email in token for {auth0_user_id} — "
                f"using placeholder: {email}"
            )

        # Name: prefer real name, fall back to email prefix, then sub suffix
        name = (
            auth0_claims.get('name')
            or auth0_claims.get('https://raphael.app/name')
            or (email.split('@')[0] if email and '@' in email else None)
            or auth0_user_id.split('|')[-1]
        )

        picture = (
            auth0_claims.get('picture')
            or auth0_claims.get('https://raphael.app/picture')
        )
        email_verified = auth0_claims.get('email_verified', False)

        logger.info(f"Processing Auth0 login: {email} (sub: {auth0_user_id})")

        user = AuthRepository.sync_user_from_auth0(
            auth0_user_id=auth0_user_id,
            email=email,
            name=name,
            password_hash=None,
            picture=picture,
            email_verified=email_verified
        )

        logger.info(f"Auth0 user synced: {email} (DB UUID: {user.id})")
        return user

    @staticmethod
    def get_user_by_id(user_id: str) -> User:
        """Fetch user by Auth0 ID or internal UUID. Tries Auth0 ID first."""
        user = AuthRepository.get_user_by_auth0_id(user_id)
        if user:
            return user

        try:
            return AuthRepository.get_user_by_id(user_id)
        except NotFoundException:
            logger.warning(f"User not found: {user_id}")
            raise NotFoundException(f"User with ID {user_id} not found")

    @staticmethod
    def get_user_by_auth0_id(auth0_user_id: str) -> User:
        """Fetch user by Auth0 sub claim directly."""
        user = AuthRepository.get_user_by_auth0_id(auth0_user_id)
        if not user:
            logger.warning(f"No user found with Auth0 ID: {auth0_user_id}")
            raise NotFoundException(f"User with Auth0 ID {auth0_user_id} not found")
        return user