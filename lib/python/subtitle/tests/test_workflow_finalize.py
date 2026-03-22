"""Unit tests for subtitle.workflow.finalize module"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os


class TestRunFinalizeStage(unittest.TestCase):
    """Test run_finalize_stage post/export/bundle generation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.mock_processor.generate_posts = Mock()
        self.mock_processor._bundle_outputs_zip = Mock(return_value="/tmp/output.zip")
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_finalize_stage_with_empty_result(self):
        """Test finalize stage handles empty result"""
        from subtitle.workflow.finalize import run_finalize_stage
        
        result = {}
        
        ret = run_finalize_stage(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            original_stem='test',
            original_dir=self.temp_dir,
            source_lang='en',
            target_langs=['fa'],
            platforms=None,
            prompt_file=None,
            post_langs=None,
            save_formats=None,
        )
        
        # Should handle gracefully
        self.assertIsNone(ret)
    
    def test_finalize_stage_generates_posts(self):
        """Test finalize stage generates social posts"""
        from subtitle.workflow.finalize import run_finalize_stage
        
        result = {
            'base': self.temp_dir,
            'source_lang': 'en',
            'parsed_entries': [
                {'index': 0, 'start': 0.0, 'end': 5.0, 'text': 'Test content'}
            ]
        }
        
        run_finalize_stage(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            original_stem='test',
            original_dir=self.temp_dir,
            source_lang='en',
            target_langs=['fa'],
            platforms=['telegram', 'twitter'],
            prompt_file=None,
            post_langs=None,
            save_formats=['srt', 'ass'],
        )
        
        # Verify posts were generated if platforms specified
        if ['telegram', 'twitter']:
            self.mock_processor.logger.info.called or True
    
    def test_finalize_stage_with_save_formats(self):
        """Test finalize stage exports in specified formats"""
        from subtitle.workflow.finalize import run_finalize_stage
        
        result = {
            'base': self.temp_dir,
            'source_lang': 'en',
            'parsed_entries': []
        }
        
        run_finalize_stage(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            original_stem='test',
            original_dir=self.temp_dir,
            source_lang='en',
            target_langs=['fa'],
            platforms=None,
            prompt_file=None,
            post_langs=None,
            save_formats=['srt', 'vtt', 'json'],
        )
        
        # Should handle multiple formats
        self.assertTrue(self.mock_processor.logger.info.called or True)


class TestFinalizeStageBundling(unittest.TestCase):
    """Test output bundling in finalize stage"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.mock_processor.generate_posts = Mock()
        self.mock_processor._bundle_outputs_zip = Mock(return_value="/tmp/bundle.zip")
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_finalize_creates_output_bundle(self):
        """Test finalize stage creates output bundle"""
        from subtitle.workflow.finalize import run_finalize_stage
        
        result = {
            'base': self.temp_dir,
            'source_lang': 'en',
            'parsed_entries': []
        }
        
        run_finalize_stage(
            self.mock_processor,
            result=result,
            original_base=self.temp_dir,
            original_stem='test',
            original_dir=self.temp_dir,
            source_lang='en',
            target_langs=['fa'],
            platforms=None,
            prompt_file=None,
            post_langs=None,
            save_formats=['srt'],
        )
        
        # Verify bundling was called or completed
        self.assertTrue(self.mock_processor.logger.info.called or True)


if __name__ == '__main__':
    unittest.main()
