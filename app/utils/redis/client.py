"""
Redis client for caching and checkpoint management.

Provides:
- LLM response caching
- Temporary checkpoint storage (syncs with PostgreSQL)
- Pipeline state tracking
"""

import redis
import json
from typing import Optional, Dict, Any, Union
from flask import current_app
from uuid import UUID

class RedisClient:
    """Redis client for caching LLM responses and managing checkpoints"""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    def init_app(self, app):
        """
        Initialize Redis client with Flask app.

        Args:
            app: Flask application instance
        """
        redis_url = app.config.get('REDIS_URL')

        if not redis_url:
            app.logger.warning("REDIS_URL not configured. Redis caching disabled.")
            return

        try:
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10
            )

            # Test connection
            self.client.ping()
            app.logger.info(f"✅ Redis connected: {redis_url}")

        except redis.ConnectionError as e:
            app.logger.error(f"❌ Redis connection failed: {e}")
            self.client = None
        except Exception as e:
            app.logger.error(f"❌ Redis initialization error: {e}")
            self.client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected and available"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False

    # ==========================================
    # LLM RESPONSE CACHING
    # ==========================================

    def cache_llm_response(self, prompt: str, response: Dict[Any, Any], ttl: int = 3600) -> bool:
        """
        Cache LLM response for reuse.

        Args:
            prompt (str): LLM prompt text
            response (dict): LLM response data
            ttl (int): Time to live in seconds (default: 1 hour)

        Returns:
            bool: True if cached successfully
        """
        if not self.is_connected():
            return False

        try:
            # Create a simple hash of the prompt
            import hashlib
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

            key = f"llm:cache:{prompt_hash}"
            self.client.setex(key, ttl, json.dumps(response))
            return True
        except Exception as e:
            current_app.logger.error(f"Redis cache error: {e}")
            return False

    def get_cached_llm_response(self, prompt: str) -> Optional[Dict[Any, Any]]:
        """
        Retrieve cached LLM response.

        Args:
            prompt (str): LLM prompt text

        Returns:
            dict or None: Cached response or None if not found
        """
        if not self.is_connected():
            return None

        try:
            import hashlib
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

            key = f"llm:cache:{prompt_hash}"
            data = self.client.get(key)

            if data:
                return json.loads(data)
            return None
        except Exception as e:
            current_app.logger.error(f"Redis get cache error: {e}")
            return None

    # ==========================================
    # CHECKPOINT MANAGEMENT
    # ==========================================

    def save_checkpoint(self, course_id: Union[str, int, UUID], stage: str, data: Dict[Any, Any], ttl: int = 86400) -> bool:
        """
        Save checkpoint to Redis (temporary, fast access).

        Args:
            course_id (int): Course ID
            stage (str): Pipeline stage (stage1, stage2, stage3, stage4)
            data (dict): Checkpoint data
            ttl (int): Time to live in seconds (default: 24 hours)

        Returns:
            bool: True if saved successfully
        """
        if not self.is_connected():
            return False

        try:
            key = f"checkpoint:{course_id}:{stage}"
            self.client.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            current_app.logger.error(f"Redis checkpoint save error: {e}")
            return False

    def get_checkpoint(self, course_id: Union[str, int, UUID], stage: str) -> Optional[Dict[Any, Any]]:
        """
        Retrieve checkpoint from Redis.

        Args:
            course_id (int): Course ID
            stage (str): Pipeline stage

        Returns:
            dict or None: Checkpoint data or None if not found
        """
        if not self.is_connected():
            return None

        try:
            key = f"checkpoint:{course_id}:{stage}"
            data = self.client.get(key)

            if data:
                return json.loads(data)
            return None
        except Exception as e:
            current_app.logger.error(f"Redis checkpoint get error: {e}")
            return None

    def delete_checkpoint(self, course_id: Union[str, int, UUID], stage: str = None) -> bool:
        """
        Delete checkpoint(s) from Redis.

        Args:
            course_id (int): Course ID
            stage (str, optional): Specific stage to delete, or None to delete all stages

        Returns:
            bool: True if deleted successfully
        """
        if not self.is_connected():
            return False

        try:
            if stage:
                # Delete specific stage
                key = f"checkpoint:{course_id}:{stage}"
                self.client.delete(key)
            else:
                # Delete all stages for this course
                pattern = f"checkpoint:{course_id}:*"
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)
            return True
        except Exception as e:
            current_app.logger.error(f"Redis checkpoint delete error: {e}")
            return False

    # ==========================================
    # PIPELINE STATE TRACKING
    # ==========================================

    def set_pipeline_state(self, course_id: Union[str, int, UUID], state: str, ttl: int = 3600) -> bool:
        """
        Set current pipeline state for a course.

        Args:
            course_id (int): Course ID
            state (str): Current state (generating, stage1, stage2, etc.)
            ttl (int): Time to live in seconds (default: 1 hour)

        Returns:
            bool: True if set successfully
        """
        if not self.is_connected():
            return False

        try:
            key = f"pipeline:state:{course_id}"
            self.client.setex(key, ttl, state)
            return True
        except Exception as e:
            current_app.logger.error(f"Redis state set error: {e}")
            return False

    def get_pipeline_state(self, course_id: Union[str, int, UUID]) -> Optional[str]:
        """
        Get current pipeline state for a course.

        Args:
            course_id (int): Course ID

        Returns:
            str or None: Current state or None if not found
        """
        if not self.is_connected():
            return None

        try:
            key = f"pipeline:state:{course_id}"
            return self.client.get(key)
        except Exception as e:
            current_app.logger.error(f"Redis state get error: {e}")
            return None

    def increment_retry_count(self, course_id: Union[str, int, UUID], stage: str) -> int:
        """
        Increment retry counter for a course stage.

        Args:
            course_id (int): Course ID
            stage (str): Pipeline stage

        Returns:
            int: New retry count
        """
        if not self.is_connected():
            return 0

        try:
            key = f"retry:{course_id}:{stage}"
            count = self.client.incr(key)
            self.client.expire(key, 86400)  # Expire after 24 hours
            return count
        except Exception as e:
            current_app.logger.error(f"Redis retry increment error: {e}")
            return 0

    def get_retry_count(self, course_id: Union[str, int, UUID], stage: str) -> int:
        """
        Get retry count for a course stage.

        Args:
            course_id (int): Course ID
            stage (str): Pipeline stage

        Returns:
            int: Retry count
        """
        if not self.is_connected():
            return 0

        try:
            key = f"retry:{course_id}:{stage}"
            count = self.client.get(key)
            return int(count) if count else 0
        except Exception as e:
            current_app.logger.error(f"Redis retry get error: {e}")
            return 0

    # ==========================================
    # UTILITY METHODS
    # ==========================================

    def flush_course_cache(self, course_id: Union[str, int, UUID]) -> bool:
        """
        Flush all Redis cache for a specific course.

        Args:
            course_id (int): Course ID

        Returns:
            bool: True if flushed successfully
        """
        if not self.is_connected():
            return False

        try:
            patterns = [
                f"checkpoint:{course_id}:*",
                f"pipeline:state:{course_id}",
                f"retry:{course_id}:*"
            ]

            for pattern in patterns:
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)

            return True
        except Exception as e:
            current_app.logger.error(f"Redis flush error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis connection and usage stats.

        Returns:
            dict: Redis statistics
        """
        if not self.is_connected():
            return {"connected": False}

        try:
            info = self.client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed")
            }
        except Exception as e:
            current_app.logger.error(f"Redis stats error: {e}")
            return {"connected": False, "error": str(e)}


# Global Redis client instance
redis_client = RedisClient()
