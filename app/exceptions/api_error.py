from app.exceptions.base import BaseAPIException

class APIErrorException(BaseAPIException):
    """
    Generic API error you can raise anywhere.
    Example:
        raise APIErrorException("Course generation failed", 500)
    """

    def __init__(self, message="API Error", status_code=500):
        super().__init__(message=message, status_code=status_code)
