"""
Authentication-related exception classes.
✅ UPDATED: Added Auth0-specific exceptions for JWT token handling
"""
from app.exceptions.base import BaseAPIException


class UnauthorizedException(BaseAPIException):
    """Raised when user is not authorized to access a resource."""
    status_code = 401
    message = "Unauthorized access"


class InvalidCredentialsException(BaseAPIException):
    """Raised when login credentials are invalid."""
    status_code = 401
    message = "Invalid email or password"


class InvalidTokenException(BaseAPIException):
    """Raised when JWT token is invalid or expired."""
    status_code = 401
    message = "Invalid or expired token"


class EmailAlreadyExistsException(BaseAPIException):
    """Raised when attempting to register with an existing email."""
    status_code = 409
    message = "Email already registered"


# ✅ NEW: Auth0-specific exceptions
class Auth0TokenException(UnauthorizedException):
    """
    Raised when Auth0 JWT token validation fails.
    ✅ NEW: Specific to Auth0 token verification errors
    """
    status_code = 401
    message = "Invalid or expired Auth0 token"


class Auth0JWKSException(BaseAPIException):
    """
    Raised when Auth0 JWKS (JSON Web Key Set) fetch fails.
    ✅ NEW: Indicates Auth0 service connectivity issues
    """
    status_code = 503
    message = "Unable to fetch Auth0 public keys"


class Auth0SyncException(BaseAPIException):
    """
    Raised when syncing Auth0 user to local database fails.
    ✅ NEW: Database sync error for Auth0 users
    """
    status_code = 500
    message = "Failed to sync Auth0 user to database"


class ForbiddenException(BaseAPIException):
    """
    Raised when user is authenticated but lacks required permissions.
    ✅ NEW: Used for scope/permission-based access control
    """
    status_code = 403
    message = "You do not have permission to access this resource"
