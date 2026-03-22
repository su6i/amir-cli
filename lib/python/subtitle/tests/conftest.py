"""Common test utilities and fixtures for subtitle tests"""
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from typing import Optional


class TempWorkspace:
    """Context manager for temporary test workspace"""
    
    def __init__(self):
        self.temp_dir = None
    
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)


def create_mock_processor(
    transcribe_result: Optional[str] = None,
    detect_language_result: str = 'en',
    **kwargs
) -> Mock:
    """Create a mock processor with common method stubs"""
    
    processor = Mock()
    processor.logger = Mock()
    processor.logger.info = Mock()
    processor.logger.warning = Mock()
    processor.logger.error = Mock()
    
    processor.transcribe_video = Mock(
        return_value=transcribe_result or "1\n00:00:00,000 --> 00:00:05,000\nTest\n\n"
    )
    processor.detect_source_language = Mock(return_value=detect_language_result)
    processor.parse_srt = Mock(return_value=[
        {'index': 0, 'start': '00:00:00,000', 'end': '00:00:05,000', 'text': 'Test'}
    ])
    
    # Add any custom kwargs as mock methods
    for name, return_value in kwargs.items():
        setattr(processor, name, Mock(return_value=return_value))
    
    return processor


def create_temp_video_file(directory: str, filename: str = "test.mp4") -> str:
    """Create a temporary video file for testing"""
    path = Path(directory) / filename
    path.touch()
    return str(path)


def create_temp_srt_file(directory: str, content: str = "", filename: str = "test.srt") -> str:
    """Create a temporary SRT file for testing"""
    if not content:
        content = "1\n00:00:00,000 --> 00:00:05,000\nTest subtitle\n\n"
    
    path = Path(directory) / filename
    path.write_text(content)
    return str(path)


def create_result_dict_with_entries(num_entries: int = 3) -> dict:
    """Create a mock result dictionary with sample entries"""
    entries = []
    for i in range(num_entries):
        entries.append({
            'index': i,
            'start': i * 5.0,
            'end': (i + 1) * 5.0,
            'text': f'Sample subtitle line {i + 1}',
        })
    
    return {
        'entries': entries,
        'base': '/tmp/test',
        'source_lang': 'en',
        'parsed_entries': entries,
    }


class ProcessorBuilder:
    """Builder pattern for creating mock processors with specific setup"""
    
    def __init__(self):
        self._processor = Mock()
        self._setup_logger()
    
    def _setup_logger(self):
        self._processor.logger = Mock()
        self._processor.logger.info = Mock()
        self._processor.logger.warning = Mock()
        self._processor.logger.error = Mock()
        return self
    
    def with_transcription(self, srt_content: str):
        """Add mock transcription"""
        self._processor.transcribe_video = Mock(return_value=srt_content)
        return self
    
    def with_language_detection(self, lang: str):
        """Add mock language detection"""
        self._processor.detect_source_language = Mock(return_value=lang)
        return self
    
    def with_srt_parsing(self, entries: list):
        """Add mock SRT parsing"""
        self._processor.parse_srt = Mock(return_value=entries)
        return self
    
    def with_translation(self, translations: list):
        """Add mock translation"""
        self._processor.translate_batch_single_attempt = Mock(return_value=translations)
        return self
    
    def build(self) -> Mock:
        """Build and return the configured processor mock"""
        return self._processor
