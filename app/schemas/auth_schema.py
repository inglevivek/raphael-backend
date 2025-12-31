"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, field_validator


class RegisterSchema(BaseModel):
    """Schema for user registration."""
    
    email: EmailStr
    password: str
    name: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password has minimum 8 characters."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()


class LoginSchema(BaseModel):
    """Schema for user login."""
    
    email: EmailStr
    password: str
