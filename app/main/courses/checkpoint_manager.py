"""
Hybrid checkpoint manager: Redis (temp) + PostgreSQL (persistent)
Updated for new CourseCheckpoint schema with UUID support.
"""
from typing import Optional, Dict, Union
from uuid import UUID
from app.utils.redis.client import redis_client
from app.models import CourseCheckpoint, Course
from app import db
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CheckpointManager:
    """Manages checkpoints in Redis (temp) and PostgreSQL (persistent)"""

    def __init__(self, course_id: Union[str, UUID]):
        """
        Initialize checkpoint manager for a course.

        Args:
            course_id (str | UUID): Course UUID
        """
        # Convert to UUID if string
        if isinstance(course_id, str):
            course_id = UUID(course_id)

        self.course_id = course_id
        self.checkpoint = None
        self._load_or_create_checkpoint()

    def _load_or_create_checkpoint(self):
        """Load existing checkpoint or create new one."""
        # Try to load from database
        self.checkpoint = CourseCheckpoint.query.filter_by(
            course_id=self.course_id
        ).first()

        if not self.checkpoint:
            # Create new checkpoint
            self.checkpoint = CourseCheckpoint(course_id=self.course_id)
            db.session.add(self.checkpoint)
            db.session.commit()
            logger.info(f"Created new checkpoint for course {self.course_id}")
        else:
            logger.info(f"Loaded existing checkpoint for course {self.course_id}")

    def save_stage_data(self, stage: str, data: dict) -> None:
        """
        Save stage data to checkpoint.

        Args:
            stage (str): Stage identifier (stage1, stage2, stage3, stage4)
            data (dict): Stage data to save
        """
        try:
            # Save to checkpoint table
            self.checkpoint.set_stage_data(stage, data)

            # Update current stage if needed
            if self.checkpoint.current_stage is None:
                self.checkpoint.current_stage = stage

            db.session.commit()
            logger.info(f"Saved {stage} data for course {self.course_id}")

            # Also save to Redis for fast recovery (optional)
            redis_key = f"checkpoint:{self.course_id}:{stage}"
            redis_client.save_checkpoint(
                    course_id=str(self.course_id),
                    stage=stage,
                    data=data,
                    ttl=3600
                )  # 1 hour TTL

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save checkpoint {stage}: {str(e)}")
            raise

    def get_stage_data(self, stage: str) -> Optional[dict]:
        """
        Get stage data from checkpoint.
        
        Args:
            stage (str): Stage identifier (stage1, stage2, stage3, stage4)
        
        Returns:
            dict: Stage data or None if not found
        """
        # Try Redis first (fast)
        if redis_client.is_connected():
            data = redis_client.get_checkpoint(
                course_id=str(self.course_id),
                stage=stage
            )
            if data:
                logger.debug(f"Retrieved {stage} from Redis cache")
                return data
        
        # Fallback to database
        data = self.checkpoint.get_stage_data(stage)
        if data:
            logger.debug(f"Retrieved {stage} from PostgreSQL")
            # Restore to Redis cache
            if redis_client.is_connected():
                redis_client.save_checkpoint(
                    course_id=str(self.course_id),
                    stage=stage,
                    data=data,
                    ttl=3600
                )
        return data

    def mark_stage_complete(self, stage: str) -> None:
        """
        Mark a stage as completed.

        Args:
            stage (str): Stage identifier (stage1, stage2, stage3, stage4)
        """
        try:
            self.checkpoint.mark_stage_complete(stage)
            db.session.commit()
            logger.info(f"Marked {stage} as complete for course {self.course_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark {stage} complete: {str(e)}")
            raise

    def save_llm_context(self, stage: str, prompt: str, response: dict, tokens: int = 0) -> None:
        """
        Save LLM prompt and response for future reference.

        Args:
            stage (str): Stage identifier
            prompt (str): LLM prompt text
            response (dict): LLM response JSON
            tokens (int): Token count for this interaction
        """
        try:
            # Update LLM prompts dict
            if self.checkpoint.llm_prompts is None:
                self.checkpoint.llm_prompts = {}
            self.checkpoint.llm_prompts[stage] = prompt

            # Update LLM responses dict
            if self.checkpoint.llm_responses is None:
                self.checkpoint.llm_responses = {}
            self.checkpoint.llm_responses[stage] = response

            # Update token counts
            self.checkpoint.total_tokens = (self.checkpoint.total_tokens or 0) + tokens

            if self.checkpoint.stage_tokens is None:
                self.checkpoint.stage_tokens = {}
            self.checkpoint.stage_tokens[stage] = (
                self.checkpoint.stage_tokens.get(stage, 0) + tokens
            )

            db.session.commit()
            logger.info(f"Saved LLM context for {stage} ({tokens} tokens)")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save LLM context: {str(e)}")
            raise

    def get_llm_context(self, up_to_stage: Optional[str] = None) -> Dict:
        """
        Retrieve all previous LLM interactions for context.
        Useful for stage 3/4 to reference stage 1/2 decisions.

        Args:
            up_to_stage (str, optional): Only return stages before this one

        Returns:
            dict: LLM context with prompts and responses
        """
        if up_to_stage:
            stage_order = ['stage1', 'stage2', 'stage3', 'stage4']
            try:
                max_idx = stage_order.index(up_to_stage)
                relevant_stages = stage_order[:max_idx]
            except ValueError:
                relevant_stages = stage_order
        else:
            relevant_stages = ['stage1', 'stage2', 'stage3', 'stage4']

        context = {}
        for stage in relevant_stages:
            if self.checkpoint.llm_prompts and stage in self.checkpoint.llm_prompts:
                context[stage] = {
                    'prompt': self.checkpoint.llm_prompts.get(stage),
                    'response': self.checkpoint.llm_responses.get(stage),
                    'tokens': self.checkpoint.stage_tokens.get(stage, 0) if self.checkpoint.stage_tokens else 0
                }

        return context

    def log_error(self, stage: str, error_message: str) -> None:
        """
        Log an error to the checkpoint.

        Args:
            stage (str): Stage where error occurred
            error_message (str): Error description
        """
        try:
            self.checkpoint.add_error(stage, error_message)
            self.checkpoint.retry_count += 1
            db.session.commit()
            logger.warning(f"Logged error for {stage}: {error_message}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to log error: {str(e)}")

    def update_last_successful_topic(self, topic_id: str) -> None:
        """
        Update the last successfully processed topic.

        Args:
            topic_id (str): Topic ID (e.g., 'mod_1_ch_2_top_3')
        """
        try:
            self.checkpoint.last_successful_topic = topic_id
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update last successful topic: {str(e)}")

    def get_current_stage(self) -> Optional[str]:
        """Get the current pipeline stage."""
        return self.checkpoint.current_stage.value if self.checkpoint.current_stage else None

    def get_completed_stages(self) -> list:
        """Get list of completed stages."""
        return self.checkpoint.completed_stages or []

    def clear_redis_cache(self) -> None:
        """Clear Redis cache for this course (keep PostgreSQL data)."""
        try:
            if redis_client.is_connected():
                # Delete all stages for this course
                redis_client.delete_checkpoint(
                    course_id=str(self.course_id),
                    stage=None  # None = delete all stages
                )
                logger.info(f"Cleared Redis cache for course {self.course_id}")
        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {str(e)}")