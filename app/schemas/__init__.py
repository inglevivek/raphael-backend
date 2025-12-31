"""
Pydantic schemas for request validation.
"""
from app.schemas.auth_schema import RegisterSchema, LoginSchema
from app.schemas.course_schema import CreateCourseSchema


__all__ = [
    'RegisterSchema',
    'LoginSchema',
    'CreateCourseSchema'
]
