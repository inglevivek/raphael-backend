"""
Validation exception class.
"""
from app.exceptions.base import BaseAPIException


class ValidationException(BaseAPIException):
    """Raised when request validation fails."""
    
    status_code = 400
    message = "Validation error"
