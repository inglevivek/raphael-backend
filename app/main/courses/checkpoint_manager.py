"""
Checkpoint manager for course generation state persistence.
Handles saving and loading generation progress.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.main.courses.memory import CourseMemory, ModuleMemory, ChapterMemory, TopicMemory
from app.models import TopicContent
from app import db
from app.utils.logger import get_logger

logger = get_logger(__name__)

class CheckpointManager:
    """Manages state persistence and resumption for course generation."""

    def __init__(self, course_id: int = None, course_topic: str = None, 
                 course_level: str = None, checkpoints_dir: str = None):
        """
        Initialize checkpoint manager.

        Args:
            course_id: Database course ID (optional)
            course_topic: Course topic name for file-based lookup (optional)
            course_level: Course difficulty level (optional)
            checkpoints_dir: Directory for checkpoint files
        """
        self.course_id = course_id
        self.course_topic = course_topic
        self.course_level = course_level
        self.checkpoints_dir = Path(checkpoints_dir or 'data/checkpoints')
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, text: str) -> str:
        """Convert course topic to filesystem-safe name."""
        # Remove special characters, keep alphanumeric and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Replace spaces with underscores and lowercase
        sanitized = sanitized.replace(' ', '_').lower()
        # Limit length to 50 characters
        return sanitized[:50]

    def get_checkpoint_path(self, stage: str, topic: str = None, level: str = None) -> Path:
        """
        Get path for a stage checkpoint file.

        Args:
            stage: Stage identifier
            topic: Course topic (optional, uses instance value if not provided)
            level: Course level (optional, uses instance value if not provided)

        Returns:
            Path to checkpoint file
        """
        topic = topic or self.course_topic
        level = level or self.course_level

        if not topic or not level:
            # Fallback to old behavior if topic/level not provided
            return self.checkpoints_dir / f"course_{self.course_id}_stage_{stage}.json"

        sanitized_topic = self._sanitize_filename(topic)
        return self.checkpoints_dir / f"course_{sanitized_topic}_{level}_stage_{stage}.json"

    def save_checkpoint(self, memory: CourseMemory, stage: str) -> None:
        """
        Save memory state to checkpoint file AND database.

        Args:
            memory: CourseMemory object with current state
            stage: Stage identifier (e.g., 'stage2_points', 'stage3_content')
        """
        try:
            # 1. Save to JSON file (fast resume)
            checkpoint_data = {
                'course_id': self.course_id,
                'course_topic': memory.topic,
                'course_level': memory.level,
                'stage': stage,
                'timestamp': datetime.utcnow().isoformat(),
                'memory': self._serialize_memory(memory)
            }

            checkpoint_path = self.get_checkpoint_path(stage, memory.topic, memory.level)
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved checkpoint to {checkpoint_path}")

            # 2. Save to database (permanent storage) - only if course_id exists
            if self.course_id:
                self._save_to_database(memory)

            logger.info(f"✅ Checkpoint saved for course '{memory.topic}', stage: {stage}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}", exc_info=True)

    def load_checkpoint(self, stage: str, topic: str = None, level: str = None) -> Optional[CourseMemory]:
        """
        Load memory state from checkpoint file.

        Args:
            stage: Stage to load (e.g., 'stage2_points')
            topic: Course topic (optional)
            level: Course level (optional)

        Returns:
            CourseMemory object if checkpoint exists, None otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(stage, topic, level)
            if checkpoint_path.exists():
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)

                memory = self._deserialize_memory(checkpoint_data['memory'])
                logger.info(f"✅ Loaded checkpoint from {checkpoint_path}")
                logger.info(f"   Restored {len(memory.get_all_topics())} topics")
                return memory

            logger.debug(f"No checkpoint file found at {checkpoint_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {str(e)}", exc_info=True)
            return None

    def has_checkpoint(self, stage: str, topic: str = None, level: str = None) -> bool:
        """Check if checkpoint exists for a stage."""
        return self.get_checkpoint_path(stage, topic, level).exists()

    def find_checkpoint_by_topic(self, topic: str, level: str) -> Optional[str]:
        """
        Find most recent checkpoint stage for given topic and level.

        Args:
            topic: Course topic name
            level: Course difficulty level

        Returns:
            Stage name if found, None otherwise
        """
        sanitized_topic = self._sanitize_filename(topic)

        stages = [
            'stage4_resources',
            'stage3_content',
            'stage2_points',
            'stage1_outline'
        ]

        for stage in stages:
            checkpoint_path = self.checkpoints_dir / f"course_{sanitized_topic}_{level}_stage_{stage}.json"
            if checkpoint_path.exists():
                logger.info(f"🔍 Found checkpoint for '{topic}' at {stage}")
                return stage

        return None

    # def clear_checkpoints(self, topic: str = None, level: str = None) -> None:
    #     """
    #     Delete all checkpoints for this course.

    #     Args:
    #         topic: Course topic (optional, uses instance value)
    #         level: Course level (optional, uses instance value)
    #     """
    #     try:
    #         topic = topic or self.course_topic
    #         level = level or self.course_level

    #         # Delete files
    #         deleted_count = 0
    #         if topic and level:
    #             sanitized_topic = self._sanitize_filename(topic)
    #             for checkpoint_file in self.checkpoints_dir.glob(f"course_{sanitized_topic}_{level}_*.json"):
    #                 checkpoint_file.unlink()
    #                 deleted_count += 1
    #         elif self.course_id:
    #             # Fallback to course_id pattern
    #             for checkpoint_file in self.checkpoints_dir.glob(f"course_{self.course_id}_*.json"):
    #                 checkpoint_file.unlink()
    #                 deleted_count += 1

    #         # Delete from database
    #         if self.course_id:
    #             TopicContent.query.filter_by(course_id=self.course_id).delete()
    #             db.session.commit()

    #         logger.info(f"🗑️  Cleared {deleted_count} checkpoints")

    #     except Exception as e:
    #         logger.error(f"Failed to clear checkpoints: {str(e)}")

    def get_progress_summary(self) -> dict:
        """Get summary of current progress from database."""
        topics = TopicContent.query.filter_by(course_id=self.course_id).all()

        if not topics:
            return {
                'total': 0,
                'completed': 0,
                'in_progress': 0,
                'failed': 0
            }

        statuses = [t.status for t in topics]

        return {
            'total': len(topics),
            'completed': statuses.count('complete'),
            'content_complete': statuses.count('content_complete'),
            'points_complete': statuses.count('points_complete'),
            'pending': statuses.count('pending'),
            'failed': statuses.count('failed')
        }

    def _serialize_memory(self, memory: CourseMemory) -> dict:
        """Convert CourseMemory to JSON-serializable dict."""
        return {
            'course_id': memory.course_id,
            'topic': memory.topic,
            'level': memory.level,
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
                for module_id, module in memory.modules.items()
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

    def _save_to_database(self, memory: CourseMemory) -> None:
        """Save all topics to database."""
        for topic in memory.get_all_topics():
            # Find parent module and chapter
            module, chapter = self._find_topic_parents(memory, topic.topic_id)

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

    def _find_topic_parents(self, memory: CourseMemory, topic_id: str):
        """Find parent module and chapter for a topic."""
        for module in memory.modules.values():
            for chapter in module.chapters.values():
                if topic_id in chapter.topics:
                    return module, chapter
        return None, None
