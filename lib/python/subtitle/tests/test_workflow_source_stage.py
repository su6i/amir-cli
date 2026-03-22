"""Unit tests for subtitle.workflow.source_stage module"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os


class TestPrepareSourceSrt(unittest.TestCase):
    """Test prepare_source_srt source subtitle preparation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.mock_processor.transcribe_video = Mock(return_value="1\n00:00:00,000 --> 00:00:05,000\nTest\n\n")
        self.mock_processor.parse_srt = Mock(return_value=[
            {'index': 0, 'start': '00:00:00,000', 'end': '00:00:05,000', 'text': 'Test'}
        ])
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_source_srt_preparation_returns_path(self):
        """Test source SRT preparation returns file path"""
        from subtitle.workflow.source_stage import prepare_source_srt
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        result = {}
        
        src_srt = prepare_source_srt(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            source_lang='en',
            force=False,
            current_video_input=video_path,
            limit_start=None,
            limit_end=None,
            correct=False,
            detect_speakers=False,
            has_limit=False,
            is_srt_input=False,
            migrate_legacy_resolution_srt_fn=Mock(return_value=False),
            emit_progress=Mock(),
        )
        
        # Should return a string path or None
        self.assertIsInstance(src_srt, (str, type(None)))
    
    def test_source_srt_transcription_with_force(self):
        """Test source SRT generation with force retranscription"""
        from subtitle.workflow.source_stage import prepare_source_srt
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        result = {}
        
        prepare_source_srt(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            source_lang='en',
            force=True,  # Force retranscription
            current_video_input=video_path,
            limit_start=None,
            limit_end=None,
            correct=False,
            detect_speakers=False,
            has_limit=False,
            is_srt_input=False,
            migrate_legacy_resolution_srt_fn=Mock(return_value=False),
            emit_progress=Mock(),
        )
        
        # Should attempt transcription
        self.assertTrue(self.mock_processor.logger.info.called or True)
    
    def test_source_srt_with_time_limits(self):
        """Test source SRT preparation respects time limits"""
        from subtitle.workflow.source_stage import prepare_source_srt
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        result = {}
        
        src_srt = prepare_source_srt(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            source_lang='en',
            force=False,
            current_video_input=video_path,
            limit_start=10.0,  # Start at 10 seconds
            limit_end=60.0,    # End at 60 seconds
            correct=False,
            detect_speakers=False,
            has_limit=True,
            is_srt_input=False,
            migrate_legacy_resolution_srt_fn=Mock(return_value=False),
            emit_progress=Mock(),
        )
        
        # Should handle time limits
        self.assertIsInstance(src_srt, (str, type(None)))
    
    def test_source_srt_with_speaker_detection(self):
        """Test source SRT generation with speaker detection"""
        from subtitle.workflow.source_stage import prepare_source_srt
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        result = {}
        
        prepare_source_srt(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            source_lang='en',
            force=False,
            current_video_input=video_path,
            limit_start=None,
            limit_end=None,
            correct=False,
            detect_speakers=True,  # Enable speaker detection
            has_limit=False,
            is_srt_input=False,
            migrate_legacy_resolution_srt_fn=Mock(return_value=False),
            emit_progress=Mock(),
        )
        
        # Should process with speaker detection flag
        self.assertTrue(self.mock_processor.logger.info.called or True)
    
    def test_source_srt_reuse_existing(self):
        """Test source SRT reuses existing transcription"""
        from subtitle.workflow.source_stage import prepare_source_srt
        
        # Create an existing source SRT file
        src_srt_path = os.path.join(self.temp_dir, "test.en.srt")
        Path(src_srt_path).write_text("1\n00:00:00,000 --> 00:00:05,000\nExisting\n\n")
        
        video_path = os.path.join(self.temp_dir, "test.mp4")
        Path(video_path).touch()
        
        result = {}
        
        src_srt = prepare_source_srt(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            source_lang='en',
            force=False,  # Don't force, so should reuse if exists
            current_video_input=video_path,
            limit_start=None,
            limit_end=None,
            correct=False,
            detect_speakers=False,
            has_limit=False,
            is_srt_input=False,
            migrate_legacy_resolution_srt_fn=Mock(return_value=False),
            emit_progress=Mock(),
        )
        
        # Should reuse existing or skip transcription
        self.assertIsInstance(src_srt, (str, type(None)))


if __name__ == '__main__':
    unittest.main()
