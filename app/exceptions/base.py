"""
Base exception classes for Raphael backend.
All custom exceptions inherit from BaseAPIException for consistent error handling.
"""


class BaseAPIException(Exception):
    """Base exception class for all API exceptions."""
    
    status_code = 500
    message = "An error occurred"
    
    def __init__(self, message=None, status_code=None):
        """
        Initialize exception with optional custom message and status code.
        
        Args:
            message (str, optional): Custom error message
            status_code (int, optional): HTTP status code
        """
        super().__init__()
        if message:
            self.message = message
        if status_code:
            self.status_code = status_code
    
    def to_dict(self):
        """
        Convert exception to dictionary for JSON response.
        
        Returns:
            dict: Error details with message and status code
        """
        return {
            'error': self.message,
            'status_code': self.status_code
        }
    
    def __str__(self):
        return self.message
