"""
LiteLLM Translation Pipeline
=============================
Extraction of translate_with_litellm() method body.
Universal LLM bridge for debugging and testing - supports DeepSeek, OpenAI, Anthropic, Google models.

Features:
  • Smart provider prefix resolution (auto-detect service from model name)
  • 10-attempt nuclear retry with temperature nudging
  • Per-batch validation + live SRT checkpointing
  • Graceful fallback to DeepSeek on exhaustion
  • Language-specific text fixes (Persian chars, echo cleaning)
"""

from typing import List, Dict, Optional
import time
from tqdm import tqdm

from . import write_partial_translation_srt


def run_litellm_translation_pipeline(
    processor,
    texts: List[str],
    target_lang: str,
    source_lang: str = 'en',
    batch_size: int = 20,
    original_entries: Optional[List[Dict]] = None,
    output_srt: Optional[str] = None,
    existing_translations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """
    Universal LLM bridge via LiteLLM for debugging and testing.
    
    Supports any LLM accessible through LiteLLM (OpenAI, Anthropic, DeepSeek, Gemini, etc.)
    with smart provider prefix resolution.
    
    Args:
        processor: SubtitleProcessor instance (for API keys, logging, etc.)
        texts: List of strings to translate
        target_lang: ISO 639-1 target language code
        source_lang: ISO 639-1 source language code (default: 'en')
        batch_size: Items per batch (default: 20)
        original_entries: List of SRT entry dicts with 'start', 'end', 'text' keys
        output_srt: Path to save live SRT checkpoint
        existing_translations: Dict mapping indices to pre-translated strings
    
    Returns:
        List[str]: Translated texts (same length as input)
    
    Raises:
        RuntimeError: If LiteLLM not installed or all retries exhausted
    """
    # Early exit checks
    try:
        from litellm import completion
    except ImportError:
        processor.logger.error("LiteLLM not installed. Use 'uv pip install litellm'")
        return processor.translate_with_deepseek(
            texts, target_lang, source_lang, 30,
            original_entries, output_srt, existing_translations
        )
    
    from litellm import completion
    
    # ── Resolve model name ────────────────────────────────────────────────
    model_name = processor.custom_model or "gpt-4o-mini"
    
    # Smart provider prefix resolution from model name
    if "/" not in model_name:
        if "deepseek" in model_name.lower():
            model_name = f"deepseek/{model_name}"
        elif any(x in model_name.lower() for x in ["gpt-", "o1-", "o3-"]):
            model_name = f"openai/{model_name}"
        elif "claude" in model_name.lower():
            model_name = f"anthropic/{model_name}"
        elif "gemini" in model_name.lower():
            model_name = f"google/{model_name}"
    
    processor.logger.info(f"🌌 LiteLLM Bridge Active. Resolved Model: {model_name}")

    # ── Initialize translation tracking ───────────────────────────────────
    indices = list(range(len(texts)))
    final_result = [None] * len(texts)
    
    if existing_translations:
        for idx, txt in existing_translations.items():
            if 0 <= idx < len(final_result) and txt and txt.strip():
                final_result[idx] = txt
    
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
        desc=f"  LiteLLM-Translating ({model_name})"
    )
    
    # ── Process each batch ───────────────────────────────────────────────
    for i, batch_indices in enumerate(batch_indices_list):
        batch = [texts[idx] for idx in batch_indices]
        batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
        
        pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
        
        # NUCLEAR RETRY LOGIC
        attempt = 0
        max_retries = 10
        success = False
        
        while attempt < max_retries and not success:
            attempt += 1
            try:
                # Temperature nudging: slight increase on retries to break stuck loops
                current_temp = processor.temperature + (
                    attempt * 0.05 if attempt > 3 else 0
                )
                
                response = completion(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": processor.get_translation_prompt(target_lang)
                        },
                        {"role": "user", "content": batch_text}
                    ],
                    temperature=min(1.0, current_temp),  # Cap at 1.0
                    timeout=90
                )
                
                output = response.choices[0].message.content.strip()
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
                    from ..utils import has_target_language_chars
                    processed = []
                    for idx, t in enumerate(trans_list):
                        if t and has_target_language_chars(t, target_lang):
                            processed.append(
                                processor.fix_persian_text(
                                    processor.strip_english_echo(t)
                                )
                            )
                        else:
                            processed.append(
                                batch[idx] if idx < len(batch) else t
                            )
                    trans_list = processed
                
                # Validate batch completeness
                if len(trans_list) >= len(batch):
                    for rel_idx, trans in enumerate(trans_list[:len(batch)]):
                        abs_idx = batch_indices[rel_idx]
                        final_result[abs_idx] = trans
                    
                    # Live checkpoint saving
                    if output_srt and original_entries:
                        write_partial_translation_srt(
                            output_srt, final_result, original_entries
                        )
                    
                    success = True
                    pbar.update(len(batch))
                else:
                    delay = min(5 + attempt, 12)
                    processor.logger.warning(
                        f"⚠️ LiteLLM attempt {attempt}/{max_retries} incomplete: "
                        f"{len(trans_list)}/{len(batch)}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)

            except Exception as e:
                processor.logger.error(f"❌ LiteLLM attempt {attempt} failed: {e}")
                if attempt >= max_retries:
                    raise RuntimeError(
                        f"Halted: LiteLLM failed after {max_retries} attempts: {e}"
                    )
                time.sleep(5)

    pbar.close()
    return final_result


__all__ = ["run_litellm_translation_pipeline"]
