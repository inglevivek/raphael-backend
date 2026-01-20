"""
Courses service layer for business logic.
"""
import threading
import sys
import traceback
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
        app = current_app._get_current_object()
        # Start pipeline in background thread with full error handling
        def run_pipeline():
            """Background thread with comprehensive exception handling."""
            course_id = course.id
            thread_name = threading.current_thread().name
            
            try:
                logger.info(f"[{thread_name}] Starting pipeline for course {course_id}")
                
                with app.app_context():
                    pipeline = CourseGeneratorPipeline(course_id)
                    pipeline.generate()
                
                logger.info(f"[{thread_name}] Pipeline completed successfully for course {course_id}")
                
            except KeyboardInterrupt:
                logger.warning(f"[{thread_name}] Pipeline interrupted by user for course {course_id}")
                try:
                    CoursesRepository.mark_failed(course_id, "Interrupted by user")
                except Exception as db_error:
                    logger.error(f"[{thread_name}] Failed to mark course as failed: {db_error}")
                
            except Exception as e:
                # Log the full exception with traceback
                error_msg = str(e)
                error_type = type(e).__name__
                tb = traceback.format_exc()
                
                logger.error(f"[{thread_name}] ❌ PIPELINE CRASHED for course {course_id}")
                logger.error(f"[{thread_name}] Exception Type: {error_type}")
                logger.error(f"[{thread_name}] Exception Message: {error_msg}")
                logger.error(f"[{thread_name}] Full Traceback:\n{tb}")
                
                # Try to mark course as failed in database
                try:
                    with app.app_context():
                        CoursesRepository.mark_failed(course_id, f"{error_type}: {error_msg}")
                        logger.info(f"[{thread_name}] Marked course {course_id} as failed in database")
                except Exception as db_error:
                    logger.error(f"[{thread_name}] Failed to update database: {db_error}", exc_info=True)
                
            except:
                # Catch absolutely everything, including SystemExit
                exc_info = sys.exc_info()
                logger.critical(
                    f"[{thread_name}] ⚠️ UNEXPECTED EXCEPTION TYPE for course {course_id}: "
                    f"{exc_info[0].__name__}: {exc_info[1]}"
                )
                logger.critical(f"[{thread_name}] Traceback: {''.join(traceback.format_exception(*exc_info))}")
            
            finally:
                logger.info(f"[{thread_name}] Thread exiting for course {course_id}")

        thread = threading.Thread(
            target=run_pipeline,
            name=f"course-gen-{course.id}",
            daemon=True  # Don't prevent Flask shutdown
        )
        thread.start()

        logger.info(f"Started course generation thread for course {course.id}")
        return course.to_dict()

        
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
        if int(course.user_id) != int(user_id):
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
        
        # # Check ownership
        # if course.user_id != user_id:
        #     raise UnauthorizedException("You don't have permission to access this course")
        
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
        if int(course.user_id) != int(user_id):
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
