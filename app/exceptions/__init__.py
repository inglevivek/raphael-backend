"""
Exception classes for Raphael backend.
Centralized import point for all custom exceptions.
✅ UPDATED: Added Auth0-specific exception exports
"""
from app.exceptions.base import BaseAPIException
from app.exceptions.auth import (
    UnauthorizedException,
    InvalidCredentialsException,
    InvalidTokenException,
    EmailAlreadyExistsException,
    Auth0TokenException,  # ✅ NEW: Auth0 token validation error
    Auth0JWKSException,  # ✅ NEW: Auth0 JWKS fetch error
    Auth0SyncException,  # ✅ NEW: Auth0 user sync error
    ForbiddenException  # ✅ NEW: Permission denied error
)
from app.exceptions.not_found import NotFoundException
from app.exceptions.validation import ValidationException
from app.exceptions.storage import StorageException
from app.exceptions.api_error import APIErrorException

__all__ = [
    # Base
    'BaseAPIException',
    
    # Authentication (existing)
    'UnauthorizedException',
    'InvalidCredentialsException',
    'InvalidTokenException',
    'EmailAlreadyExistsException',
    
    # ✅ NEW: Auth0-specific
    'Auth0TokenException',
    'Auth0JWKSException',
    'Auth0SyncException',
    'ForbiddenException',
    
    # Other
    'NotFoundException',
    'ValidationException',
    'StorageException',
    'APIErrorException'
]
