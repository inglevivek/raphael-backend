"""
Authentication service layer for business logic.
✅ UPDATED: Added Auth0 JWT handling and user sync
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
    """Service for authentication business logic."""
    
    # ✅ KEPT: Legacy password-based registration (for backup/fallback)
    @staticmethod
    def register(email: str, password: str, name: str) -> User:
        """
        Register new user with hashed password.
        ✅ NOTE: This is now a FALLBACK method if Auth0 is down
        Primary registration should go through Auth0
        
        Args:
            email (str): User email
            password (str): Plain text password
            name (str): User name
            
        Returns:
            User: User model object
            
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
        
        # Create user (without Auth0 ID for legacy/fallback)
        user = AuthRepository.create_user(email, password_hash, name)
        logger.info(f"User registered successfully (legacy): {email} (UUID: {user.id})")
        
        return user
    
    # ✅ KEPT: Legacy password-based login (for backup/fallback)
    @staticmethod
    def login(email: str, password: str) -> User:
        """
        Authenticate user with password.
        ✅ NOTE: This is now a FALLBACK method if Auth0 is down
        Primary login should go through Auth0
        
        Args:
            email (str): User email
            password (str): Plain text password
            
        Returns:
            User: User model object
            
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
        
        # ✅ ADDED: Update last login timestamp
        AuthRepository.update_last_login(user.id)
        
        logger.info(f"User logged in successfully (legacy): {email} (UUID: {user.id})")
        return user
    
    # ✅ NEW METHOD: Process Auth0 login and sync to database
    @staticmethod
    def process_auth0_login(auth0_claims: Dict[str, Any]) -> User:
        """
        Process Auth0 JWT claims and sync user to local database.
        ✅ PRIMARY LOGIN METHOD: Handles Auth0 authentication
        This ensures local database always has user data as backup
        
        Args:
            auth0_claims (dict): Verified JWT claims from Auth0
                - sub: Auth0 user ID (e.g., "auth0|123" or "google-oauth2|456")
                - email: User email
                - name: User display name
                - picture: Profile picture URL
                - email_verified: Email verification status
                
        Returns:
            User: User object (synced to local database)
            
        Raises:
            ValueError: If required claims are missing
        """
        # Extract required claims
        auth0_user_id = auth0_claims.get('sub')
        email = auth0_claims.get('email')
        name = auth0_claims.get('name') or email.split('@')[0]  # Fallback to email username
        
        if not auth0_user_id or not email:
            logger.error(f"Missing required Auth0 claims: {auth0_claims}")
            raise ValueError("Invalid Auth0 claims: missing sub or email")
        
        # Extract optional claims
        picture = auth0_claims.get('picture')
        email_verified = auth0_claims.get('email_verified', False)
        
        logger.info(f"Processing Auth0 login for: {email} (Auth0 ID: {auth0_user_id})")
        
        # ✅ SYNC TO DATABASE: Create or update user
        # This ensures we have local backup even if Auth0 goes down
        user = AuthRepository.sync_user_from_auth0(
            auth0_user_id=auth0_user_id,
            email=email,
            name=name,
            password_hash=None,  # Auth0 manages passwords, we don't store them
            picture=picture,
            email_verified=email_verified
        )
        
        logger.info(f"Auth0 user synced to database: {email} (DB ID: {user.id})")
        return user
    
    # ✅ MODIFIED: Now supports both Auth0 ID and internal UUID
    @staticmethod
    def get_user_by_id(user_id: str) -> User:
        """
        Fetch user by ID (supports both internal UUID and Auth0 ID).
        ✅ UPDATED: Intelligent lookup - tries Auth0 ID first, then UUID
        
        Args:
            user_id (str): User ID (Auth0 ID or internal UUID string)
            
        Returns:
            User: User model object
            
        Raises:
            NotFoundException: If user not found
        """
        # ✅ TRY AUTH0 ID FIRST (most common for JWT-based auth)
        user = AuthRepository.get_user_by_auth0_id(user_id)
        if user:
            return user
        
        # ✅ FALLBACK TO INTERNAL UUID (for legacy/direct DB access)
        try:
            return AuthRepository.get_user_by_id(user_id)
        except NotFoundException:
            logger.warning(f"User not found with ID: {user_id} (tried Auth0 ID and UUID)")
            raise NotFoundException(f"User with ID {user_id} not found")
    
    # ✅ NEW METHOD: Get user from Auth0 user ID specifically
    @staticmethod
    def get_user_by_auth0_id(auth0_user_id: str) -> User:
        """
        Fetch user by Auth0 user ID.
        ✅ NEW: Direct Auth0 ID lookup
        
        Args:
            auth0_user_id (str): Auth0 user ID (sub claim)
            
        Returns:
            User: User model object
            
        Raises:
            NotFoundException: If user not found
        """
        user = AuthRepository.get_user_by_auth0_id(auth0_user_id)
        if not user:
            logger.warning(f"No user found with Auth0 ID: {auth0_user_id}")
            raise NotFoundException(f"User with Auth0 ID {auth0_user_id} not found")
        return user
