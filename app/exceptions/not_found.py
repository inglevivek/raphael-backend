"""
Not found exception class.
"""
from app.exceptions.base import BaseAPIException


class NotFoundException(BaseAPIException):
    """Raised when a requested resource is not found."""
    
    status_code = 404
    message = "Resource not found"
