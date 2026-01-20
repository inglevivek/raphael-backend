"""
Courses repository layer for database operations.
"""
from typing import List
from datetime import datetime, timezone

from app.models import db, Course
from app.exceptions import NotFoundException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class CoursesRepository:
    """Repository for course-related database operations."""
    
    @staticmethod
    def get_by_id(course_id: int) -> Course:
        """
        Fetch course by ID.
        
        Args:
            course_id (int): Course ID
        
        Returns:
            Course: Course object
        
        Raises:
            NotFoundException: If course not found
        """
        course = Course.query.get(course_id)
        if not course:
            logger.warning(f"Course not found with ID: {course_id}")
            raise NotFoundException(f"Course with ID {course_id} not found")
        return course
    
    @staticmethod
    def get_all_by_user(user_id: int) -> List[Course]:
        """
        Fetch all courses for a user, ordered by created_at desc.
        
        Args:
            user_id (int): User ID
        
        Returns:
            List[Course]: List of course objects
        """
        courses = Course.query.filter_by(user_id=user_id)\
            .order_by(Course.created_at.desc())\
            .all()
        return courses
    
    @staticmethod
    def create(user_id: int, topic: str, level: str) -> Course:
        """
        Create new course record with status=generating.
        
        Args:
            user_id (int): User ID
            topic (str): Course topic
            level (str): Course level (beginner|intermediate|advanced)
        
        Returns:
            Course: Created course object
        
        Raises:
            Exception: If database commit fails
        """
        try:
            course = Course(
                user_id=user_id,
                topic=topic,
                level=level,
                status='generating'
            )
            db.session.add(course)
            db.session.commit()
            logger.info(f"Created course {course.id}: {topic}")
            return course
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create course: {str(e)}")
            raise
    
    @staticmethod
    def update_status(course_id: int, status: str) -> None:
        """
        Update course status.
        
        Args:
            course_id (int): Course ID
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
    def mark_completed(course_id: int, json_path: str) -> None:
        """
        Mark course as completed and save JSON path.
        
        Args:
            course_id (int): Course ID
            json_path (str): Path to saved JSON file
        """
        try:
            course = CoursesRepository.get_by_id(course_id)
            course.status = 'completed'
            course.json_path = json_path
            course.completed_at = datetime.now(timezone.utc) 

            db.session.commit()
            logger.info(f"Marked course {course_id} as completed")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark course {course_id} as completed: {str(e)}")
            raise
    
    @staticmethod
    def mark_failed(course_id: int, error_message: str) -> None:
        """
        Mark course as failed with error message.
        
        Args:
            course_id (int): Course ID
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
    def delete(course_id: int) -> None:
        """
        Delete course record from database.
        
        Args:
            course_id (int): Course ID
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
