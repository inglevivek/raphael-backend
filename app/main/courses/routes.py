"""
Course management routes - FastAPI version.
"""
from uuid import UUID
from fastapi import APIRouter, Depends

from app.schemas.course_schema import CreateCourseSchema
from app.main.auth.auth0_utils import get_auth0_user_id
from app.main.courses.service import CoursesService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Courses"])


@router.post("/", status_code=201)
def create_course(body: CreateCourseSchema, auth0_user_id: str = Depends(get_auth0_user_id)):
    """Create new course and start generation pipeline."""
    from app.main.auth.service import AuthService
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    result = CoursesService.create_course(
        user_id=str(user.id),
        title=body.title,
        level=body.level
    )
    logger.info(f"Course created by Auth0 user {auth0_user_id}: {result['id']}")
    return result


@router.get("/")
def list_courses(auth0_user_id: str = Depends(get_auth0_user_id)):
    """List all courses for the authenticated user."""
    from app.main.auth.service import AuthService
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    result = CoursesService.get_user_courses(str(user.id))
    logger.debug(f"Fetched {len(result)} courses for Auth0 user: {auth0_user_id}")
    return result


@router.get("/{course_id}")
def get_course(course_id: UUID, auth0_user_id: str = Depends(get_auth0_user_id)):
    """Get course details for status polling."""
    from app.main.auth.service import AuthService
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    result = CoursesService.get_course_details(str(user.id), course_id)
    return result


@router.get("/{course_id}/content")
def get_course_content(course_id: UUID, auth0_user_id: str = Depends(get_auth0_user_id)):
    """Get course with full content."""
    from app.main.auth.service import AuthService
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    result = CoursesService.get_course_content(str(user.id), course_id)
    return result


@router.delete("/{course_id}")
def delete_course(course_id: UUID, auth0_user_id: str = Depends(get_auth0_user_id)):
    """Delete a course."""
    from app.main.auth.service import AuthService
    user = AuthService.get_user_by_auth0_id(auth0_user_id)
    CoursesService.delete_course(str(user.id), course_id)
    logger.info(f"Deleted course {course_id} for Auth0 user: {auth0_user_id}")
    return {"message": "Course deleted successfully"}
