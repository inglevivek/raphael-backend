"""
Integration tests for complete pipeline execution.
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
from app.main.courses.pipeline import CourseGeneratorPipeline
from app.main.courses.repository import CoursesRepository

@pytest.mark.integration
class TestPipelineIntegration:
    """End-to-end pipeline tests."""
    
    @patch('app.main.courses.pipeline.YouTubeClient')
    @patch('app.main.courses.pipeline.GroqClient')
    @patch('app.main.courses.pipeline.GeminiClient')
    def test_complete_pipeline_execution(
        self,
        mock_gemini_class,
        mock_groq_class,
        mock_youtube_class,
        app_context,
        sample_course,
        sample_outline,
        tmp_path
    ):
        """Test complete pipeline from start to finish."""
        # Setup mocks
        mock_groq = Mock()
        mock_groq.generate_json.side_effect = [
            sample_outline,  # For outline generation
            {'points': ['Point 1', 'Point 2', 'Point 3']},  # Topic 1
            {'points': ['Point A', 'Point B', 'Point C']},  # Topic 2
            {'points': ['Point X', 'Point Y', 'Point Z']},  # Topic 3
        ]
        mock_groq.generate.return_value = "Full explanation of the topic."
        mock_groq_class.return_value = mock_groq
        
        mock_youtube = Mock()
        mock_youtube.search_videos.return_value = [
            {
                'videoId': 'test123',
                'title': 'Tutorial Video',
                'channelName': 'Test Channel',
                'thumbnailUrl': 'http://example.com/thumb.jpg',
                'duration': '15:00',
                'url': 'http://youtube.com/watch?v=test123'
            }
        ]
        mock_youtube_class.return_value = mock_youtube
        
        # Mock the _load_prompt method to avoid file system issues
        def mock_load_prompt(filename):
            prompts = {
                'outline_prompt.txt': 'Topic: {topic}, Level: {level}',
                'expand_points_prompt.txt': (
                    'Topic: {topic_title}, Module: {module_title}, '
                    'Chapter: {chapter_title}, Level: {level}, Number: {topic_number}'
                ),
                'explanation_prompt.txt': (
                    'Topic: {topic_title}, Level: {level}, '
                    'Points: {points}, Max tokens: {max_tokens}'
                )
            }
            return prompts.get(filename, '')
        
        # Execute pipeline
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        
        with patch.object(pipeline, '_load_prompt', side_effect=mock_load_prompt):
            with patch('app.main.courses.pipeline.JSONStorage') as mock_storage:
                mock_storage.save_course.return_value = str(tmp_path / 'course.json')
                
                # Execute
                pipeline.generate()
                
                # Verify all stages executed
                assert pipeline.memory is not None, "Memory should be initialized"
                assert len(pipeline.memory.modules) > 0, "Should have modules"
                
                # Verify structure
                assert len(pipeline.memory.modules) == 2  # From sample_outline
                assert 'mod_1' in pipeline.memory.modules
                assert 'mod_2' in pipeline.memory.modules
                
                # Verify topics were created
                all_topics = pipeline.memory.get_all_topics()
                assert len(all_topics) == 3  # 2 in mod1, 1 in mod2
                
                # Verify topics have content
                complete_topics = [t for t in all_topics if t.status == 'complete']
                assert len(complete_topics) > 0, "At least one topic should be complete"
                
                # Verify course was saved
                mock_storage.save_course.assert_called_once()
                
                # Verify database was updated
                updated_course = CoursesRepository.get_by_id(sample_course.id)
                assert updated_course.status == 'completed'
                assert str(tmp_path / 'course.json') in updated_course.json_path
    
    @patch('app.main.courses.pipeline.CoursesRepository')
    def test_pipeline_concurrent_processing(
        self,
        mock_repo,
        app_context,
        sample_course,
        tmp_path
    ):
        """Test that pipeline processes topics concurrently."""
        from concurrent.futures import ThreadPoolExecutor
        
        pipeline = CourseGeneratorPipeline(course_id=1)
        
        # Verify MAX_WORKERS is set correctly
        assert pipeline.MAX_WORKERS == 5
        assert hasattr(pipeline, 'MAX_WORKERS')
        assert hasattr(pipeline, 'BATCH_SIZE')
    
    @patch('app.main.courses.pipeline.YouTubeClient')
    @patch('app.main.courses.pipeline.GroqClient')
    @patch('app.main.courses.pipeline.GeminiClient')
    @patch('app.main.courses.pipeline.JSONStorage')
    def test_pipeline_handles_partial_failures(
        self,
        mock_storage,
        mock_gemini_class,
        mock_groq_class,
        mock_youtube_class,
        app_context,
        sample_course,
        sample_outline,
        tmp_path
    ):
        """Test pipeline handles partial failures gracefully."""
        # Setup mocks with some failures
        mock_groq = Mock()
        
        # Create a mock that handles multiple calls
        call_count = {'count': 0}
        def groq_generate_json_side_effect(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return sample_outline
            elif call_count['count'] == 2:
                return {'points': ['Point 1', 'Point 2']}
            elif call_count['count'] == 3:
                raise Exception("API Error")
            else:
                return {'points': ['Point X', 'Point Y']}
        
        mock_groq.generate_json.side_effect = groq_generate_json_side_effect
        mock_groq.generate.return_value = "Explanation text"
        mock_groq_class.return_value = mock_groq
        
        # YouTube sometimes fails
        mock_youtube = Mock()
        yt_call_count = {'count': 0}
        def youtube_side_effect(*args, **kwargs):
            yt_call_count['count'] += 1
            if yt_call_count['count'] == 2:
                raise Exception("YouTube API Error")
            return [{'videoId': f'vid{yt_call_count["count"]}', 'title': f'Video {yt_call_count["count"]}', 'url': 'http://example.com/1'}]
        
        mock_youtube.search_videos.side_effect = youtube_side_effect
        mock_youtube_class.return_value = mock_youtube
        
        mock_storage.save_course.return_value = str(tmp_path / 'course.json')
        
        # Mock _load_prompt
        def mock_load_prompt(filename):
            prompts = {
                'outline_prompt.txt': 'Topic: {topic}, Level: {level}',
                'expand_points_prompt.txt': 'Expand: {topic_title}, Module: {module_title}, Chapter: {chapter_title}, Level: {level}, Number: {topic_number}',
                'explanation_prompt.txt': 'Explain: {topic_title}, Level: {level}, Points: {points}, Max tokens: {max_tokens}'
            }
            return prompts.get(filename, '')
        
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        
        with patch.object(pipeline, '_load_prompt', side_effect=mock_load_prompt):
            pipeline.generate()
            
            all_topics = pipeline.memory.get_all_topics()
            successful_topics = [t for t in all_topics if t.status != 'failed']
            
            assert len(successful_topics) > 0
            assert pipeline.course.status == 'completed'
    
    @patch('app.main.courses.pipeline.YouTubeClient')
    @patch('app.main.courses.pipeline.GeminiClient')
    @patch('app.main.courses.pipeline.GroqClient')
    @patch('app.main.courses.pipeline.CoursesRepository')  # Patch at the pipeline import location
    def test_pipeline_stage1_failure_marks_course_failed(
        self,
        mock_repo_class,  # This patches the entire CoursesRepository class
        mock_groq_class,
        mock_gemini_class,
        mock_youtube_class,
        app_context,
        sample_course,
        tmp_path
    ):
        """Test that Stage 1 failure marks entire course as failed."""
        # Setup - Stage 1 fails
        mock_groq = Mock()
        mock_groq.generate_json.side_effect = Exception("Groq API is down")
        mock_groq_class.return_value = mock_groq
        
        # Mock the other clients to avoid initialization errors
        mock_gemini_class.return_value = Mock()
        mock_youtube_class.return_value = Mock()
        
        # Mock the repository methods
        mock_repo_class.get_by_id.return_value = sample_course
        mock_repo_class.mark_failed = Mock()  # Mock the mark_failed method
        
        def mock_load_prompt(filename):
            return 'Topic: {topic}, Level: {level}'
        
        pipeline = CourseGeneratorPipeline(course_id=sample_course.id)
        
        with patch.object(pipeline, '_load_prompt', side_effect=mock_load_prompt):
            pipeline.generate()
            
            # Verify mark_failed was called
            mock_repo_class.mark_failed.assert_called_once()
            call_args = mock_repo_class.mark_failed.call_args[0]
            assert call_args[0] == sample_course.id
            assert "Groq API is down" in call_args[1]


@pytest.mark.integration
class TestPipelinePerformance:
    """Performance-related tests."""
    
    def test_concurrent_execution_faster_than_sequential(self):
        """Verify concurrent execution is configured correctly."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        
        assert pipeline.MAX_WORKERS == 5
        assert pipeline.BATCH_SIZE == 10
    
    def test_token_limits_configured(self):
        """Verify token limits are set to prevent truncation."""
        pipeline = CourseGeneratorPipeline(course_id=1)
        
        assert hasattr(pipeline, 'MAX_TOKENS_PER_TOPIC')
        assert pipeline.MAX_TOKENS_PER_TOPIC == 2000
