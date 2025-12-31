"""
Course generation pipeline with 4-stage processing.
"""
import os
from pathlib import Path
from flask import current_app

from app.main.courses.repository import CoursesRepository
from app.utils import GeminiClient, YouTubeClient, JSONStorage, GroqClient
from app.utils.logger import get_logger


logger = get_logger(__name__)


class CourseGeneratorPipeline:
    """4-stage pipeline for generating personalized courses."""
    
    def __init__(self, course_id: int):
        """
        Initialize pipeline with course ID.
        
        Args:
            course_id (int): Course database ID
        """
        self.course_id = course_id
        self.course = None
        self.gemini_client = None
        self.groq_client = None
        self.youtube_client = None
        self.prompts_dir = Path(__file__).parent / 'prompts'
    
    def _load_prompt(self, filename: str) -> str:
        """
        Load prompt template from prompts directory.
        
        Args:
            filename (str): Prompt file name
        
        Returns:
            str: Prompt template content
        """
        prompt_path = self.prompts_dir / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def generate(self) -> None:
        """
        Execute full 4-stage course generation pipeline.
        Updates database with results or error.
        """
        try:
            logger.info(f"Starting course generation pipeline for course {self.course_id}")
            
            # Initialize
            self.course = CoursesRepository.get_by_id(self.course_id)
            self.gemini_client = GeminiClient(current_app.config['GEMINI_API_KEY'])
            self.groq_client = GroqClient(current_app.config['GROQ_API_KEY'])
            self.youtube_client = YouTubeClient(current_app.config['YOUTUBE_API_KEY'])
            
            # Stage 1: Generate outline
            logger.info(f"[Course {self.course_id}] Stage 1: Generating outline")
            outline = self._stage1_generate_outline()
            
            # Stage 2: Expand points
            logger.info(f"[Course {self.course_id}] Stage 2: Expanding points")
            expanded = self._stage2_expand_points(outline)
            
            # Stage 3: Aggregate content
            logger.info(f"[Course {self.course_id}] Stage 3: Aggregating content")
            complete = self._stage3_aggregate_content(expanded)
            
            # Stage 4: Save
            logger.info(f"[Course {self.course_id}] Stage 4: Saving course")
            self._stage4_save(complete)
            
            logger.info(f"Course generation completed successfully for course {self.course_id}")
        
        except Exception as e:
            logger.error(f"Course generation failed for course {self.course_id}: {str(e)}", exc_info=True)
            CoursesRepository.mark_failed(self.course_id, str(e))
    
    def _stage1_generate_outline(self) -> dict:
        """
        Stage 1: Generate course structure (modules/chapters/topics).
        
        Returns:
            dict: Course outline with nested structure
        """
        prompt_template = self._load_prompt('outline_prompt.txt')
        prompt = prompt_template.format(
            topic=self.course.topic,
            level=self.course.level
        )
        
        outline = self.groq_client.generate_json(prompt)
        logger.info(f"[Course {self.course_id}] Generated outline with {len(outline.get('modules', []))} modules")
        return outline
    
    def _stage2_expand_points(self, outline: dict) -> dict:
        """
        Stage 2: Add 3-5 key points to each topic.
        
        Args:
            outline (dict): Course outline from stage 1
        
        Returns:
            dict: Enhanced outline with key points
        """
        prompt_template = self._load_prompt('expand_points_prompt.txt')
        
        for module in outline.get('modules', []):
            for chapter in module.get('chapters', []):
                for topic in chapter.get('topics', []):
                    # Generate key points for this topic
                    prompt = prompt_template.format(
                        topic_title=topic['topic_title'],
                        module_title=module['module_title'],
                        chapter_title=chapter['chapter_title'],
                        level=self.course.level,
                        topic_number=topic['topic_number']
                    )
                    
                    expanded_topic = self.groq_client.generate_json(prompt)
                    topic['points'] = expanded_topic.get('points', [])
        
        logger.info(f"[Course {self.course_id}] Expanded all topics with key points")
        return outline
    
    def _stage3_aggregate_content(self, outline: dict) -> dict:
        """
        Stage 3: Add videos and explanations to each topic.
        
        Args:
            outline (dict): Course outline with points from stage 2
        
        Returns:
            dict: Complete course structure with all content
        """
        explanation_template = self._load_prompt('explanation_prompt.txt')
        
        for module in outline.get('modules', []):
            for chapter in module.get('chapters', []):
                for topic in chapter.get('topics', []):
                    # Search for videos
                    search_query = f"{self.course.topic} {topic['topic_title']} tutorial"
                    try:
                        videos = self.youtube_client.search_videos(search_query, max_results=3)
                        topic['videos'] = videos
                    except Exception as e:
                        logger.warning(f"Failed to fetch videos for topic '{topic['topic_title']}': {str(e)}")
                        topic['videos'] = []
                    
                    # Generate explanation
                    points_text = '\n'.join(f"- {point}" for point in topic.get('points', []))
                    prompt = explanation_template.format(
                        topic_title=topic['topic_title'],
                        level=self.course.level,
                        points=points_text
                    )
                    
                    try:
                        explanation = self.groq_client.generate(prompt)
                        topic['explanation'] = explanation
                    except Exception as e:
                        logger.warning(f"Failed to generate explanation for topic '{topic['topic_title']}': {str(e)}")
                        topic['explanation'] = "Content generation in progress..."
        
        logger.info(f"[Course {self.course_id}] Aggregated all content")
        return outline
    
    def _stage4_save(self, content: dict) -> None:
        """
        Stage 4: Save JSON file and update database.
        
        Args:
            content (dict): Complete course content
        """
        # Save to JSON file
        json_path = JSONStorage.save_course(
            self.course_id,
            self.course.topic,
            content,
            current_app.config['COURSES_DIR']
        )
        
        # Update database
        CoursesRepository.mark_completed(self.course_id, json_path)
        logger.info(f"[Course {self.course_id}] Saved to {json_path}")
