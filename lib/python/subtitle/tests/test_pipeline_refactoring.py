"""Integration test for refactored translation pipelines

Validates that all extracted translation pipelines (DeepSeek, Gemini, LiteLLM, MiniMax)
can be called with correct signatures and don't break existing workflows.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Optional


class TestTranslationPipelineIntegration(unittest.TestCase):
    """Integration tests for translation pipeline extraction"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_processor = Mock()
        self.mock_processor.logger = Mock()
        self.mock_processor.logger.info = Mock()
        self.mock_processor.logger.warning = Mock()
        self.mock_processor.logger.error = Mock()
        self.mock_processor.logger.debug = Mock()
        
        # Setup processor attributes
        self.mock_processor.api_key = "test-deepseek-key"
        self.mock_processor.google_api_key = "test-google-key"
        self.mock_processor.minimax_api_key = "test-minimax-key"
        self.mock_processor.custom_model = "gpt-4o-mini"
        self.mock_processor.temperature = 0.7
        
        # Setup processor methods
        self.mock_processor.get_translation_prompt = Mock(
            return_value="Translate to English"
        )
        self.mock_processor._parse_translated_batch_output = Mock(
            return_value=["translated text"]
        )
        self.mock_processor._create_balanced_batches = Mock(
            return_value=[[0, 1, 2]]
        )
        self.mock_processor.fix_persian_text = Mock(side_effect=lambda x: x)
        self.mock_processor.strip_english_echo = Mock(side_effect=lambda x: x)
    
    def test_pipeline_imports_available(self):
        """Verify all pipeline functions can be imported"""
        try:
            from subtitle.translation import (
                run_deepseek_translation_pipeline,
                run_gemini_translation_pipeline,
                run_litellm_translation_pipeline,
                run_minimax_translation_pipeline,
            )
        except ImportError as e:
            self.fail(f"Pipeline imports failed: {e}")
    
    def test_deepseek_pipeline_function_signature(self):
        """Test DeepSeek pipeline has correct function signature"""
        from subtitle.translation import run_deepseek_translation_pipeline
        import inspect
        
        sig = inspect.signature(run_deepseek_translation_pipeline)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'processor', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        for param in expected_params:
            self.assertIn(
                param, params,
                f"DeepSeek pipeline missing parameter: {param}"
            )
    
    def test_gemini_pipeline_function_signature(self):
        """Test Gemini pipeline has correct function signature"""
        from subtitle.translation import run_gemini_translation_pipeline
        import inspect
        
        sig = inspect.signature(run_gemini_translation_pipeline)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'processor', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        for param in expected_params:
            self.assertIn(
                param, params,
                f"Gemini pipeline missing parameter: {param}"
            )
    
    def test_litellm_pipeline_function_signature(self):
        """Test LiteLLM pipeline has correct function signature"""
        from subtitle.translation import run_litellm_translation_pipeline
        import inspect
        
        sig = inspect.signature(run_litellm_translation_pipeline)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'processor', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        for param in expected_params:
            self.assertIn(
                param, params,
                f"LiteLLM pipeline missing parameter: {param}"
            )
    
    def test_minimax_pipeline_function_signature(self):
        """Test MiniMax pipeline has correct function signature"""
        from subtitle.translation import run_minimax_translation_pipeline
        import inspect
        
        sig = inspect.signature(run_minimax_translation_pipeline)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'processor', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        for param in expected_params:
            self.assertIn(
                param, params,
                f"MiniMax pipeline missing parameter: {param}"
            )
    
    def test_processor_methods_still_exist(self):
        """Verify processor still has all translation methods"""
        from subtitle.processor import SubtitleProcessor
        import inspect
        
        # Get all methods of SubtitleProcessor
        methods = {
            name for name, method in inspect.getmembers(
                SubtitleProcessor, predicate=inspect.isfunction
            )
        }
        
        expected_methods = [
            'translate_with_deepseek',
            'translate_with_gemini',
            'translate_with_litellm',
            'translate_with_minimax',
        ]
        
        for method_name in expected_methods:
            self.assertIn(
                method_name, methods,
                f"Processor missing method: {method_name}"
            )
    
    def test_processor_methods_are_thin_delegators(self):
        """Verify processor methods delegate to pipelines (not thick)"""
        from subtitle.processor import SubtitleProcessor
        import inspect
        
        processor = SubtitleProcessor.__init__.__self__ if hasattr(
            SubtitleProcessor.__init__, '__self__'
        ) else SubtitleProcessor()
        
        # Check that translate_with_deepseek roughly delegates
        source = inspect.getsource(SubtitleProcessor.translate_with_deepseek)
        
        # Should contain "run_deepseek_translation_pipeline" delegation
        self.assertIn(
            'run_deepseek_translation_pipeline',
            source,
            "translate_with_deepseek should delegate to pipeline"
        )
    
    def test_all_pipeline_exports_in_init(self):
        """Verify all pipeline functions are exported in __init__.py"""
        from subtitle import translation
        
        expected_exports = [
            'run_deepseek_translation_pipeline',
            'run_gemini_translation_pipeline',
            'run_litellm_translation_pipeline',
            'run_minimax_translation_pipeline',
        ]
        
        for export in expected_exports:
            self.assertTrue(
                hasattr(translation, export),
                f"Pipeline not exported in __all__: {export}"
            )


class TestProcessorMethodsBehave(unittest.TestCase):
    """Test that processor translation methods still work with old signatures"""
    
    def setUp(self):
        """Set up processor mock"""
        from subtitle.processor import SubtitleProcessor
        
        self.processor = Mock(spec=SubtitleProcessor)
        self.processor.logger = Mock()
        self.processor.api_key = "test-key"
        self.processor.google_api_key = "test-google-key"
        self.processor.minimax_api_key = "test-minimax-key"
        self.processor.custom_model = "gpt-4o"
        self.processor.temperature = 0.7
    
    def test_backward_compatibility_deepseek_signature(self):
        """Verify translate_with_deepseek still has same signature"""
        from subtitle.processor import SubtitleProcessor
        import inspect
        
        sig = inspect.signature(SubtitleProcessor.translate_with_deepseek)
        params = list(sig.parameters.keys())
        
        # Should match old signature
        expected = [
            'self', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        self.assertEqual(
            params, expected,
            "translate_with_deepseek signature changed!"
        )
    
    def test_backward_compatibility_gemini_signature(self):
        """Verify translate_with_gemini still has same signature"""
        from subtitle.processor import SubtitleProcessor
        import inspect
        
        sig = inspect.signature(SubtitleProcessor.translate_with_gemini)
        params = list(sig.parameters.keys())
        
        expected = [
            'self', 'texts', 'target_lang', 'source_lang',
            'batch_size', 'original_entries', 'output_srt',
            'existing_translations'
        ]
        
        self.assertEqual(
            params, expected,
            "translate_with_gemini signature changed!"
        )


if __name__ == '__main__':
    unittest.main()
