"""
Pytest configuration and shared fixtures — FastAPI version.
"""
import pytest
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Override DATABASE_URL before importing app modules that read it at module level
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AUTH0_DOMAIN", "test.auth0.com")
os.environ.setdefault("AUTH0_AUDIENCE", "test-audience")

from app.database import Base
import app.database as _db_module

# Create a test engine (SQLite in-memory)
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Patch the module-level engine and SessionLocal used by all repositories
_db_module.engine = TEST_ENGINE
_db_module.SessionLocal = TestSessionLocal


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables in the test SQLite database."""
    from app.models import User, Course, CourseCheckpoint  # noqa: F401
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client():
    """FastAPI TestClient."""
    from main import app as fastapi_app
    return TestClient(fastapi_app)


@pytest.fixture
def db_session(create_tables):
    """Database session for tests."""
    session = TestSessionLocal()
    yield session
    session.rollback()
    # Clean up tables
    from app.models import Course, User
    session.query(Course).delete()
    session.query(User).delete()
    session.commit()
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create sample user."""
    from app.models import User
    user = User(
        email='test@example.com',
        password_hash='hashed_password',
        name='Test User',
        auth0_user_id='auth0|test123'
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_course(db_session, sample_user):
    """Create sample course."""
    from app.models import Course
    course = Course(
        user_id=sample_user.id,
        title='Python Programming',
        level='beginner',
        status='generating',
        course_json={'metadata': {}, 'index': {'modules': []}, 'content': {}}
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


@pytest.fixture
def sample_outline():
    """Sample course outline from API."""
    return {
        'modules': [
            {
                'module_number': 1,
                'module_title': 'Introduction to Python',
                'description': 'Python basics',
                'chapters': [
                    {
                        'chapter_number': 1,
                        'chapter_title': 'Getting Started',
                        'topics': [
                            {
                                'topic_number': 1,
                                'topic_title': 'Installing Python'
                            },
                            {
                                'topic_number': 2,
                                'topic_title': 'Your First Program'
                            }
                        ]
                    }
                ]
            },
            {
                'module_number': 2,
                'module_title': 'Data Types',
                'chapters': [
                    {
                        'chapter_number': 1,
                        'chapter_title': 'Basic Types',
                        'topics': [
                            {
                                'topic_number': 1,
                                'topic_title': 'Strings'
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_groq_client():
    """Mock Groq API client."""
    client = Mock()
    client.generate_json.return_value = {
        'points': [
            'Point 1',
            'Point 2',
            'Point 3'
        ]
    }
    client.generate.return_value = "This is a detailed explanation of the topic."
    return client


@pytest.fixture
def mock_youtube_client():
    """Mock YouTube API client."""
    client = Mock()
    client.search_videos.return_value = [
        {
            'videoId': 'abc123',
            'title': 'Python Tutorial',
            'channelName': 'Code Academy',
            'thumbnailUrl': 'https://example.com/thumb.jpg',
            'duration': '10:30',
            'url': 'https://youtube.com/watch?v=abc123'
        }
    ]
    return client


@pytest.fixture
def sample_topic_memory():
    """Sample TopicMemory instance."""
    from app.main.courses.memory import TopicMemory
    return TopicMemory(
        topic_id='mod_1_ch_1_top_1',
        topic_number=1,
        title='Installing Python',
        key_points=['Download from python.org', 'Run installer', 'Verify installation'],
        explanation='Python installation is straightforward...',
        status='complete'
    )


@pytest.fixture
def sample_chapter_memory(sample_topic_memory):
    """Sample ChapterMemory instance."""
    from app.main.courses.memory import ChapterMemory
    chapter = ChapterMemory(
        chapter_id='mod_1_ch_1',
        chapter_number=1,
        title='Getting Started'
    )
    chapter.add_topic(sample_topic_memory)
    return chapter


@pytest.fixture
def sample_module_memory(sample_chapter_memory):
    """Sample ModuleMemory instance."""
    from app.main.courses.memory import ModuleMemory
    module = ModuleMemory(
        module_id='mod_1',
        module_number=1,
        title='Introduction to Python',
        description='Learn Python basics'
    )
    module.add_chapter(sample_chapter_memory)
    return module


@pytest.fixture
def sample_course_memory(sample_module_memory):
    """Sample CourseMemory instance."""
    from app.main.courses.memory import CourseMemory
    memory = CourseMemory(
        course_id=1,
        topic='Python Programming',
        level='beginner'
    )
    memory.add_module(sample_module_memory)
    return memory
