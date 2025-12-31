"""
Storage-related exception class.
"""
from app.exceptions.base import BaseAPIException


class StorageException(BaseAPIException):
    """Raised when file storage operations fail."""
    
    status_code = 500
    message = "Storage operation failed"
