"""
Courses repository layer for database operations with UUID support.
"""
from typing import List, Union
from uuid import UUID
from datetime import datetime, timezone
from app.models import Course, CourseCheckpoint
from app import db
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
        # Convert string to UUID if needed
        if isinstance(course_id, str):
            try:
                course_id = UUID(course_id)
            except ValueError:
                logger.warning(f"Invalid UUID format: {course_id}")
                raise NotFoundException(f"Course with ID {course_id} not found")

        course = Course.query.get(course_id)
        if not course:
            logger.warning(f"Course not found with ID: {course_id}")
            raise NotFoundException(f"Course with ID {course_id} not found")
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
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        courses = Course.query.filter_by(user_id=user_id)\
            .order_by(Course.created_at.desc())\
            .all()
        return courses

    @staticmethod
    def create(user_id: Union[str, UUID], title: str, level: str, course_json: dict) -> Course:
        """
        Create new course record with status=generating.

        Args:
            user_id (str | UUID): User ID
            title (str): Course title (formerly 'topic')
            level (str): Course level (beginner|intermediate|advanced)
            course_json (dict): Complete course JSON structure

        Returns:
            Course: Created course object

        Raises:
            Exception: If database commit fails
        """
        try:
            # Convert string to UUID if needed
            if isinstance(user_id, str):
                user_id = UUID(user_id)

            course = Course(
                user_id=user_id,
                title=title,
                level=level,
                status='generating',
                course_json=course_json
            )
            db.session.add(course)
            db.session.commit()
            logger.info(f"Created course {course.id}: {title}")
            return course
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create course: {str(e)}")
            raise

    @staticmethod
    def update_course_json(course_id: Union[str, UUID], course_json: dict, 
                           total_modules: int = None, total_chapters: int = None, 
                           total_topics: int = None, estimated_minutes: int = None) -> None:
        """
        Update course JSON and metadata.

        Args:
            course_id (str | UUID): Course ID
            course_json (dict): Complete course JSON
            total_modules (int, optional): Total module count
            total_chapters (int, optional): Total chapter count
            total_topics (int, optional): Total topic count
            estimated_minutes (int, optional): Estimated duration
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            course.course_json = course_json

            # Update metadata if provided
            if total_modules is not None:
                course.total_modules = total_modules
            if total_chapters is not None:
                course.total_chapters = total_chapters
            if total_topics is not None:
                course.total_topics = total_topics
            if estimated_minutes is not None:
                course.estimated_minutes = estimated_minutes

            db.session.commit()
            logger.info(f"Updated course_json for course {course_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update course_json for {course_id}: {str(e)}")
            raise

    @staticmethod
    def update_status(course_id: Union[str, UUID], status: str) -> None:
        """
        Update course status.

        Args:
            course_id (str | UUID): Course ID
            status (str): New status (generating|completed|failed)
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            course.status = status
            db.session.commit()
            logger.info(f"Updated course {course_id} status to: {status}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update course {course_id} status: {str(e)}")
            raise

    @staticmethod
    def mark_completed(course_id: Union[str, UUID]) -> None:
        """
        Mark course as completed.

        Args:
            course_id (str | UUID): Course ID
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            course.status = 'completed'
            course.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"Marked course {course_id} as completed")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark course {course_id} as completed: {str(e)}")
            raise

    @staticmethod
    def mark_failed(course_id: Union[str, UUID], error_message: str) -> None:
        """
        Mark course as failed with error message.

        Args:
            course_id (str | UUID): Course ID
            error_message (str): Error description
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            course.status = 'failed'
            course.error_message = error_message
            db.session.commit()
            logger.error(f"Marked course {course_id} as failed: {error_message}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark course {course_id} as failed: {str(e)}")
            raise

    @staticmethod
    def delete(course_id: Union[str, UUID]) -> None:
        """
        Delete course record from database.
        Cascade will automatically delete associated checkpoint.

        Args:
            course_id (str | UUID): Course ID
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            db.session.delete(course)
            db.session.commit()
            logger.info(f"Deleted course {course_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to delete course {course_id}: {str(e)}")
            raise