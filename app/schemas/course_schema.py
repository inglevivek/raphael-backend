"""
Pydantic schemas for course endpoints.
"""
from typing import Literal
from pydantic import BaseModel, field_validator


class CreateCourseSchema(BaseModel):
    """Schema for course creation."""

    title: str
    level: Literal['beginner', 'intermediate', 'advanced']

    @field_validator('title')
    @classmethod
    def title_validation(cls, v: str) -> str:
        """Validate title is not empty and within length limit."""
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        if len(v) > 200:
            raise ValueError('Title must be 200 characters or less')
        return v.strip()