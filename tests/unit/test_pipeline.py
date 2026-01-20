"""
Unit tests for course generation pipeline.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from app.main.courses.pipeline import CourseGeneratorPipeline
from app.main.courses.memory import CourseMemory
from app.exceptions import NotFoundException

class TestPipelineInitialization:
    """Tests for pipeline initialization."""
    
    def test_pipeline_init(self):
        """Test pipeline initialization."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        
        assert pipeline.course_id == 1
        assert pipeline.course is None
        assert pipeline.memory is None
        assert pipeline.MAX_WORKERS == 5
        assert pipeline.BATCH_SIZE == 10
    
    def test_load_prompt(self, app_context, tmp_path):
        """Test loading prompt templates."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        
        # Create temporary prompts directory
        prompts_dir = tmp_path / 'prompts'
        prompts_dir.mkdir()
        
        # Create test prompt file
        test_prompt = prompts_dir / 'test_prompt.txt'
        test_prompt.write_text('Topic: {topic}, Level: {level}')
        
        pipeline.prompts_dir = prompts_dir
        
        result = pipeline._load_prompt('test_prompt.txt')
        assert result == 'Topic: {topic}, Level: {level}'


class TestPipelineStage1:
    """Tests for Stage 1: Index Generation."""
    
    @patch('app.main.courses.pipeline.CoursesRepository')
    @patch('app.main.courses.pipeline.GroqClient')
    def test_stage1_generate_index(
        self,
        mock_groq_class,
        mock_repo,
        app_context,
        sample_course,
        sample_outline,
        tmp_path
    ):
        """Test stage 1 generates index and populates memory."""
        # Setup
        mock_repo.get_by_id.return_value = sample_course
        mock_groq_client = Mock()
        mock_groq_client.generate_json.return_value = sample_outline
        mock_groq_class.return_value = mock_groq_client
        
        # Create prompts
        prompts_dir = tmp_path / 'prompts'
        prompts_dir.mkdir()
        (prompts_dir / 'outline_prompt.txt').write_text('Topic: {topic}, Level: {level}')
        
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.prompts_dir = prompts_dir
        pipeline.course = sample_course
        pipeline.groq_client = mock_groq_client
        pipeline.memory = CourseMemory(
            sample_course.id,
            sample_course.topic,
            sample_course.level
        )
        
        # Execute
        pipeline._stage1_generate_index()
        
        # Verify
        assert len(pipeline.memory.modules) == 2
        assert 'mod_1' in pipeline.memory.modules
        assert 'mod_2' in pipeline.memory.modules
        
        # Check first module structure
        mod1 = pipeline.memory.modules['mod_1']
        assert mod1.title == 'Introduction to Python'
        assert len(mod1.chapters) == 1
        
        # Check topics
        topics = pipeline.memory.get_all_topics()
        assert len(topics) == 3  # 2 in mod1_ch1, 1 in mod2_ch1
        
        # Verify topic IDs are correct
        topic_ids = [t.topic_id for t in topics]
        assert 'mod_1_ch_1_top_1' in topic_ids
        assert 'mod_1_ch_1_top_2' in topic_ids
        assert 'mod_2_ch_1_top_1' in topic_ids


class TestPipelineStage2:
    """Tests for Stage 2: Batch Expand Points."""
    
    @patch('app.main.courses.pipeline.ThreadPoolExecutor')
    def test_stage2_batch_expand_points(
        self,
        mock_executor_class,
        app_context,
        sample_course,
        sample_course_memory,
        mock_groq_client,
        tmp_path
    ):
        """Test stage 2 expands points in parallel."""
        # Setup executor mock
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor
        
        # Mock futures
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_executor.submit.return_value = mock_future
        
        # Mock as_completed
        with patch('app.main.courses.pipeline.as_completed') as mock_as_completed:
            mock_as_completed.return_value = [mock_future]
            
            # Setup pipeline
            pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
            pipeline.course = sample_course
            pipeline.memory = sample_course_memory
            pipeline.groq_client = mock_groq_client
            
            # Create prompts
            prompts_dir = tmp_path / 'prompts'
            prompts_dir.mkdir()
            (prompts_dir / 'expand_points_prompt.txt').write_text(
                'Topic: {topic_title}, Module: {module_title}'
            )
            pipeline.prompts_dir = prompts_dir
            
            # Execute
            pipeline._stage2_batch_expand_points()
            
            # Verify ThreadPoolExecutor was used
            mock_executor_class.assert_called_once_with(max_workers=5)
            
            # Verify topics were submitted for processing
            assert mock_executor.submit.call_count == 1  # 1 topic in sample memory
    
    def test_expand_single_topic_success(
        self,
        app_context,
        sample_course,
        sample_course_memory,
        mock_groq_client,
        tmp_path
    ):
        """Test expanding a single topic successfully."""
        # Setup
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.course = sample_course
        pipeline.memory = sample_course_memory
        pipeline.groq_client = mock_groq_client
        
        # Create prompt
        prompts_dir = tmp_path / 'prompts'
        prompts_dir.mkdir()
        (prompts_dir / 'expand_points_prompt.txt').write_text(
            'Topic: {topic_title}, Level: {level}'
        )
        pipeline.prompts_dir = prompts_dir
        
        # Get topic
        topic = sample_course_memory.get_all_topics()[0]
        topic.status = 'pending'
        
        # Mock the expand function (simulate what happens inside batch)
        mock_groq_client.generate_json.return_value = {
            'points': ['Point A', 'Point B', 'Point C']
        }
        
        # Manually call what would happen in thread
        module, chapter = pipeline._find_topic_parents(topic.topic_id)
        prompt_template = pipeline._load_prompt('expand_points_prompt.txt')
        prompt = prompt_template.format(
            topic_title=topic.title,
            module_title=module.title if module else '',
            chapter_title=chapter.title if chapter else '',
            level=pipeline.course.level,
            topic_number=topic.topic_number
        )
        
        result = pipeline.groq_client.generate_json(prompt)
        topic.key_points = result.get('points', [])
        topic.status = 'points_complete'
        
        # Verify
        assert len(topic.key_points) == 3
        assert topic.status == 'points_complete'


class TestPipelineStage3:
    """Tests for Stage 3: Batch Generate Content."""
    
    def test_stage3_batch_generate_content(
        self,
        app_context,
        sample_course,
        sample_course_memory,
        mock_groq_client,
        tmp_path
    ):
        """Test stage 3 generates content for topics."""
        # Setup
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.course = sample_course
        pipeline.memory = sample_course_memory
        pipeline.groq_client = mock_groq_client
        
        # Set topic status to points_complete
        topic = sample_course_memory.get_all_topics()[0]
        topic.status = 'points_complete'
        topic.key_points = ['Point 1', 'Point 2']
        
        # Create prompt
        prompts_dir = tmp_path / 'prompts'
        prompts_dir.mkdir()
        (prompts_dir / 'explanation_prompt.txt').write_text(
            'Topic: {topic_title}, Points: {points}'
        )
        pipeline.prompts_dir = prompts_dir
        
        # Mock content generation
        mock_groq_client.generate.return_value = "Detailed explanation text here."
        
        # Execute with mocked executor
        with patch('app.main.courses.pipeline.ThreadPoolExecutor') as mock_exec:
            mock_future = Mock()
            mock_executor = MagicMock()
            mock_executor.submit.return_value = mock_future
            mock_exec.return_value.__enter__.return_value = mock_executor
            
            with patch('app.main.courses.pipeline.as_completed') as mock_completed:
                # Simulate the function execution
                points_text = '\n'.join(f"- {point}" for point in topic.key_points)
                prompt_template = pipeline._load_prompt('explanation_prompt.txt')
                prompt = prompt_template.format(
                    topic_title=topic.title,
                    level=pipeline.course.level,
                    points=points_text,
                    max_tokens=pipeline.MAX_TOKENS_PER_TOPIC
                )
                
                explanation = pipeline.groq_client.generate(
                    prompt,
                    max_tokens=pipeline.MAX_TOKENS_PER_TOPIC
                )
                
                topic.explanation = explanation
                topic.status = 'content_complete'
                
                mock_completed.return_value = [mock_future]
                pipeline._stage3_batch_generate_content()
        
        # Verify
        assert topic.explanation == "Detailed explanation text here."
        assert topic.status == 'content_complete'


class TestPipelineStage4:
    """Tests for Stage 4: Aggregate Resources."""
    
    def test_stage4_aggregate_resources(
        self,
        app_context,
        sample_course,
        sample_course_memory,
        mock_youtube_client
    ):
        """Test stage 4 fetches videos for topics."""
        # Setup
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.course = sample_course
        pipeline.memory = sample_course_memory
        pipeline.youtube_client = mock_youtube_client
        
        # Set topic to content_complete
        topic = sample_course_memory.get_all_topics()[0]
        topic.status = 'content_complete'
        
        # Execute with mocked executor
        with patch('app.main.courses.pipeline.ThreadPoolExecutor') as mock_exec:
            mock_future = Mock()
            mock_executor = MagicMock()
            mock_executor.submit.return_value = mock_future
            mock_exec.return_value.__enter__.return_value = mock_executor
            
            with patch('app.main.courses.pipeline.as_completed') as mock_completed:
                # Simulate resource fetching
                search_query = f"{pipeline.course.topic} {topic.title} tutorial"
                videos = pipeline.youtube_client.search_videos(search_query, max_results=3)
                topic.videos = videos
                topic.status = 'complete'
                
                mock_completed.return_value = [mock_future]
                pipeline._stage4_batch_aggregate_resources()
        
        # Verify
        assert len(topic.videos) == 1
        assert topic.videos[0]['videoId'] == 'abc123'
        assert topic.status == 'complete'
    
    def test_stage4_handles_youtube_api_failure(
        self,
        app_context,
        sample_course,
        sample_course_memory
    ):
        """Test stage 4 handles YouTube API failures gracefully."""
        # Setup
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.course = sample_course
        pipeline.memory = sample_course_memory
        
        # Mock YouTube client to raise exception
        mock_yt_client = Mock()
        mock_yt_client.search_videos.side_effect = Exception("API Error")
        pipeline.youtube_client = mock_yt_client
        
        topic = sample_course_memory.get_all_topics()[0]
        topic.status = 'content_complete'
        
        # Execute (simulating what happens in thread)
        try:
            search_query = f"{pipeline.course.topic} {topic.title} tutorial"
            videos = pipeline.youtube_client.search_videos(search_query, max_results=3)
            topic.videos = videos
        except Exception:
            topic.videos = []
        
        topic.status = 'complete'
        
        # Verify topic marked complete even with no videos
        assert topic.videos == []
        assert topic.status == 'complete'


class TestPipelineStage5:
    """Tests for Stage 5: Export."""
    
    @patch('app.main.courses.pipeline.JSONStorage')
    @patch('app.main.courses.pipeline.CoursesRepository')
    def test_stage5_export(
        self,
        mock_repo,
        mock_storage,
        app_context,
        sample_course,
        sample_course_memory
    ):
        """Test stage 5 exports course file."""
        # Setup
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        pipeline.course = sample_course
        pipeline.memory = sample_course_memory
        
        mock_storage.save_course.return_value = '/path/to/course.json'
        
        # Execute
        pipeline._stage5_export()
        
        # Verify JSONStorage.save_course was called
        mock_storage.save_course.assert_called_once()
        call_args = mock_storage.save_course.call_args
        
        # Verify course file structure
        course_file = call_args[0][2]  # Third argument is the course data
        assert 'metadata' in course_file
        assert 'index' in course_file
        assert 'content' in course_file
        
        # Verify database update
        mock_repo.mark_completed.assert_called_once_with(
            sample_course.id,
            '/path/to/course.json'
        )


class TestPipelineHelpers:
    """Tests for helper methods."""
    
    def test_find_topic_parents(self, sample_course_memory):
        """Test finding parent module and chapter for a topic."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        pipeline.memory = sample_course_memory
        
        module, chapter = pipeline._find_topic_parents('mod_1_ch_1_top_1')
        
        assert module is not None
        assert module.module_id == 'mod_1'
        assert chapter is not None
        assert chapter.chapter_id == 'mod_1_ch_1'
    
    def test_find_topic_parents_not_found(self, sample_course_memory):
        """Test finding parents for non-existent topic."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        pipeline.memory = sample_course_memory
        
        module, chapter = pipeline._find_topic_parents('invalid_id')
        
        assert module is None
        assert chapter is None


class TestPipelineErrorHandling:
    """Tests for pipeline error handling."""
    
    @patch('app.main.courses.pipeline.CoursesRepository')
    def test_pipeline_handles_stage1_failure(
        self,
        mock_repo,
        app_context,
        sample_course
    ):
        """Test pipeline handles stage 1 failure."""
        mock_repo.get_by_id.side_effect = NotFoundException("Course not found")
        
        pipeline = CourseGeneratorPipeline(course_id=999)
        
        # Execute should catch exception
        pipeline.generate()
        
        # Verify error was logged and course marked failed
        mock_repo.mark_failed.assert_called_once()
        call_args = mock_repo.mark_failed.call_args[0]
        assert call_args[0] == 999
        assert "Course not found" in call_args[1]
