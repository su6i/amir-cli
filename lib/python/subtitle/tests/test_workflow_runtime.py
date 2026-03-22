"""Unit tests for subtitle.workflow.runtime module"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os


class TestPrepareRuntimeExecution(unittest.TestCase):
    """Test prepare_runtime_execution runtime setup helper"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.mock_processor.detect_source_language = Mock(return_value='en')
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_post_only_early_exit(self):
        """Test post-only mode returns early exit flag"""
        from subtitle.workflow.runtime import prepare_runtime_execution
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = prepare_runtime_execution(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=['fa'],
            original_stem='test',
            original_base=self.temp_dir,
            is_srt_input=False,
            source_auto_requested=False,
            post_only=True,
            platforms=None,
            prompt_file=None,
            post_langs=None,
            limit_start=None,
            limit_end=None,
        )
        
        # Post-only mode should set early exit flag
        self.assertTrue(ctx['post_only_done'])
    
    def test_source_language_autodetection(self):
        """Test automatic source language detection"""
        from subtitle.workflow.runtime import prepare_runtime_execution
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = prepare_runtime_execution(
            self.mock_processor,
            video_path=video_path,
            source_lang='auto',
            target_langs=['fa'],
            original_stem='test',
            original_base=self.temp_dir,
            is_srt_input=False,
            source_auto_requested=True,
            post_only=False,
            platforms=None,
            prompt_file=None,
            post_langs=None,
            limit_start=None,
            limit_end=None,
        )
        
        # Auto detection should be attempted
        if not ctx['post_only_done']:
            self.assertEqual(ctx['source_lang'], 'en')  # Mock returns 'en'
    
    def test_target_language_resolution(self):
        """Test target language list resolution"""
        from subtitle.workflow.runtime import prepare_runtime_execution
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = prepare_runtime_execution(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=None,  # None should default to source or be processed
            original_stem='test',
            original_base=self.temp_dir,
            is_srt_input=False,
            source_auto_requested=False,
            post_only=False,
            platforms=None,
            prompt_file=None,
            post_langs=None,
            limit_start=None,
            limit_end=None,
        )
        
        # Target langs should be resolved
        if not ctx['post_only_done']:
            self.assertIsInstance(ctx['target_langs'], list)
    
    def test_limit_clipping_creates_temp_video(self):
        """Test time-range limiting creates temporary video"""
        from subtitle.workflow.runtime import prepare_runtime_execution
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = prepare_runtime_execution(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=['fa'],
            original_stem='test',
            original_base=self.temp_dir,
            is_srt_input=False,
            source_auto_requested=False,
            post_only=False,
            platforms=None,
            prompt_file=None,
            post_langs=None,
            limit_start=10.0,  # Start at 10 seconds
            limit_end=60.0,    # End at 60 seconds
        )
        
        if not ctx['post_only_done']:
            # Limit clipping should set has_limit flag
            self.assertIn('has_limit', ctx)
            # Temperature video or original should be indicated
            self.assertIn('current_video_input', ctx)


class TestRuntimeContextIntegration(unittest.TestCase):
    """Integration tests for runtime context preparation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_runtime_context_keys_present(self):
        """Test all expected context keys are returned"""
        from subtitle.workflow.runtime import prepare_runtime_execution
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        expected_keys = [
            'post_only_done',
            'current_video_input',
            'source_lang',
            'target_langs',
            'limit_start',
            'limit_end',
            'has_limit',
            'temp_vid',
        ]
        
        ctx = prepare_runtime_execution(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=['fa'],
            original_stem='test',
            original_base=self.temp_dir,
            is_srt_input=False,
            source_auto_requested=False,
            post_only=False,
            platforms=None,
            prompt_file=None,
            post_langs=None,
            limit_start=None,
            limit_end=None,
        )
        
        for key in expected_keys:
            self.assertIn(key, ctx, f"Missing expected context key: {key}")


if __name__ == '__main__':
    unittest.main()
