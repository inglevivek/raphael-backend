"""
Refactored course generation pipeline with memory-based batching.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import math
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app

from app.main.courses.repository import CoursesRepository
from app.main.courses.memory import (
    CourseMemory, ModuleMemory, ChapterMemory, TopicMemory
)
from app.utils import GeminiClient, YouTubeClient, JSONStorage, GroqClient
from app.utils.logger import get_logger


logger = get_logger(__name__)

class CourseGeneratorPipeline:
    """Memory-based pipeline with batch content generation."""
    
    MAX_WORKERS = 5  # Concurrent API calls
    BATCH_SIZE = 10  # Topics per batch
    MAX_TOKENS_PER_TOPIC = 100000 # Token limit per explanation
    
    def __init__(self, course_id: int):
        self.course_id = course_id
        self.course = None
        self.memory: CourseMemory = None
        
        # Initialize clients in __init__ for reuse
        self.gemini_client = None
        self.groq_client = None
        self.youtube_client = None
        self.prompts_dir = Path(__file__).parent / 'prompts'
    
    def _load_prompt(self, filename: str) -> str:
        prompt_path = self.prompts_dir / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def generate(self) -> None:
        """Execute memory-based 5-stage pipeline."""
        try:
            logger.info(f"Starting course generation for course {self.course_id}")
            
            # Initialize
            self.course = CoursesRepository.get_by_id(self.course_id)
            self.gemini_client = GeminiClient(current_app.config['GEMINI_API_KEY'])
            self.groq_client = GroqClient(current_app.config['GROQ_API_KEY'])
            self.youtube_client = YouTubeClient(current_app.config['YOUTUBE_API_KEY'])
            
            # Initialize memory
            self.memory = CourseMemory(self.course_id, self.course.topic, self.course.level)
            
            # Stage 1: Generate index/outline and populate memory
            logger.info(f"[Course {self.course_id}] Stage 1: Generating index")
            self._stage1_generate_index()
            
            # Stage 2: Batch expand key points
            logger.info(f"[Course {self.course_id}] Stage 2: Expanding key points (batched)")
            self._stage2_batch_expand_points()
            
            # Stage 3: Batch generate content
            logger.info(f"[Course {self.course_id}] Stage 3: Generating content (batched)")
            self._stage3_batch_generate_content()
            
            # Stage 4: Aggregate resources
            logger.info(f"[Course {self.course_id}] Stage 4: Aggregating resources (batched)")
            self._stage4_batch_aggregate_resources()
            
            # Stage 5: Export structured course file
            logger.info(f"[Course {self.course_id}] Stage 5: Exporting course file")
            self._stage5_export()
            
            logger.info(f"Course generation completed for course {self.course_id}")
            
        except Exception as e:
            logger.error(f"Course generation failed: {str(e)}", exc_info=True)
            CoursesRepository.mark_failed(self.course_id, str(e))
    
    def _stage1_generate_index(self) -> None:
        """Stage 1: Generate outline and populate memory structure."""
        prompt_template = self._load_prompt('outline_prompt.txt')
        logger.info(f"Loaded prompt template, length: {len(prompt_template)}")
        prompt = prompt_template.format(
            topic=self.course.topic,
            level=self.course.level
        )
        logger.info(f"Formatted prompt (first 300 chars): {prompt[:300]}")
        
        logger.error(f"=== FORMATTED PROMPT:\n{prompt}\n===")
    
        # Call Groq
        try:
            outline = self.groq_client.generate_json(prompt)
        except Exception as e:
            logger.error(f"=== GROQ API CALL FAILED: {e}")
            raise
        outline = self.groq_client.generate_json(prompt)
           # CRITICAL DEBUG LOGS
        logger.error(f"!!! OUTLINE TYPE: {type(outline)}")
        logger.error(f"!!! OUTLINE CONTENT: {outline}")
        logger.error(f"!!! OUTLINE KEYS: {outline.keys() if isinstance(outline, dict) else 'NOT A DICT'}")
        logger.error(f"!!! MODULES KEY EXISTS: {'modules' in outline if isinstance(outline, dict) else False}")
        logger.error(f"!!! MODULES VALUE: {outline.get('modules', 'KEY NOT FOUND')}")
        # ADAPTER: Convert old format to new format if needed
        if 'modules' not in outline and 'chapter_number' in outline:
            logger.warning("⚠️ Converting OLD format to NEW format")
            outline = {
                'modules': [
                    {
                        'module_number': 1,
                        'module_title': f'Introduction to {self.course.topic}',
                        'description': f'Core {self.course.topic} concepts',
                        'chapters': [outline]  # Wrap single chapter
                    }
                ]
            }
        logger.info(f"✅ Converted to {len(outline['modules'])} modules")
        # Populate memory hierarchy
        for mod_idx, module_data in enumerate(outline.get('modules', []), 1):
            module_id = f"mod_{mod_idx}"
            module = ModuleMemory(
                module_id=module_id,
                module_number=mod_idx,
                title=module_data.get('module_title', ''),
                description=module_data.get('description')
            )
            
            for ch_idx, chapter_data in enumerate(module_data.get('chapters', []), 1):
                chapter_id = f"{module_id}_ch_{ch_idx}"
                chapter = ChapterMemory(
                    chapter_id=chapter_id,
                    chapter_number=ch_idx,
                    title=chapter_data.get('chapter_title', '')
                )
                
                for top_idx, topic_data in enumerate(chapter_data.get('topics', []), 1):
                    topic_id = f"{chapter_id}_top_{top_idx}"
                    topic = TopicMemory(
                        topic_id=topic_id,
                        topic_number=top_idx,
                        title=topic_data.get('topic_title', '')
                    )
                    chapter.add_topic(topic)
                
                module.add_chapter(chapter)
            
            self.memory.add_module(module)
        
        logger.info(f"Memory populated with {len(self.memory.get_all_topics())} topics")
    
    def _stage2_batch_expand_points(self) -> None:
        """Stage 2: Expand key points for all topics in batches."""
        topics = self.memory.get_all_topics()
        prompt_template = self._load_prompt('expand_points_prompt.txt')
        
        def expand_topic_points(topic: TopicMemory) -> TopicMemory:
            """Expand key points for a single topic."""
            try:
                # Find parent module and chapter for context
                module, chapter = self._find_topic_parents(topic.topic_id)
                
                prompt = prompt_template.format(
                    topic_title=topic.title,
                    module_title=module.title if module else '',
                    chapter_title=chapter.title if chapter else '',
                    level=self.course.level,
                    topic_number=topic.topic_number
                )
                
                result = self.groq_client.generate_json(prompt)
                topic.key_points = result.get('points', [])
                topic.status = 'points_complete'
                
                logger.info(f"Expanded points for {topic.topic_id}")
                return topic
                
            except Exception as e:
                logger.error(f"Failed to expand {topic.topic_id}: {str(e)}")
                topic.status = 'failed'
                topic.error = str(e)
                return topic
        
        # Batch process with thread pool
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(expand_topic_points, topic): topic for topic in topics}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                logger.info(f"Progress: {completed}/{len(topics)} topics expanded")
        
        logger.info("All topics expanded with key points")
    
    def _stage3_batch_generate_content(self) -> None:
        """Stage 3: Generate detailed content in batches with token limits."""
        topics = self.memory.get_topics_by_status('points_complete')
        explanation_template = self._load_prompt('explanation_prompt.txt')
        
        def generate_topic_content(topic: TopicMemory) -> TopicMemory:
            """Generate explanation for a single topic."""
            try:
                points_text = '\n'.join(f"- {point}" for point in topic.key_points)
                
                prompt = explanation_template.format(
                    topic_title=topic.title,
                    level=self.course.level,
                    points=points_text,
                    
                )
                
                explanation = self.groq_client.generate(
                    prompt
                )
                
                topic.explanation = explanation
                topic.token_count = len(explanation.split())  # Rough estimate
                topic.status = 'content_complete'
                topic.generated_at = datetime.now(timezone.utc).isoformat()
                
                logger.info(f"Generated content for {topic.topic_id}")
                return topic
                
            except Exception as e:
                logger.error(f"Failed to generate content for {topic.topic_id}: {str(e)}")
                topic.status = 'failed'
                topic.error = str(e)
                return topic
        
        # Process in batches
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(generate_topic_content, topic): topic for topic in topics}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                logger.info(f"Content generation: {completed}/{len(topics)}")
        
        logger.info("All topic content generated")
    
    def _stage4_batch_aggregate_resources(self) -> None:
        """Stage 4: Fetch videos and other resources in batches."""
        topics = self.memory.get_topics_by_status('content_complete')
        
        def fetch_topic_resources(topic: TopicMemory) -> TopicMemory:
            """Fetch videos for a single topic."""
            try:
                search_query = f"{self.course.topic} {topic.title} tutorial"
                videos = self.youtube_client.search_videos(search_query, max_results=3)
                topic.videos = videos
                topic.status = 'complete'
                
                logger.info(f"Fetched resources for {topic.topic_id}")
                return topic
                
            except Exception as e:
                logger.warning(f"Failed to fetch resources for {topic.topic_id}: {str(e)}")
                topic.videos = []
                topic.status = 'complete'  # Mark complete even if videos fail
                return topic
        
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_topic_resources, topic): topic for topic in topics}
            
            for future in as_completed(futures):
                pass  # Just wait for completion
        
        logger.info("All resources aggregated")
    
    def _stage5_export(self) -> None:
        """Stage 5: Export structured course file."""
        course_file = self.memory.export_course_file()
        
        # Save to JSON
        json_path = JSONStorage.save_course(
            self.course_id,
            self.course.topic,
            course_file,
            current_app.config['COURSES_DIR']
        )
        
        # Update database
        CoursesRepository.mark_completed(self.course_id, json_path)
        logger.info(f"Exported course to {json_path}")
    
    def _find_topic_parents(self, topic_id: str) -> tuple:
        """Find parent module and chapter for a topic."""
        for module in self.memory.modules.values():
            for chapter in module.chapters.values():
                if topic_id in chapter.topics:
                    return module, chapter
        return None, None
