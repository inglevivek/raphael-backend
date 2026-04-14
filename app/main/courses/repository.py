"""
Courses repository layer for database operations with UUID support.
Migrated from Flask-SQLAlchemy to plain SQLAlchemy 2.0 session patterns.
"""
from typing import List, Union
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from app.models import Course, CourseCheckpoint
from app.database import SessionLocal
from app.exceptions import NotFoundException
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CoursesRepository:
    """Repository for course-related database operations."""

    @staticmethod
    def get_by_id(course_id: Union[str, UUID]) -> Course:
        """
        Fetch course by ID (UUID).

        Args:
            course_id (str | UUID): Course ID

        Returns:
            Course: Course object

        Raises:
            NotFoundException: If course not found
        """
        if isinstance(course_id, str):
            try:
                course_id = UUID(course_id)
            except ValueError:
                logger.warning(f"Invalid UUID format: {course_id}")
                raise NotFoundException(f"Course with ID {course_id} not found")

        with SessionLocal() as session:
            course = session.get(Course, course_id)
            if not course:
                logger.warning(f"Course not found with ID: {course_id}")
                raise NotFoundException(f"Course with ID {course_id} not found")
            session.expunge(course)
            return course

    @staticmethod
    def get_all_by_user(user_id: Union[str, UUID]) -> List[Course]:
        """
        Fetch all courses for a user, ordered by created_at desc.

        Args:
            user_id (str | UUID): User ID

        Returns:
            List[Course]: List of course objects
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        with SessionLocal() as session:
            courses = session.execute(
                select(Course)
                .where(Course.user_id == user_id)
                .order_by(Course.created_at.desc())
            ).scalars().all()
            for course in courses:
                session.expunge(course)
            return list(courses)

    @staticmethod
    def create(user_id: Union[str, UUID], title: str, level: str, course_json: dict) -> Course:
        """
        Create new course record with status=generating.

        Args:
            user_id (str | UUID): User ID
            title (str): Course title
            level (str): Course level
            course_json (dict): Complete course JSON structure

        Returns:
            Course: Created course object
        """
        try:
            if isinstance(user_id, str):
                user_id = UUID(user_id)

            with SessionLocal() as session:
                course = Course(
                    user_id=user_id,
                    title=title,
                    level=level,
                    status='generating',
                    course_json=course_json
                )
                session.add(course)
                session.commit()
                session.refresh(course)
                logger.info(f"Created course {course.id}: {title}")
                session.expunge(course)
                return course
        except Exception as e:
            logger.error(f"Failed to create course: {str(e)}")
            raise

    @staticmethod
    def update_course_json(course_id: Union[str, UUID], course_json: dict,
                           total_modules: int = None, total_chapters: int = None,
                           total_topics: int = None, estimated_minutes: int = None) -> None:
        """Update course JSON and metadata."""
        try:
            if isinstance(course_id, str):
                course_id = UUID(course_id)
            with SessionLocal() as session:
                course = session.get(Course, course_id)
                if not course:
                    raise NotFoundException(f"Course {course_id} not found")
                course.course_json = course_json
                if total_modules is not None:
                    course.total_modules = total_modules
                if total_chapters is not None:
                    course.total_chapters = total_chapters
                if total_topics is not None:
                    course.total_topics = total_topics
                if estimated_minutes is not None:
                    course.estimated_minutes = estimated_minutes
                session.commit()
                logger.info(f"Updated course_json for course {course_id}")
        except Exception as e:
            logger.error(f"Failed to update course_json for {course_id}: {str(e)}")
            raise

    @staticmethod
    def update_status(course_id: Union[str, UUID], status: str) -> None:
        """Update course status."""
        try:
            if isinstance(course_id, str):
                course_id = UUID(course_id)
            with SessionLocal() as session:
                course = session.get(Course, course_id)
                if not course:
                    raise NotFoundException(f"Course {course_id} not found")
                course.status = status
                session.commit()
                logger.info(f"Updated course {course_id} status to: {status}")
        except Exception as e:
            logger.error(f"Failed to update course {course_id} status: {str(e)}")
            raise

    @staticmethod
    def mark_completed(course_id: Union[str, UUID]) -> None:
        """Mark course as completed."""
        try:
            if isinstance(course_id, str):
                course_id = UUID(course_id)
            with SessionLocal() as session:
                course = session.get(Course, course_id)
                if not course:
                    raise NotFoundException(f"Course {course_id} not found")
                course.status = 'completed'
                course.completed_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Marked course {course_id} as completed")
        except Exception as e:
            logger.error(f"Failed to mark course {course_id} as completed: {str(e)}")
            raise

    @staticmethod
    def mark_failed(course_id: Union[str, UUID], error_message: str) -> None:
        """Mark course as failed with error message."""
        try:
            if isinstance(course_id, str):
                course_id = UUID(course_id)
            with SessionLocal() as session:
                course = session.get(Course, course_id)
                if not course:
                    raise NotFoundException(f"Course {course_id} not found")
                course.status = 'failed'
                course.error_message = error_message
                session.commit()
                logger.error(f"Marked course {course_id} as failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark course {course_id} as failed: {str(e)}")
            raise

    @staticmethod
    def delete(course_id: Union[str, UUID]) -> None:
        """
        Delete course record from database.
        Cascade will automatically delete associated checkpoint.
        """
        try:
            if isinstance(course_id, str):
                course_id = UUID(course_id)
            with SessionLocal() as session:
                course = session.get(Course, course_id)
                if not course:
                    raise NotFoundException(f"Course {course_id} not found")
                session.delete(course)
                session.commit()
                logger.info(f"Deleted course {course_id}")
        except Exception as e:
            logger.error(f"Failed to delete course {course_id}: {str(e)}")
            raise