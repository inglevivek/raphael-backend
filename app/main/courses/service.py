"""
Courses service layer for business logic.
"""
import threading
from typing import List, Dict
from flask import current_app

from app.main.courses.repository import CoursesRepository
from app.main.courses.pipeline import CourseGeneratorPipeline
from app.exceptions import UnauthorizedException, ValidationException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class CoursesService:
    """Service for course-related business logic."""
    
    @staticmethod
    def create_course(user_id: int, topic: str, level: str) -> Dict:
        """
        Create course and start generation pipeline in background.
        
        Args:
            user_id (int): User ID
            topic (str): Course topic
            level (str): Course level
        
        Returns:
            dict: Course data with status='generating'
        """
        # Create course record
        course = CoursesRepository.create(user_id, topic, level)
        
        # Get app instance before starting thread
        app = current_app._get_current_object()

        # Start pipeline in background thread
        def run_pipeline():
            with app.app_context():
                pipeline = CourseGeneratorPipeline(course.id)
                pipeline.generate()
        
        thread = threading.Thread(target=run_pipeline)
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started course generation for course {course.id}")
        return course.to_dict()
    
    @staticmethod
    def get_user_courses(user_id: int) -> List[Dict]:
        """
        Get all courses for a user.
        
        Args:
            user_id (int): User ID
        
        Returns:
            List[dict]: List of course data
        """
        courses = CoursesRepository.get_all_by_user(user_id)
        return [course.to_dict() for course in courses]
    
    @staticmethod
    def get_course_details(user_id: int, course_id: int) -> Dict:
        """
        Get course metadata for status polling.
        
        Args:
            user_id (int): User ID
            course_id (int): Course ID
        
        Returns:
            dict: Course data without content
        
        Raises:
            NotFoundException: If course not found
            UnauthorizedException: If user doesn't own course
        """
        course = CoursesRepository.get_by_id(course_id)
        
        # Check ownership
        if course.user_id != user_id:
            logger.warning(f"User {user_id} attempted to access course {course_id} owned by {course.user_id}")
            raise UnauthorizedException("You don't have permission to access this course")
        
        return course.to_dict()
    
    @staticmethod
    def get_course_content(user_id: int, course_id: int) -> Dict:
        """
        Get course with full JSON content.
        
        Args:
            user_id (int): User ID
            course_id (int): Course ID
        
        Returns:
            dict: Course data with content field
        
        Raises:
            NotFoundException: If course not found
            UnauthorizedException: If user doesn't own course
            ValidationException: If course not completed
        """
        course = CoursesRepository.get_by_id(course_id)
        
        # Check ownership
        if course.user_id != user_id:
            raise UnauthorizedException("You don't have permission to access this course")
        
        # Check if completed
        if course.status != 'completed':
            raise ValidationException(f"Course is not ready yet. Current status: {course.status}")
        
        base_dir = current_app.config['BASE_DIR']
        return course.to_dict(include_content=True, base_dir=base_dir)
    
    @staticmethod
    def delete_course(user_id: int, course_id: int) -> None:
        """
        Delete course and associated JSON file.
        
        Args:
            user_id (int): User ID
            course_id (int): Course ID
        
        Raises:
            NotFoundException: If course not found
            UnauthorizedException: If user doesn't own course
        """
        course = CoursesRepository.get_by_id(course_id)
        
        # Check ownership
        if course.user_id != user_id:
            raise UnauthorizedException("You don't have permission to delete this course")
        
        # Delete JSON file if exists
        if course.json_path:
            from app.utils.storage import JSONStorage
            try:
                base_dir = current_app.config['BASE_DIR']
                JSONStorage.delete_course(course.json_path, base_dir)
            except Exception as e:
                logger.warning(f"Failed to delete course file: {str(e)}")
        
        # Delete from database
        CoursesRepository.delete(course_id)
        logger.info(f"Deleted course {course_id}")
