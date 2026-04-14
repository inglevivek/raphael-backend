"""
Database models for Raphael backend - PostgreSQL Production Schema

Three-table architecture with best practices:
1. User - Authentication and profile
2. Course - Complete course JSON storage with metadata
3. CourseCheckpoint - LLM cache and pipeline recovery (ONE ROW PER COURSE)

Key improvements:
- UUID primary keys (not guessable, scalable)
- PostgreSQL ENUM for status (typo-safe)
- GIN index on JSONB for fast searches
- Renamed 'topic' → 'title' for clarity
- Fixed to_dict_full() to avoid nesting collision

Designed for Railway deployment with PostgreSQL and Redis integration.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean,
    Index, Enum as SQLEnum, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PostgreSQL_UUID
from app.database import Base

# PostgreSQL ENUM types for type safety
CourseStatusEnum = SQLEnum(
    'generating',
    'completed',
    'failed',
    name='course_status',
    create_type=True
)

PipelineStageEnum = SQLEnum(
    'stage1',
    'stage2',
    'stage3',
    'stage4',
    'completed',
    name='pipeline_stage',
    create_type=True
)


# ========================================
# TABLE 1: USERS
# ========================================
class User(Base):
    """
    User model for authentication and course ownership.

    Uses UUID for security and scalability.
    Single row per user containing all authentication data.
    """
    __tablename__ = 'users'

    # Primary Key (UUID)
    id = Column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    auth0_user_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    # User Data
    email = Column(String(120), unique=True, nullable=False, index=True)

    picture = Column(String(500), nullable=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    email_verified = Column(Boolean, default=False)

    last_login_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    # Relationships
    courses = relationship(
        'Course',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        """
        Convert user to dictionary representation.
        Excludes sensitive data like password_hash.

        Returns:
            dict: User data with id, email, name, created_at
        """
        return {
            'id': str(self.id),  # Internal UUID
            'auth0_user_id': self.auth0_user_id,  # Auth0 subject
            'email': self.email,
            'name': self.name,
            'picture': self.picture,
            'email_verified': self.email_verified,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.email}>'


# ========================================
# TABLE 2: COURSES
# ========================================
class Course(Base):
    """
    Course model for storing complete course JSON and metadata.

    Single row per course containing:
    - Metadata for fast /list queries (title, level, status, etc.)
    - Complete course JSON unaltered in JSONB column
    - No file-based storage, pure PostgreSQL

    Key improvements:
    - UUID primary key (secure, scalable)
    - ENUM for status (typo-safe)
    - GIN index on course_json for fast JSON searches
    - 'title' instead of 'topic' for clarity

    API Usage:
    - GET /courses → Returns metadata only (fast)
    - GET /courses/<id> → Returns full course_json under 'course' key
    """
    __tablename__ = 'courses'

    # Primary Key (UUID)
    id = Column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign Key (UUID)
    user_id = Column(
        PostgreSQL_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # ===== Metadata (for /list endpoint - fast queries) =====
    title = Column(String(200), nullable=False)  # Course title (was 'topic')
    level = Column(String(20), nullable=False)  # beginner|intermediate|advanced
    status = Column(
        CourseStatusEnum,  # PostgreSQL ENUM (typo-safe)
        nullable=False,
        default='generating',
        index=True
    )

    # ===== Complete Course JSON (unaltered storage) =====
    course_json = Column(JSONB, nullable=False)
    # Stores entire course structure:
    # {
    #   "metadata": {...},
    #   "index": {"modules": [...]},
    #   "content": {...}
    # }

    # ===== Additional Metadata (extracted for quick stats) =====
    total_modules = Column(Integer)
    total_chapters = Column(Integer)
    total_topics = Column(Integer)
    estimated_minutes = Column(Integer)

    # ===== Error Handling =====
    error_message = Column(Text)

    # ===== Timestamps =====
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    checkpoint = relationship(
        'CourseCheckpoint',
        backref='course',
        uselist=False,  # One-to-one relationship
        cascade='all, delete-orphan'
    )

    # Indexes
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
        # GIN index for fast JSONB searches (e.g., search by module title, topic)
        Index('idx_course_json_gin', 'course_json', postgresql_using='gin'),
    )

    def to_dict_metadata(self):
        """
        Convert course to dictionary with metadata only.
        Used for /list endpoint to avoid loading full JSON.

        Returns:
            dict: Course metadata without course_json content
        """
        data = {
            'id': str(self.id),  # Convert UUID to string
            'title': self.title,  # Course title
            'level': self.level,
            'status': self.status.value if hasattr(self.status, 'value') else self.status,
            'total_modules': self.total_modules,
            'total_chapters': self.total_chapters,
            'total_topics': self.total_topics,
            'estimated_minutes': self.estimated_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

        if self.error_message:
            data['error_message'] = self.error_message

        return data

    def to_dict_full(self):
        """
        Convert course to dictionary with full course JSON.
        Used for /courses/<id> endpoint to return complete course.

        Returns:
            dict: Course metadata + full course_json under 'course' key
                  (avoids nesting collision with 'content' node inside JSON)
        """
        data = self.to_dict_metadata()
        # Use 'course' key instead of 'content' to avoid collision
        # since course_json already has a 'content' node
        data['course_json'] = self.course_json
        return data

    def __repr__(self):
        return f'<Course {self.id}: {self.title} ({self.status})>'


# ========================================
# TABLE 3: COURSE CHECKPOINTS
# ========================================
class CourseCheckpoint(Base):
    """
    LLM cache and checkpoint persistence for crash recovery.

    ONE ROW PER COURSE - stores all pipeline state and LLM context.

    Architecture:
    - Redis: Fast in-memory cache for active generation
    - PostgreSQL: Persistent backup for crash recovery

    Usage:
    1. Pipeline saves checkpoints to Redis (fast)
    2. On stage completion, persist to PostgreSQL
    3. On crash/restart, recover from PostgreSQL
    4. LLM context stored for future reference
    """
    __tablename__ = 'course_checkpoints'

    # Primary Key (UUID)
    id = Column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign Key (ONE ROW PER COURSE - enforced by unique constraint)
    course_id = Column(
        PostgreSQL_UUID(as_uuid=True),
        ForeignKey('courses.id', ondelete='CASCADE'),
        unique=True,  # Ensures one checkpoint per course
        nullable=False,
        index=True
    )

    # ===== Stage Checkpoints (JSONB for flexibility) =====
    stage1_outline = Column(JSONB)      # Stage 1: Course outline
    stage2_points = Column(JSONB)       # Stage 2: Expanded key points
    stage3_content = Column(JSONB)      # Stage 3: Generated content
    stage4_resources = Column(JSONB)    # Stage 4: Video resources

    # ===== Current Pipeline State =====
    current_stage = Column(PipelineStageEnum)  # PostgreSQL ENUM (typo-safe)
    completed_stages = Column(ARRAY(String))  # ['stage1', 'stage2']

    # ===== LLM Context & Caching =====
    llm_prompts = Column(JSONB)    # {"stage1": "prompt text", "stage2": "..."}
    llm_responses = Column(JSONB)  # {"stage1": {...}, "stage2": {...}}

    # ===== Metrics =====
    total_tokens = Column(Integer, default=0)
    stage_tokens = Column(JSONB)  # {"stage1": 1500, "stage2": 3200, ...}

    # ===== Recovery Metadata =====
    last_successful_topic = Column(String(100))  # e.g., "mod_2_ch_3_top_5"
    retry_count = Column(Integer, default=0)
    error_log = Column(JSONB)  # [{"stage": "stage2", "error": "...", "timestamp": "..."}]

    # ===== Timestamps =====
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Indexes
    __table_args__ = (
        Index('idx_current_stage', 'current_stage'),
    )

    def to_dict(self):
        """
        Convert checkpoint to dictionary representation.

        Returns:
            dict: Checkpoint data with pipeline state and metadata
        """
        return {
            'id': str(self.id),  # Convert UUID to string
            'course_id': str(self.course_id),
            'current_stage': self.current_stage.value if hasattr(self.current_stage, 'value') else self.current_stage,
            'completed_stages': self.completed_stages or [],
            'total_tokens': self.total_tokens,
            'last_successful_topic': self.last_successful_topic,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def get_stage_data(self, stage: str):
        """
        Get data for a specific stage.

        Args:
            stage (str): Stage identifier (stage1, stage2, stage3, stage4)

        Returns:
            dict: Stage data or None if not found
        """
        stage_map = {
            'stage1': self.stage1_outline,
            'stage2': self.stage2_points,
            'stage3': self.stage3_content,
            'stage4': self.stage4_resources
        }
        return stage_map.get(stage)

    def set_stage_data(self, stage: str, data: dict):
        """
        Set data for a specific stage.

        Args:
            stage (str): Stage identifier (stage1, stage2, stage3, stage4)
            data (dict): Stage data to store
        """
        if stage == 'stage1':
            self.stage1_outline = data
        elif stage == 'stage2':
            self.stage2_points = data
        elif stage == 'stage3':
            self.stage3_content = data
        elif stage == 'stage4':
            self.stage4_resources = data

    def add_error(self, stage: str, error_message: str):
        """
        Add error to error log.

        Args:
            stage (str): Stage where error occurred
            error_message (str): Error description
        """
        if self.error_log is None:
            self.error_log = []

        self.error_log.append({
            'stage': stage,
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat(),
            'retry_count': self.retry_count
        })

    def mark_stage_complete(self, stage: str):
        """
        Mark a stage as completed and advance to next.

        Args:
            stage (str): Stage to mark as complete
        """
        if self.completed_stages is None:
            self.completed_stages = []

        if stage not in self.completed_stages:
            self.completed_stages.append(stage)

        # Update current stage to next
        stage_order = ['stage1', 'stage2', 'stage3', 'stage4']
        try:
            current_idx = stage_order.index(stage)
            if current_idx < len(stage_order) - 1:
                self.current_stage = stage_order[current_idx + 1]
            else:
                self.current_stage = 'completed'
        except ValueError:
            pass

    def __repr__(self):
        return f'<CourseCheckpoint course_id={self.course_id} stage={self.current_stage}>'