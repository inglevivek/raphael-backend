"""
Authentication-related exception classes.
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
