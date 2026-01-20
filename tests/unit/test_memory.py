"""
Unit tests for memory objects.
"""
import pytest
from datetime import datetime
from app.main.courses.memory import (
    TopicMemory, ChapterMemory, ModuleMemory, CourseMemory
)

class TestTopicMemory:
    """Tests for TopicMemory class."""
    
    def test_topic_memory_initialization(self):
        """Test TopicMemory is initialized correctly."""
        topic = TopicMemory(
            topic_id='mod_1_ch_1_top_1',
            topic_number=1,
            title='Test Topic'
        )
        
        assert topic.topic_id == 'mod_1_ch_1_top_1'
        assert topic.topic_number == 1
        assert topic.title == 'Test Topic'
        assert topic.status == 'pending'
        assert topic.key_points == []
        assert topic.explanation is None
    
    def test_topic_to_dict(self, sample_topic_memory):
        """Test TopicMemory converts to dict correctly."""
        result = sample_topic_memory.to_dict()
        
        assert result['topicId'] == 'mod_1_ch_1_top_1'
        assert result['title'] == 'Installing Python'
        assert len(result['keyPoints']) == 3
        assert 'explanation' in result
        assert result['explanation']['text'] == 'Python installation is straightforward...'
        assert 'resources' in result
        assert 'metadata' in result
        assert result['metadata']['status'] == 'complete'
    
    def test_topic_parse_sections_with_headers(self):
        """Test parsing explanation with markdown headers."""
        topic = TopicMemory(
            topic_id='test',
            topic_number=1,
            title='Test',
            explanation='## Introduction\nThis is intro\n## Setup\nThis is setup'
        )
        
        sections = topic._parse_sections()
        
        assert len(sections) == 2
        assert sections[0]['heading'] == 'Introduction'
        assert 'This is intro' in sections[0]['content']
        assert sections[1]['heading'] == 'Setup'
    
    def test_topic_parse_sections_without_headers(self):
        """Test parsing explanation without headers returns empty list."""
        topic = TopicMemory(
            topic_id='test',
            topic_number=1,
            title='Test',
            explanation='Just plain text without headers'
        )
        
        sections = topic._parse_sections()
        assert sections == []
    
    def test_topic_status_transitions(self, sample_topic_memory):
        """Test topic status can be updated."""
        sample_topic_memory.status = 'pending'
        assert sample_topic_memory.status == 'pending'
        
        sample_topic_memory.status = 'generating'
        assert sample_topic_memory.status == 'generating'
        
        sample_topic_memory.status = 'complete'
        assert sample_topic_memory.status == 'complete'


class TestChapterMemory:
    """Tests for ChapterMemory class."""
    
    def test_chapter_initialization(self):
        """Test ChapterMemory initialization."""
        chapter = ChapterMemory(
            chapter_id='mod_1_ch_1',
            chapter_number=1,
            title='Test Chapter'
        )
        
        assert chapter.chapter_id == 'mod_1_ch_1'
        assert chapter.chapter_number == 1
        assert chapter.title == 'Test Chapter'
        assert chapter.topics == {}
    
    def test_add_topic(self, sample_topic_memory):
        """Test adding topic to chapter."""
        chapter = ChapterMemory(
            chapter_id='mod_1_ch_1',
            chapter_number=1,
            title='Test Chapter'
        )
        
        chapter.add_topic(sample_topic_memory)
        
        assert len(chapter.topics) == 1
        assert 'mod_1_ch_1_top_1' in chapter.topics
        assert chapter.topics['mod_1_ch_1_top_1'] == sample_topic_memory
    
    def test_chapter_to_index(self, sample_chapter_memory):
        """Test chapter index generation."""
        index = sample_chapter_memory.to_index()
        
        assert index['chapterId'] == 'mod_1_ch_1'
        assert index['chapterNumber'] == 1
        assert index['title'] == 'Getting Started'
        assert 'estimatedMinutes' in index
        assert len(index['topics']) == 1
        assert index['topics'][0]['topicId'] == 'mod_1_ch_1_top_1'
    
    def test_calculate_duration(self):
        """Test chapter duration calculation."""
        chapter = ChapterMemory(
            chapter_id='test',
            chapter_number=1,
            title='Test'
        )
        
        # Add topics with varying token counts
        topic1 = TopicMemory(
            topic_id='t1',
            topic_number=1,
            title='Topic 1',
            token_count=400
        )
        topic2 = TopicMemory(
            topic_id='t2',
            topic_number=2,
            title='Topic 2',
            token_count=600
        )
        
        chapter.add_topic(topic1)
        chapter.add_topic(topic2)
        
        duration = chapter._calculate_duration()
        # 1000 tokens / 200 = 5 minutes
        assert duration == 5
    
    def test_empty_chapter_duration(self):
        """Test minimum duration for empty chapter."""
        chapter = ChapterMemory(
            chapter_id='test',
            chapter_number=1,
            title='Test'
        )
        
        duration = chapter._calculate_duration()
        assert duration == 5  # Minimum 5 minutes


class TestModuleMemory:
    """Tests for ModuleMemory class."""
    
    def test_module_initialization(self):
        """Test ModuleMemory initialization."""
        module = ModuleMemory(
            module_id='mod_1',
            module_number=1,
            title='Test Module',
            description='Test Description'
        )
        
        assert module.module_id == 'mod_1'
        assert module.module_number == 1
        assert module.title == 'Test Module'
        assert module.description == 'Test Description'
        assert module.chapters == {}
    
    def test_add_chapter(self, sample_chapter_memory):
        """Test adding chapter to module."""
        module = ModuleMemory(
            module_id='mod_1',
            module_number=1,
            title='Test Module'
        )
        
        module.add_chapter(sample_chapter_memory)
        
        assert len(module.chapters) == 1
        assert 'mod_1_ch_1' in module.chapters
    
    def test_module_to_index(self, sample_module_memory):
        """Test module index generation."""
        index = sample_module_memory.to_index()
        
        assert index['moduleId'] == 'mod_1'
        assert index['moduleNumber'] == 1
        assert index['title'] == 'Introduction to Python'
        assert index['description'] == 'Learn Python basics'
        assert len(index['chapters']) == 1
        assert index['chapters'][0]['chapterId'] == 'mod_1_ch_1'


class TestCourseMemory:
    """Tests for CourseMemory class."""
    
    def test_course_memory_initialization(self):
        """Test CourseMemory initialization."""
        memory = CourseMemory(
            course_id=1,
            topic='Python Programming',
            level='beginner'
        )
        
        assert memory.course_id == 1
        assert memory.topic == 'Python Programming'
        assert memory.level == 'beginner'
        assert memory.modules == {}
        assert memory.created_at is not None
    
    def test_add_module(self, sample_module_memory):
        """Test adding module to course memory."""
        memory = CourseMemory(
            course_id=1,
            topic='Test',
            level='beginner'
        )
        
        memory.add_module(sample_module_memory)
        
        assert len(memory.modules) == 1
        assert 'mod_1' in memory.modules
    
    def test_get_all_topics(self, sample_course_memory):
        """Test retrieving all topics from course memory."""
        topics = sample_course_memory.get_all_topics()
        
        assert len(topics) == 1
        assert topics[0].topic_id == 'mod_1_ch_1_top_1'
    
    def test_get_all_topics_multiple_modules(self):
        """Test getting topics from multiple modules."""
        memory = CourseMemory(course_id=1, topic='Test', level='beginner')
        
        # Create 2 modules with 2 topics each
        for mod_num in range(1, 3):
            module = ModuleMemory(
                module_id=f'mod_{mod_num}',
                module_number=mod_num,
                title=f'Module {mod_num}'
            )
            
            chapter = ChapterMemory(
                chapter_id=f'mod_{mod_num}_ch_1',
                chapter_number=1,
                title='Chapter 1'
            )
            
            for top_num in range(1, 3):
                topic = TopicMemory(
                    topic_id=f'mod_{mod_num}_ch_1_top_{top_num}',
                    topic_number=top_num,
                    title=f'Topic {top_num}'
                )
                chapter.add_topic(topic)
            
            module.add_chapter(chapter)
            memory.add_module(module)
        
        topics = memory.get_all_topics()
        assert len(topics) == 4
    
    def test_get_topics_by_status(self):
        """Test filtering topics by status."""
        memory = CourseMemory(course_id=1, topic='Test', level='beginner')
        
        module = ModuleMemory(module_id='mod_1', module_number=1, title='Module')
        chapter = ChapterMemory(chapter_id='ch_1', chapter_number=1, title='Chapter')
        
        topic1 = TopicMemory(topic_id='t1', topic_number=1, title='T1', status='pending')
        topic2 = TopicMemory(topic_id='t2', topic_number=2, title='T2', status='complete')
        topic3 = TopicMemory(topic_id='t3', topic_number=3, title='T3', status='pending')
        
        chapter.add_topic(topic1)
        chapter.add_topic(topic2)
        chapter.add_topic(topic3)
        module.add_chapter(chapter)
        memory.add_module(module)
        
        pending = memory.get_topics_by_status('pending')
        complete = memory.get_topics_by_status('complete')
        
        assert len(pending) == 2
        assert len(complete) == 1
    
    def test_export_course_file(self, sample_course_memory):
        """Test exporting complete course file."""
        course_file = sample_course_memory.export_course_file()
        
        assert 'metadata' in course_file
        assert course_file['metadata']['courseId'] == 1
        assert course_file['metadata']['topic'] == 'Python Programming'
        assert course_file['metadata']['level'] == 'beginner'
        assert course_file['metadata']['version'] == '1.0'
        
        assert 'index' in course_file
        assert len(course_file['index']['modules']) == 1
        
        assert 'content' in course_file
        assert 'mod_1_ch_1_top_1' in course_file['content']
        assert course_file['content']['mod_1_ch_1_top_1']['title'] == 'Installing Python'
    
    def test_export_preserves_hierarchy(self):
        """Test export maintains proper hierarchy."""
        memory = CourseMemory(course_id=1, topic='Test', level='advanced')
        
        # Create hierarchical structure
        module = ModuleMemory(module_id='mod_1', module_number=1, title='Module 1')
        chapter = ChapterMemory(chapter_id='mod_1_ch_1', chapter_number=1, title='Chapter 1')
        topic = TopicMemory(
            topic_id='mod_1_ch_1_top_1',
            topic_number=1,
            title='Topic 1',
            key_points=['Point A', 'Point B'],
            status='complete'
        )
        
        chapter.add_topic(topic)
        module.add_chapter(chapter)
        memory.add_module(module)
        
        exported = memory.export_course_file()
        
        # Verify hierarchy in index
        assert exported['index']['modules'][0]['moduleId'] == 'mod_1'
        assert exported['index']['modules'][0]['chapters'][0]['chapterId'] == 'mod_1_ch_1'
        assert exported['index']['modules'][0]['chapters'][0]['topics'][0]['topicId'] == 'mod_1_ch_1_top_1'
        
        # Verify content is accessible by topic ID
        assert exported['content']['mod_1_ch_1_top_1']['keyPoints'] == ['Point A', 'Point B']
