"""
JSON file storage utilities for course content.
"""
import json
import os
from pathlib import Path
from typing import Dict
from slugify import slugify

from app.exceptions import StorageException, NotFoundException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class JSONStorage:
    """Handles JSON file storage operations for course content."""
    
    @staticmethod
    def save_course(course_id: int, topic: str, content: Dict, courses_dir: Path) -> str:
        """
        Save course content as JSON file.
        
        Args:
            course_id (int): Course database ID
            topic (str): Course topic for filename
            content (Dict): Course content to save
            courses_dir (Path): Directory to save courses
        
        Returns:
            str: Relative path to saved file
        
        Raises:
            StorageException: If file write fails
        """
        try:
            # Create courses directory if it doesn't exist
            courses_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            topic_slug = slugify(topic)[:50]  # Limit length
            filename = f"{course_id}_{topic_slug}.json"
            file_path = courses_dir / filename
            
            # Write JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved course {course_id} to {file_path}")
            
            # Return relative path
            return str(file_path.relative_to(courses_dir.parent.parent))
        
        except Exception as e:
            logger.error(f"Failed to save course {course_id}: {str(e)}")
            raise StorageException(f"Failed to save course content: {str(e)}")
    
    @staticmethod
    def load_course(json_path: str, base_dir: Path) -> Dict:
        """
        Load course content from JSON file.
        
        Args:
            json_path (str): Relative path to JSON file
            base_dir (Path): Base directory of the application
        
        Returns:
            Dict: Course content
        
        Raises:
            NotFoundException: If file doesn't exist
            StorageException: If file read fails
        """
        try:
            file_path = base_dir / json_path
            
            if not file_path.exists():
                logger.warning(f"Course file not found: {file_path}")
                raise NotFoundException(f"Course file not found: {json_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            
            logger.info(f"Loaded course from {file_path}")
            return content
        
        except NotFoundException:
            raise
        
        except Exception as e:
            logger.error(f"Failed to load course from {json_path}: {str(e)}")
            raise StorageException(f"Failed to load course content: {str(e)}")
    
    @staticmethod
    def delete_course(json_path: str, base_dir: Path) -> None:
        """
        Delete course JSON file.
        
        Args:
            json_path (str): Relative path to JSON file
            base_dir (Path): Base directory of the application
        
        Raises:
            StorageException: If file deletion fails
        """
        try:
            file_path = base_dir / json_path
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted course file: {file_path}")
            else:
                logger.warning(f"Course file not found for deletion: {file_path}")
        
        except Exception as e:
            logger.error(f"Failed to delete course file {json_path}: {str(e)}")
            raise StorageException(f"Failed to delete course file: {str(e)}")
