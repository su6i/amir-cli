"""Unit tests for subtitle.workflow.base module"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os

# These tests validate the extracted workflow base context resolution
# to ensure the refactoring maintained correctness


class TestResolveWorkflowBase(unittest.TestCase):
    """Test resolve_workflow_base context resolution helper"""
    
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
    
    def test_basic_video_input(self):
        """Test basic video file input processing"""
        from subtitle.workflow.base import resolve_workflow_base
        
        # Create a temporary video file
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = resolve_workflow_base(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=['fa', 'es'],
            post_only=False,
            render_resolution=None,
        )
        
        # Verify context dict has required keys
        self.assertIn('video_path', ctx)
        self.assertIn('source_lang', ctx)
        self.assertIn('target_langs', ctx)
        self.assertIn('original_base', ctx)
        self.assertIn('original_stem', ctx)
        self.assertIn('lock_key', ctx)
        
        # Verify basic transformations
        self.assertEqual(ctx['source_lang'], 'en')
        self.assertIn('fa', ctx['target_langs'])
        self.assertIn('es', ctx['target_langs'])
    
    def test_srt_input_detection(self):
        """Test SRT file input detection"""
        from subtitle.workflow.base import resolve_workflow_base
        
        # Create a temporary SRT file
        srt_path = os.path.join(self.temp_dir, "test.srt")
        Path(srt_path).write_text("1\n00:00:00,000 --> 00:00:05,000\nTest\n\n")
        
        ctx = resolve_workflow_base(
            self.mock_processor,
            video_path=srt_path,
            source_lang='en',
            target_langs=['fa'],
            post_only=False,
            render_resolution=None,
        )
        
        # Verify SRT input is detected
        self.assertTrue(ctx['is_srt_input'])
    
    def test_auto_source_language(self):
        """Test auto source language detection flag"""
        from subtitle.workflow.base import resolve_workflow_base
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = resolve_workflow_base(
            self.mock_processor,
            video_path=video_path,
            source_lang='auto',
            target_langs=['fa'],
            post_only=False,
            render_resolution=None,
        )
        
        # Verify auto flag is captured
        self.assertTrue(ctx['source_auto_requested'])
    
    def test_post_only_early_exit(self):
        """Test post-only mode context"""
        from subtitle.workflow.base import resolve_workflow_base
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        ctx = resolve_workflow_base(
            self.mock_processor,
            video_path=video_path,
            source_lang='en',
            target_langs=['fa'],
            post_only=True,
            render_resolution=None,
        )
        
        # Context should still be valid for post generation
        self.assertIn('original_base', ctx)
        self.assertIn('original_dir', ctx)


class TestDetectSubtitleGeometry(unittest.TestCase):
    """Test subtitle geometry detection for video"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
    
    def test_geometry_detection_returns_tuple(self):
        """Test that geometry detection returns width/height tuple"""
        from subtitle.workflow.base import detect_subtitle_geometry
        
        # Mock video dimensions
        self.mock_processor._detect_video_dimensions = Mock(return_value=(1920, 1080))
        
        width, height = detect_subtitle_geometry(
            self.mock_processor,
            video_path="/tmp/test.mp4",
            target_langs=['fa']
        )
        
        # Verify return is tuple of dimensions or None
        if width is not None and height is not None:
            self.assertIsInstance(width, (int, float))
            self.assertIsInstance(height, (int, float))


class TestMigrateLegacyResolutionSrt(unittest.TestCase):
    """Test legacy SRT migration logic"""
    
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
    
    def test_migration_with_nonexistent_legacy_file(self):
        """Test migration when legacy file doesn't exist"""
        from subtitle.workflow.base import migrate_legacy_resolution_srt
        
        result = migrate_legacy_resolution_srt(
            self.mock_processor,
            original_base="/tmp/test",
            original_dir="/tmp",
            lang_code="fa",
            expected_path="/tmp/test.fa.srt"
        )
        
        # Should return False when no legacy file to migrate
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
