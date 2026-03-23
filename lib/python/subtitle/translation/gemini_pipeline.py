"""
Gemini Translation Pipeline
============================
Complete extraction of the translate_with_gemini() method body.
Implements batched translation with dynamic Google Gemini model fallback.

Features:
  • Model discovery & ranking (top 6 models)
  • Per-batch context awareness (3 lines before/after)
  • 2-attempt retry per model with backoff
  • Emergency DeepSeek fallback on complete failure
  • Live SRT checkpoint saving during processing
  • Language-specific text fixes (Persian chars, English echo stripping)
"""

from typing import List, Dict, Optional
import time
from tqdm import tqdm

from . import (
    build_contextual_batch_text, 
    write_partial_translation_srt,
    filter_gemini_generation_models,
    rank_gemini_model_name
)


def run_gemini_translation_pipeline(
    processor,
    texts: List[str],
    target_lang: str,
    source_lang: str = 'en',
    batch_size: int = 40,
    original_entries: Optional[List[Dict]] = None,
    output_srt: Optional[str] = None,
    existing_translations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """
    Gemini-first batched translation pipeline with dynamic model fallback.
    
    Discovers available Gemini models, ranks them, and attempts translation
    with top 6 models. Per-batch context awareness + emergency DeepSeek fallback.
    
    Args:
        processor: SubtitleProcessor instance (for API keys, logging, etc.)
        texts: List of strings to translate
        target_lang: ISO 639-1 target language code ('fa', 'en', etc.)
        source_lang: ISO 639-1 source language code (default: 'en')
        batch_size: Items per batch (default: 40)
        original_entries: List of SRT entry dicts with 'start', 'end', 'text' keys
        output_srt: Path to save live SRT checkpoint
        existing_translations: Dict mapping indices to pre-translated strings
    
    Returns:
        List[str]: Translated texts (same length as input), with None values 
                  replaced by originals where translation failed
    
    Raises:
        RuntimeError: If both Gemini and DeepSeek emergency fallback fail
    """
    # Early exit checks
    try:
        from google import genai
        HAS_GEMINI = True
    except ImportError:
        HAS_GEMINI = False
    
    if not HAS_GEMINI:
        processor.logger.warning("google-genai SDK not installed. Falling back to DeepSeek.")
        return processor.translate_with_deepseek(
            texts, target_lang, source_lang, 30, 
            original_entries, output_srt, existing_translations
        )
    
    if not processor.google_api_key:
        processor.logger.error("GOOGLE_API_KEY not found. Cannot use Gemini.")
        return processor.translate_with_deepseek(
            texts, target_lang, source_lang, 30,
            original_entries, output_srt, existing_translations
        )

    # ── Initialize Gemini Client ──────────────────────────────────────────
    from google import genai
    client = genai.Client(api_key=processor.google_api_key)
    
    # ── Discover and rank available models ─────────────────────────────────
    available_models = _get_available_gemini_models_internal(
        client, processor
    )
    processor.logger.info(
        f"📡 Discovered {len(available_models)} Gemini models. "
        f"Top pick: {available_models[0] if available_models else 'NONE'}"
    )

    # ── Initialize translation tracking ───────────────────────────────────
    indices = list(range(len(texts)))
    final_result = [None] * len(texts)
    
    # Prefill with any existing recovered translations
    if existing_translations:
        for idx, txt in existing_translations.items():
            if 0 <= idx < len(final_result) and txt and txt.strip():
                final_result[idx] = txt
    
    # Early exit if nothing to translate
    indices_to_translate = [i for i in indices if final_result[i] is None]
    if not indices_to_translate:
        return [
            final_result[i] if final_result[i] is not None else texts[i]
            for i in range(len(texts))
        ]

    # ── Create batches ───────────────────────────────────────────────────
    batch_indices_list = processor._create_balanced_batches(
        indices_to_translate, texts, batch_size
    )
    batch_count = len(batch_indices_list)
    pbar = tqdm(
        total=len(indices_to_translate),
        unit="item",
        desc=f"  Gemini-Translating ({target_lang.upper()})"
    )

    # ── Process each batch ───────────────────────────────────────────────
    for i, batch_indices in enumerate(batch_indices_list):
        batch = [texts[idx] for idx in batch_indices]

        # ── Build context-aware prompt ────────────────────────────────────
        first_abs = batch_indices[0]
        last_abs = batch_indices[-1]
        ctx_before = texts[max(0, first_abs - 3) : first_abs]
        ctx_after = texts[last_abs + 1 : last_abs + 4]
        
        ctx_section = ""
        if ctx_before or ctx_after:
            parts = []
            if ctx_before:
                parts.append(
                    "Previous lines (context only, do NOT translate):\n" +
                    "\n".join(f"  • {t}" for t in ctx_before)
                )
            if ctx_after:
                parts.append(
                    "Following lines (context only, do NOT translate):\n" +
                    "\n".join(f"  • {t}" for t in ctx_after)
                )
            ctx_section = "\n".join(parts) + "\n\nLines to translate:\n"

        batch_text = ctx_section + "\n".join(
            [f"{idx+1}. {t}" for idx, t in enumerate(batch)]
        )
        
        pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
        
        success = False
        
        # ── Try top 6 models ──────────────────────────────────────────────
        for model_name in available_models[:6]:
            if success:
                break
            
            for attempt in range(2):
                try:
                    prompt = (
                        f"{processor.get_translation_prompt(target_lang)}\n\n"
                        f"Text to translate (numbered list):\n{batch_text}"
                    )
                    
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    output = response.text.strip()
                    trans_list = processor._parse_translated_batch_output(
                        output, len(batch)
                    )
                    
                    # Replace None with original text
                    if None in trans_list:
                        trans_list = [
                            trans_list[j] if trans_list[j] is not None else batch[j]
                            for j in range(len(trans_list))
                        ]
                    
                    # Language-specific fixes
                    if target_lang == 'fa':
                        processed = []
                        for idx, t in enumerate(trans_list):
                            from ..utils import has_target_language_chars
                            if t and has_target_language_chars(t, target_lang):
                                processed.append(
                                    processor.fix_persian_text(
                                        processor.strip_english_echo(t)
                                    )
                                )
                            else:
                                # Keep original English if no Persian detected
                                processed.append(
                                    batch[idx] if idx < len(batch) else t
                                )
                        trans_list = processed
                    
                    # Validate batch completeness
                    if len(trans_list) >= len(batch):
                        result_batch = trans_list[:len(batch)]
                        for rel_idx, trans in enumerate(result_batch):
                            abs_idx = batch_indices[rel_idx]
                            final_result[abs_idx] = trans
                        
                        # Live checkpoint saving
                        if output_srt and original_entries:
                            write_partial_translation_srt(
                                output_srt, final_result, original_entries
                            )
                        
                        success = True
                        pbar.update(len(batch))
                        break
                    else:
                        delay = min(4 + attempt, 10)
                        processor.logger.warning(
                            f"⚠️ {model_name} batch incomplete: "
                            f"got {len(trans_list)}/{len(batch)}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)

                except Exception as e:
                    if "404" not in str(e) and "403" not in str(e):
                        processor.logger.warning(
                            f"🛡️ {model_name} attempt {attempt} failed: {e}"
                        )
                    time.sleep(1)
            
            if not success:
                processor.logger.debug(
                    f"🔄 Model {model_name} exhausted. Falling back downstream..."
                )

        # ── Emergency fallback: DeepSeek ──────────────────────────────────
        if not success:
            try:
                processor.logger.info(
                    "🆘 EMERGENCY FALLBACK: Gemini failed. "
                    "Switching to DeepSeek for this batch..."
                )
                ds_result = processor.translate_with_deepseek(
                    batch, target_lang, source_lang, 30
                )
                for idx_in_batch, txt in zip(batch_indices, ds_result):
                    final_result[idx_in_batch] = txt
            except Exception as e:
                processor.logger.error(
                    f"❌ CRITICAL FAILURE: Both Gemini and DeepSeek failed "
                    f"for batch {i // batch_size + 1}"
                )
                raise RuntimeError(
                    f"Translation halted to prevent data loss: {e}"
                )
            
            pbar.update(len(batch))

    pbar.close()
    return final_result


def _get_available_gemini_models_internal(client, processor) -> List[str]:
    """
    Internal helper: Discover and rank available Gemini models.
    Filters to generation models, ranks by translation suitability.
    """
    try:
        models_response = client.models.list()
        all_models = [m.name for m in models_response]
        
        # Filter to generation models
        generation_models = filter_gemini_generation_models(all_models)
        
        # Rank by translation suitability
        ranked = sorted(
            generation_models,
            key=rank_gemini_model_name,
            reverse=True
        )
        
        return ranked if ranked else ["gemini-1.5-pro"]
    except Exception as e:
        processor.logger.warning(f"⚠️ Failed to discover models: {e}")
        return ["gemini-1.5-pro"]


__all__ = ["run_gemini_translation_pipeline"]
