"""Tests for fallback chain provider order."""

import unittest
from unittest.mock import Mock

from subtitle.translation.fallback_chain import translate_with_batch_fallback_chain, FREE_PROVIDERS


class _StubProcessor:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []
        self.logger = Mock()
        self._cost_savings = {"local_cache_hits": 0}

    def _lookup_local_cache(self, text, target_lang):
        return None

    def _store_local_cache(self, text, target_lang, translation):
        pass

    def _save_local_translation_cache(self):
        pass

    def _log_cost_savings(self):
        pass

    def _create_balanced_batches(self, indices, texts, max_batch_size, max_chars=5000):
        return [indices]

    def translate_batch_single_attempt(
        self, batch, target_lang, source_lang, model_name, batch_size, max_retries=2
    ):
        self.calls.append(model_name)
        outcome = self.outcomes.get(model_name)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            raise RuntimeError(f"No outcome defined for {model_name}")
        # outcome should be a list of translated texts, one per input
        return outcome


class TestFallbackChainProviderOrder(unittest.TestCase):
    def test_gemini_tried_first_and_succeeds(self):
        processor = _StubProcessor(outcomes={"gemini": ["hi_translated"]})
        
        result = translate_with_batch_fallback_chain(
            processor,
            texts=["hi"],
            target_lang="fa",
            source_lang="en"
        )
        
        self.assertEqual(processor.calls, ["gemini"])
        self.assertEqual(result, ["hi_translated"])
        
        # Assert logger.info called with "translating via gemini"
        info_calls = [call.args[0] for call in processor.logger.info.call_args_list]
        self.assertTrue(any("translating via gemini" in str(msg).lower() for msg in info_calls))
        
        # Assert logger.warning NEVER called with "PAID"
        warning_calls = [call.args[0] for call in processor.logger.warning.call_args_list]
        self.assertFalse(any("paid" in str(msg).lower() for msg in warning_calls))

    def test_gemini_failure_falls_through_to_deepseek_with_warning(self):
        processor = _StubProcessor(
            outcomes={
                "gemini": RuntimeError("503 Service Unavailable"),
                "deepseek": ["hi_translated_deepseek"]
            }
        )
        
        result = translate_with_batch_fallback_chain(
            processor,
            texts=["hi"],
            target_lang="fa",
            source_lang="en"
        )
        
        self.assertEqual(processor.calls, ["gemini", "deepseek"])
        self.assertEqual(result, ["hi_translated_deepseek"])
        
        # Assert warning for fallthrough
        warning_calls = [str(call.args[0]).lower() for call in processor.logger.warning.call_args_list]
        has_warning = any("paid" in msg and "deepseek" in msg for msg in warning_calls)
        self.assertTrue(has_warning, "Missing warning about fallthrough to paid provider (deepseek)")
        
        # Assert info for deepseek
        info_calls = [str(call.args[0]).lower() for call in processor.logger.info.call_args_list]
        has_info = any("translating via deepseek" in msg for msg in info_calls)
        self.assertTrue(has_info, "Missing info log about translating via deepseek")

    def test_all_providers_fail_uses_original_text(self):
        processor = _StubProcessor(
            outcomes={
                "gemini": RuntimeError("fail"),
                "deepseek": RuntimeError("fail"),
                "minimax": RuntimeError("fail"),
                "grok": RuntimeError("fail")
            }
        )
        
        result = translate_with_batch_fallback_chain(
            processor,
            texts=["hi_original"],
            target_lang="fa",
            source_lang="en"
        )
        
        self.assertEqual(result, ["hi_original"])
        
        # Assert error log
        error_calls = [str(call.args[0]).lower() for call in processor.logger.error.call_args_list]
        has_error = any("failed: all models exhausted" in msg for msg in error_calls)
        self.assertTrue(has_error, "Missing error log about all models exhausted")

    def test_model_chain_free_first_order(self):
        self.assertEqual(FREE_PROVIDERS, frozenset({"gemini"}))
        
        processor = _StubProcessor(
            outcomes={
                "gemini": RuntimeError("fail"),
                "deepseek": ["hi_deepseek"]
            }
        )
        translate_with_batch_fallback_chain(
            processor,
            texts=["hi"],
            target_lang="fa",
            source_lang="en"
        )
        
        self.assertEqual(processor.calls[0], "gemini", "gemini should be attempted first")

if __name__ == "__main__":
    unittest.main()
