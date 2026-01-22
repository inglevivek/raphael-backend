"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from flask import Flask
from app.models import User, Course
from app import db
from app.main.courses.memory import (
    TopicMemory, ChapterMemory, ModuleMemory, CourseMemory
)

@pytest.fixture(scope='session')
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['GEMINI_API_KEY'] = 'test-gemini-key'
    app.config['GROQ_API_KEY'] = 'test-groq-key'
    app.config['YOUTUBE_API_KEY'] = 'test-youtube-key'
    
    # Create temp directory for test files
    temp_dir = tempfile.mkdtemp()
    app.config['COURSES_DIR'] = temp_dir
    app.config['BASE_DIR'] = Path(temp_dir)
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    
    # Cleanup temp directory
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()

@pytest.fixture
def app_context(app):
    """Application context for tests."""
    with app.app_context():
        yield app

@pytest.fixture
def db_session(app_context):
    """Database session for tests."""
    yield db.session
    db.session.rollback()
    db.session.query(Course).delete()
    db.session.query(User).delete()
    db.session.commit()

@pytest.fixture
def sample_user(db_session):
    """Create sample user."""
    user = User(
        email='test@example.com',
        password_hash='hashed_password',
        name='Test User'
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def sample_course(db_session, sample_user):
    """Create sample course."""
    course = Course(
        user_id=sample_user.id,
        topic='Python Programming',
        level='beginner',
        status='generating'
    )
    db_session.add(course)
    db_session.commit()
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
    memory = CourseMemory(
        course_id=1,
        topic='Python Programming',
        level='beginner'
    )
    memory.add_module(sample_module_memory)
    return memory
