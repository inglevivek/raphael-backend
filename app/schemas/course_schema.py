"""
Pydantic schemas for course endpoints.
"""
from typing import Literal
from pydantic import BaseModel, field_validator


class CreateCourseSchema(BaseModel):
    """Schema for course creation."""
    
    topic: str
    level: Literal['beginner', 'intermediate', 'advanced']
    
    @field_validator('topic')
    @classmethod
    def topic_validation(cls, v: str) -> str:
        """Validate topic is not empty and within length limit."""
        if not v or not v.strip():
            raise ValueError('Topic cannot be empty')
        if len(v) > 200:
            raise ValueError('Topic must be 200 characters or less')
        return v.strip()
