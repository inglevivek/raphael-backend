"""
Course generation pipeline with integrated checkpoint management.
Handles crash recovery and state persistence without external dependencies.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import threading
from flask import current_app

from app.main.courses.repository import CoursesRepository
from app.main.courses.memory import (
    CourseMemory, ModuleMemory, ChapterMemory, TopicMemory
)
from app.utils import GeminiClient, YouTubeClient, JSONStorage, GroqClient
from app.models import TopicContent
from app import db
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CourseGeneratorPipeline:
    """Memory-based pipeline with integrated checkpoint management and rate limiting."""

    MAX_WORKERS = 1
    BATCH_SIZE = 10
    MAX_TOKENS_PER_TOPIC = 100000
    MIN_REQUEST_DELAY = 4.0
    MAX_RETRIES = 3
    BACKOFF_BASE = 5.0

    def __init__(self, course_id: int = None, course_topic: str = None, course_level: str = None):
        self.course_id = course_id
        self.course_topic = course_topic  
        self.course_level = course_level  
        self.course = None
        self.memory: CourseMemory = None

        # API clients
        self.gemini_client = None
        self.groq_client = None
        self.youtube_client = None

        self.prompts_dir = Path(__file__).parent / 'prompts'

        # Rate limiting state
        self.last_request_time = None
        self.request_count = 0
        self.retry_count = 0

        # Checkpoint management
        self.checkpoints_dir = Path('data/checkpoints')
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # ==================== CHECKPOINT METHODS ====================

     # NEW METHOD: Sanitize topic name for filenames
    def _sanitize_filename(self, text: str) -> str:
        """Convert course topic to filesystem-safe name."""
        # Remove special characters, keep alphanumeric and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Replace spaces with underscores and lowercase
        sanitized = sanitized.replace(' ', '_').lower()
        # Limit length to 50 characters
        return sanitized[:50]

    def _get_checkpoint_path(self, stage: str) -> Path:
        """Get path for a stage checkpoint file using course topic."""
        topic = self.course_topic or self.course.topic
        level = self.course_level or self.course.level
        sanitized_topic = self._sanitize_filename(topic)
        # NEW filename format: course_{topic}_{level}_stage_{stage}.json
        return self.checkpoints_dir / f"course_{sanitized_topic}_{level}_stage_{stage}.json"


    def _save_checkpoint(self, stage: str) -> None:
        """
        Save current memory state to checkpoint file AND database.

        Args:
            stage: Stage identifier (e.g., 'stage1_outline', 'stage2_points')
        """
        try:
            # 1. Save to JSON file (fast resume)
            checkpoint_data = {
                'course_id': self.course_id,
                'course_topic': self.course.topic,      # NEW: Store topic
                'course_level': self.course.level,      # NEW: Store level
                'stage': stage,
                'timestamp': datetime.utcnow().isoformat(),
                'memory': self._serialize_memory()
            }

            checkpoint_path = self._get_checkpoint_path(stage)
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved checkpoint to {checkpoint_path}")

            # 2. Save to database (permanent storage) - only if course_id exists
            if self.course_id:  # MODIFIED: Conditional database save
                self._save_to_database()

            logger.info(f"✅ Checkpoint saved for course '{self.course.topic}', stage: {stage}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}", exc_info=True)


    def _load_checkpoint(self, stage: str) -> bool:
        """
        Load memory state from checkpoint file.

        Args:
            stage: Stage to load

        Returns:
            True if checkpoint was loaded successfully
        """
        try:
            checkpoint_path = self._get_checkpoint_path(stage)
            if checkpoint_path.exists():
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)

                self.memory = self._deserialize_memory(checkpoint_data['memory'])

                # NEW: Update course_id if it exists in checkpoint
                if checkpoint_data.get('course_id'):
                    self.course_id = checkpoint_data['course_id']

                logger.info(f"✅ Loaded checkpoint from {checkpoint_path}")
                logger.info(f"   Restored {len(self.memory.get_all_topics())} topics")
                return True

            logger.debug(f"No checkpoint file found for stage {stage}")
            return False

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {str(e)}", exc_info=True)
            return False

    def _has_checkpoint(self, stage: str) -> bool:
        """Check if checkpoint exists for a stage."""
        return self._get_checkpoint_path(stage).exists()

    # NEW METHOD: Find existing checkpoint by topic
    def find_existing_checkpoint(self) -> Optional[str]:
        """
        Find most recent checkpoint for current course topic/level.

        Returns:
            Stage name if found, None otherwise
        """
        stages = [
            'stage4_resources',
            'stage3_content',
            'stage2_points',
            'stage1_outline'
        ]

        for stage in stages:
            if self._has_checkpoint(stage):
                logger.info(f"🔍 Found existing checkpoint at {stage}")
                return stage

        return None

    def _try_resume(self) -> Optional[str]:
        """
        Try to resume from the most recent checkpoint.

        Returns:
            Stage name if resumed, None if starting fresh
        """
        # Check stages in reverse order (most recent first)
        stages = [
            'stage4_resources',
            'stage3_content',
            'stage2_points',
            'stage1_outline'
        ]

        for stage in stages:
            if self._load_checkpoint(stage):
                total_topics = len(self.memory.get_all_topics())
                logger.info(f"🔄 RESUMING from {stage} with {total_topics} topics")
                return stage

        logger.info("No checkpoint found, starting fresh generation")
        return None

    # def _clear_checkpoints(self) -> None:
    #     """Delete all checkpoints for this course."""
    #     try:
    #         # Delete checkpoint files
    #         deleted_count = 0
    #         topic = self.course_topic or self.course.topic
    #         level = self.course_level or self.course.level
    #         sanitized_topic = self._sanitize_filename(topic)

    #         # NEW: Use topic-based pattern instead of course_id
    #         for checkpoint_file in self.checkpoints_dir.glob(f"course_{sanitized_topic}_{level}_*.json"):
    #             checkpoint_file.unlink()
    #             deleted_count += 1

    #         # Delete from database only if course_id exists
    #         if self.course_id:  # MODIFIED: Conditional database delete
    #             TopicContent.query.filter_by(course_id=self.course_id).delete()
    #             db.session.commit()

    #         logger.info(f"🗑️  Cleared {deleted_count} checkpoints for course '{topic}'")

    #     except Exception as e:
    #         logger.error(f"Failed to clear checkpoints: {str(e)}")

    def _get_progress_summary(self) -> dict:
        """Get summary of current progress."""
        if not self.memory:
            return {
                'total': 0,
                'completed': 0,
                'in_progress': 0,
                'failed': 0
            }

        topics = self.memory.get_all_topics()
        statuses = [t.status for t in topics]

        return {
            'total': len(topics),
            'completed': statuses.count('complete'),
            'content_complete': statuses.count('content_complete'),
            'points_complete': statuses.count('points_complete'),
            'pending': statuses.count('pending'),
            'failed': statuses.count('failed')
        }

    def _serialize_memory(self) -> dict:
        """Convert CourseMemory to JSON-serializable dict."""
        return {
            'course_id': self.memory.course_id,
            'topic': self.memory.topic,
            'level': self.memory.level,
            'modules': {
                module_id: {
                    'module_id': module.module_id,
                    'module_number': module.module_number,
                    'title': module.title,
                    'description': module.description,
                    'chapters': {
                        chapter_id: {
                            'chapter_id': chapter.chapter_id,
                            'chapter_number': chapter.chapter_number,
                            'title': chapter.title,
                            'topics': {
                                topic_id: {
                                    'topic_id': topic.topic_id,
                                    'topic_number': topic.topic_number,
                                    'title': topic.title,
                                    'key_points': topic.key_points or [],
                                    'explanation': topic.explanation,
                                    'videos': topic.videos or [],
                                    'status': topic.status,
                                    'token_count': topic.token_count or 0,
                                    'generated_at': topic.generated_at,
                                    'error': topic.error
                                }
                                for topic_id, topic in chapter.topics.items()
                            }
                        }
                        for chapter_id, chapter in module.chapters.items()
                    }
                }
                for module_id, module in self.memory.modules.items()
            }
        }

    def _deserialize_memory(self, data: dict) -> CourseMemory:
        """Reconstruct CourseMemory from serialized dict."""
        memory = CourseMemory(data['course_id'], data['topic'], data['level'])

        for module_data in data['modules'].values():
            module = ModuleMemory(
                module_id=module_data['module_id'],
                module_number=module_data['module_number'],
                title=module_data['title'],
                description=module_data.get('description')
            )

            for chapter_data in module_data['chapters'].values():
                chapter = ChapterMemory(
                    chapter_id=chapter_data['chapter_id'],
                    chapter_number=chapter_data['chapter_number'],
                    title=chapter_data['title']
                )

                for topic_data in chapter_data['topics'].values():
                    topic = TopicMemory(
                        topic_id=topic_data['topic_id'],
                        topic_number=topic_data['topic_number'],
                        title=topic_data['title']
                    )
                    topic.key_points = topic_data.get('key_points', [])
                    topic.explanation = topic_data.get('explanation')
                    topic.videos = topic_data.get('videos', [])
                    topic.status = topic_data.get('status', 'pending')
                    topic.token_count = topic_data.get('token_count', 0)
                    topic.generated_at = topic_data.get('generated_at')
                    topic.error = topic_data.get('error')

                    chapter.add_topic(topic)

                module.add_chapter(chapter)

            memory.add_module(module)

        return memory

    def _save_to_database(self) -> None:
        """Save all topics to database for permanent storage."""
        for topic in self.memory.get_all_topics():
            # Find parent module and chapter
            module, chapter = self._find_topic_parents(topic.topic_id)

            # Upsert topic
            existing = TopicContent.query.filter_by(
                course_id=self.course_id,
                topic_id=topic.topic_id
            ).first()

            if existing:
                # Update existing
                existing.title = topic.title
                existing.key_points = json.dumps(topic.key_points, ensure_ascii=False) if topic.key_points else None
                existing.explanation = topic.explanation
                existing.videos = json.dumps(topic.videos, ensure_ascii=False) if topic.videos else None
                existing.status = topic.status
                existing.error_message = topic.error
                existing.token_count = topic.token_count or 0
                existing.generated_at = topic.generated_at
                existing.updated_at = datetime.utcnow()
            else:
                # Insert new
                new_topic = TopicContent(
                    course_id=self.course_id,
                    topic_id=topic.topic_id,
                    module_number=module.module_number if module else None,
                    chapter_number=chapter.chapter_number if chapter else None,
                    topic_number=topic.topic_number,
                    title=topic.title,
                    key_points=json.dumps(topic.key_points, ensure_ascii=False) if topic.key_points else None,
                    explanation=topic.explanation,
                    videos=json.dumps(topic.videos, ensure_ascii=False) if topic.videos else None,
                    status=topic.status,
                    error_message=topic.error,
                    token_count=topic.token_count or 0,
                    generated_at=topic.generated_at
                )
                db.session.add(new_topic)

        db.session.commit()

    # ==================== PIPELINE METHODS ====================

    def generate(self) -> None:
        """Execute memory-based 5-stage pipeline with checkpoint support."""
        try:
            logger.info(f"Starting course generation for course {self.course_id}")

            # Initialize
            self.course = CoursesRepository.get_by_id(self.course_id)
            self.gemini_client = GeminiClient(current_app.config['GEMINI_API_KEY'])
            self.groq_client = GroqClient(current_app.config['GROQ_API_KEY'])
            self.youtube_client = YouTubeClient(current_app.config['YOUTUBE_API_KEY'])

            # Try to resume from checkpoint
            resumed_stage = self._try_resume()

            # Determine which stages to run
            if resumed_stage is None:
                # Fresh start - run all stages
                stages_to_run = ['stage1', 'stage2', 'stage3', 'stage4', 'stage5']
            elif resumed_stage == 'stage1_outline':
                stages_to_run = ['stage2', 'stage3', 'stage4', 'stage5']
            elif resumed_stage == 'stage2_points':
                stages_to_run = ['stage3', 'stage4', 'stage5']
            elif resumed_stage == 'stage3_content':
                stages_to_run = ['stage4', 'stage5']
            elif resumed_stage == 'stage4_resources':
                stages_to_run = ['stage5']
            else:
                stages_to_run = []

            # Stage 1: Generate outline
            if 'stage1' in stages_to_run:
                logger.info(f"[Course {self.course_id}] Stage 1: Generating index")
                self.memory = CourseMemory(self.course_id, self.course.topic, self.course.level)
                self._stage1_generate_index()
                self._save_checkpoint('stage1_outline')

                # Log progress
                progress = self._get_progress_summary()
                logger.info(f"   Progress: {progress['total']} topics created")

            # Stage 2: Expand key points
            if 'stage2' in stages_to_run:
                logger.info(f"[Course {self.course_id}] Stage 2: Expanding key points")
                self._stage2_batch_expand_points()
                self._save_checkpoint('stage2_points')

                # Log progress
                progress = self._get_progress_summary()
                logger.info(f"   Progress: {progress['points_complete']}/{progress['total']} points expanded")

            # Stage 3: Generate content
            if 'stage3' in stages_to_run:
                logger.info(f"[Course {self.course_id}] Stage 3: Generating content")
                self._stage3_batch_generate_content()
                self._save_checkpoint('stage3_content')

                # Log progress
                progress = self._get_progress_summary()
                logger.info(f"   Progress: {progress['content_complete']}/{progress['total']} content generated")

            # Stage 4: Aggregate resources
            if 'stage4' in stages_to_run:
                logger.info(f"[Course {self.course_id}] Stage 4: Aggregating resources")
                self._stage4_batch_aggregate_resources()
                self._save_checkpoint('stage4_resources')

                # Log progress
                progress = self._get_progress_summary()
                logger.info(f"   Progress: {progress['completed']}/{progress['total']} topics completed")

            # Stage 5: Export
            if 'stage5' in stages_to_run:
                logger.info(f"[Course {self.course_id}] Stage 5: Exporting course file")
                self._stage5_export()

            # Clear checkpoints on successful completion
            # self._clear_checkpoints()

            # Log final statistics
            self._log_generation_stats()

            logger.info(f"✅ Course generation completed for course {self.course_id}")

        except Exception as e:
            logger.error(f"❌ Course generation failed: {str(e)}", exc_info=True)

            # Save checkpoint even on failure for recovery
            try:
                if self.memory:
                    self._save_checkpoint('crashed')
                    logger.info("💾 Saved crash checkpoint for recovery")
            except:
                pass

            CoursesRepository.mark_failed(self.course_id, str(e))
            return


    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from file."""
        prompt_path = self.prompts_dir / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _enforce_rate_limit(self):
        """Enforce minimum delay between API requests."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.MIN_REQUEST_DELAY:
                sleep_time = self.MIN_REQUEST_DELAY - elapsed
                logger.debug(f"⏱️  Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.request_count += 1

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        import random
        base_delay = self.BACKOFF_BASE * (2 ** attempt)
        jitter = random.uniform(0, 1)
        return min(base_delay + jitter, 60.0)

    def _stage1_generate_index(self) -> None:
        """Stage 1: Generate outline and populate memory structure."""
        prompt_template = self._load_prompt('outline_prompt.txt')

        prompt = prompt_template.format(
            topic=self.course.topic,
            level=self.course.level
        )

        # Rate limiting
        self._enforce_rate_limit()

        # Call Groq with validation
        outline = self.groq_client.generate_json(prompt, validate_outline=True)

        # ADAPTER: Convert old format to new format if needed
        if 'modules' not in outline and 'chapter_number' in outline:
            logger.warning("Converting OLD format to NEW format")
            outline = {
                'modules': [{
                    'module_number': 1,
                    'module_title': f'Introduction to {self.course.topic}',
                    'description': f'Core {self.course.topic} concepts',
                    'chapters': [outline]
                }]
            }

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

        logger.info(f"✅ Memory populated with {len(self.memory.get_all_topics())} topics")

    def _stage2_batch_expand_points(self) -> None:
        """Stage 2: Expand key points for all topics."""
        topics = [t for t in self.memory.get_all_topics() if t.status == 'pending']
        prompt_template = self._load_prompt('expand_points_prompt.txt')

        total_topics = len(topics)
        completed = 0
        failed = 0

        def expand_topic_points_with_retry(topic: TopicMemory) -> TopicMemory:
            """Expand key points with retry logic."""
            for attempt in range(self.MAX_RETRIES):
                try:
                    self._enforce_rate_limit()

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

                    logger.info(f"   ✅ Expanded points for {topic.topic_id}")
                    return topic

                except Exception as e:
                    self.retry_count += 1
                    logger.warning(f"   ⚠️  Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {str(e)}")

                    if attempt < self.MAX_RETRIES - 1:
                        backoff = self._calculate_backoff(attempt)
                        logger.info(f"   Retrying in {backoff:.1f}s...")
                        time.sleep(backoff)
                    else:
                        logger.error(f"   ❌ Failed after {self.MAX_RETRIES} attempts")
                        topic.status = 'failed'
                        topic.error = str(e)
                        return topic

            return topic

        # Process sequentially with rate limiting
        for idx, topic in enumerate(topics, 1):
            logger.info(f"   [{idx}/{total_topics}] {topic.title}")
            result = expand_topic_points_with_retry(topic)

            if result.status == 'points_complete':
                completed += 1
            else:
                failed += 1

        logger.info(f"✅ Points expansion: {completed} succeeded, {failed} failed")

    def _stage3_batch_generate_content(self) -> None:
        """Stage 3: Generate detailed content."""
        topics = self.memory.get_topics_by_status('points_complete')
        explanation_template = self._load_prompt('explanation_prompt.txt')

        total_topics = len(topics)
        completed = 0
        failed = 0

        def generate_topic_content_with_retry(topic: TopicMemory) -> TopicMemory:
            """Generate explanation with retry logic."""
            for attempt in range(self.MAX_RETRIES):
                try:
                    self._enforce_rate_limit()

                    points_text = '\n'.join(f"- {point}" for point in topic.key_points)
                    prompt = explanation_template.format(
                        topic_title=topic.title,
                        level=self.course.level,
                        points=points_text,
                    )

                    explanation = self.groq_client.generate(prompt)

                    topic.explanation = explanation
                    topic.token_count = len(explanation.split())
                    topic.status = 'content_complete'
                    topic.generated_at = datetime.now(timezone.utc).isoformat()

                    logger.info(f"   ✅ Generated content for {topic.topic_id} ({topic.token_count} tokens)")
                    return topic

                except Exception as e:
                    self.retry_count += 1
                    logger.warning(f"   ⚠️  Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {str(e)}")

                    if attempt < self.MAX_RETRIES - 1:
                        backoff = self._calculate_backoff(attempt)
                        logger.info(f"   Retrying in {backoff:.1f}s...")
                        time.sleep(backoff)
                    else:
                        logger.error(f"   ❌ Failed after {self.MAX_RETRIES} attempts")
                        topic.status = 'failed'
                        topic.error = str(e)
                        return topic

            return topic

        # Process sequentially with rate limiting
        for idx, topic in enumerate(topics, 1):
            logger.info(f"   [{idx}/{total_topics}] {topic.title}")
            result = generate_topic_content_with_retry(topic)

            if result.status == 'content_complete':
                completed += 1
            else:
                failed += 1

        logger.info(f"✅ Content generation: {completed} succeeded, {failed} failed")

    def _stage4_batch_aggregate_resources(self) -> None:
        """Stage 4: Fetch videos sequentially with rate limiting."""
        topics = self.memory.get_topics_by_status('content_complete')
        total_topics = len(topics)
        logger.info(f"Starting resource aggregation for {total_topics} topics")
        
        completed = 0
        failed = 0
        quota_exhausted = False
        
        for idx, topic in enumerate(topics, 1):
            # Skip if quota already exhausted
            if quota_exhausted:
                logger.info(f"   ⏭️  [{idx}/{total_topics}] Skipping {topic.topic_id} (quota exhausted)")
                topic.videos = []
                topic.status = 'complete'
                failed += 1
                continue
            
            try:
                logger.info(f"   [{idx}/{total_topics}] Fetching resources for {topic.topic_id}")
                
                search_query = f"{self.course.topic} {topic.title} tutorial"
                videos = self.youtube_client.search_videos(search_query, max_results=3)
                
                # Check if quota was exhausted
                if not videos and idx < total_topics:
                    # Might be quota issue, but continue trying
                    logger.warning(f"   ⚠️  No videos found for {topic.topic_id}")
                
                topic.videos = videos
                topic.status = 'complete'
                
                if videos:
                    completed += 1
                    logger.info(f"   ✅ Fetched {len(videos)} videos for {topic.topic_id}")
                else:
                    failed += 1
                    logger.warning(f"   ⚠️  No videos for {topic.topic_id}")
                
                # Rate limiting: small delay between requests
                if idx < total_topics:  # Don't sleep after last request
                    time.sleep(0.5)
                    
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Detect quota exhaustion
                if 'quotaExceeded' in error_msg or 'quota' in error_msg.lower():
                    quota_exhausted = True
                    logger.error(
                        f"   ❌ YouTube API quota exhausted at topic {idx}/{total_topics}. "
                        "Remaining topics will be completed without videos."
                    )
                else:
                    logger.error(
                        f"   ❌ Exception for {topic.topic_id}: {error_type}: {error_msg}",
                        exc_info=True
                    )
                
                topic.videos = []
                topic.status = 'complete'
                topic.error = f"{error_type}: {error_msg}"
                failed += 1
        
        logger.info(f"✅ Resources aggregated: {completed} succeeded, {failed} failed")
        
        if quota_exhausted:
            logger.warning(
                "⚠️  YouTube API quota exhausted during resource aggregation. "
                "Course completed with partial video content."
            )


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
        logger.info(f"✅ Exported course to {json_path}")

    def _find_topic_parents(self, topic_id: str) -> Tuple[Optional[ModuleMemory], Optional[ChapterMemory]]:
        """Find parent module and chapter for a topic."""
        for module in self.memory.modules.values():
            for chapter in module.chapters.values():
                if topic_id in chapter.topics:
                    return module, chapter
        return None, None

    def _log_generation_stats(self):
        """Log final generation statistics."""
        all_topics = self.memory.get_all_topics()
        complete = sum(1 for t in all_topics if t.status == 'complete')
        failed = sum(1 for t in all_topics if t.status == 'failed')

        logger.info("=" * 60)
        logger.info("GENERATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Topics: {len(all_topics)}")
        logger.info(f"Completed: {complete} ({complete/len(all_topics)*100:.1f}%)")
        logger.info(f"Failed: {failed} ({failed/len(all_topics)*100:.1f}%)")
        logger.info(f"Total API Requests: {self.request_count}")
        logger.info(f"Total Retries: {self.retry_count}")
        logger.info("=" * 60)
