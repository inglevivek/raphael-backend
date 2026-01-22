"""
Exception classes for Raphael backend.
Centralized import point for all custom exceptions.
"""
from app.exceptions.base import BaseAPIException
from app.exceptions.auth import (
    UnauthorizedException,
    InvalidCredentialsException,
    InvalidTokenException,
    EmailAlreadyExistsException
)
from app.exceptions.not_found import NotFoundException
from app.exceptions.validation import ValidationException
from app.exceptions.storage import StorageException
from app.exceptions.api_error import APIErrorException

__all__ = [
    'BaseAPIException',
    'UnauthorizedException',
    'InvalidCredentialsException',
    'InvalidTokenException',
    'EmailAlreadyExistsException',
    'NotFoundException',
    'ValidationException',
    'StorageException',
    'APIErrorException'
]
