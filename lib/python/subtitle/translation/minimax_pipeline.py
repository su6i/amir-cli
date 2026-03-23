"""
MiniMax Translation Pipeline
=============================
Extraction of translate_with_minimax() method body.
Translate via MiniMax LLM (OpenAI-compatible API) with optimized retries.

Features:
  • OpenAI-compatible client for MiniMax endpoint
  • 6-attempt retry with exponential backoff
  • Per-batch response validation + live SRT checkpointing
  • Language-specific fixes (Persian chars, echo cleaning)
  • Error handling for API key and connection issues
"""

from typing import List, Dict, Optional
import time
from tqdm import tqdm

from . import write_partial_translation_srt


def run_minimax_translation_pipeline(
    processor,
    texts: List[str],
    target_lang: str,
    source_lang: str = 'en',
    batch_size: int = 15,
    original_entries: Optional[List[Dict]] = None,
    output_srt: Optional[str] = None,
    existing_translations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """
    Translate subtitle texts using MiniMax LLM (OpenAI-compatible API).
    
    MiniMax provides high-quality multilingual translation through an
    OpenAI-compatible endpoint (api.minimax.io/v1).
    
    Args:
        processor: SubtitleProcessor instance (for API keys, logging, etc.)
        texts: List of strings to translate
        target_lang: ISO 639-1 target language code
        source_lang: ISO 639-1 source language code (default: 'en')
        batch_size: Items per batch (default: 15)
        original_entries: List of SRT entry dicts with 'start', 'end', 'text' keys
        output_srt: Path to save live SRT checkpoint
        existing_translations: Dict mapping indices to pre-translated strings
    
    Returns:
        List[str]: Translated texts (same length as input)
    
    Raises:
        RuntimeError: If MINIMAX_API_KEY not set or translation fails
    """
    # ── API key validation ─────────────────────────────────────────────────
    if not processor.minimax_api_key:
        raise RuntimeError(
            "MINIMAX_API_KEY not set. Export it before running."
        )

    # ── Initialize OpenAI-compatible client ────────────────────────────────
    from openai import OpenAI as _OAI
    client = _OAI(
        api_key=processor.minimax_api_key,
        base_url="https://api.minimax.io/v1"
    )

    # ── Initialize translation tracking ───────────────────────────────────
    indices = list(range(len(texts)))
    final_result: List[Optional[str]] = [None] * len(texts)

    if existing_translations:
        for idx, trans in existing_translations.items():
            if 0 <= idx < len(texts):
                final_result[idx] = trans

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
        desc=f"  MiniMax-Translating ({target_lang.upper()})"
    )

    # ── Process each batch ───────────────────────────────────────────────
    for i, batch_indices in enumerate(batch_indices_list):
        batch = [texts[idx] for idx in batch_indices]
        # Skip context lines for MiniMax (performance optimization)
        batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
        pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})

        attempt = 0
        max_retries = 6
        success_batch = False
        last_error_msg = ""

        # ── Retry loop ───────────────────────────────────────────────────
        while attempt < max_retries:
            try:
                attempt += 1
                response = client.chat.completions.create(
                    model="MiniMax-M2.5",
                    messages=[
                        {
                            "role": "system",
                            "content": processor.get_translation_prompt(target_lang)
                        },
                        {"role": "user", "content": batch_text}
                    ],
                    temperature=1.0,  # MiniMax default & optimal for translation
                    max_tokens=1500
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
                    trans_list = [
                        processor.fix_persian_text(
                            processor.strip_english_echo(t)
                        )
                        if t and has_target_language_chars(t, target_lang)
                        else batch[j]
                        for j, t in enumerate(trans_list)
                    ]

                # Validate batch completeness
                if len(trans_list) >= len(batch):
                    for rel_idx, trans in enumerate(trans_list[:len(batch)]):
                        final_result[batch_indices[rel_idx]] = trans

                    # Live checkpoint saving
                    if output_srt and original_entries:
                        try:
                            write_partial_translation_srt(
                                output_srt, final_result, original_entries
                            )
                        except:
                            pass

                    pbar.update(len(batch))
                    success_batch = True
                    time.sleep(0.1)
                    break
                else:
                    delay = min(20 + attempt * 5, 120)
                    processor.logger.warning(
                        f"⚠️ MiniMax batch {i+1} incomplete: "
                        f"got {len(trans_list)}/{len(batch)}. "
                        f"Retry {attempt}/{max_retries} in {delay}s..."
                    )
                    time.sleep(delay)
                    if attempt >= max_retries:
                        last_error_msg = f"incomplete after {max_retries} attempts"
                        break

            except Exception as e:
                last_error_msg = f"{type(e).__name__}: {e}"
                if "401" in str(e) or "Invalid API Key" in str(e):
                    raise
                if attempt >= max_retries:
                    break
                time.sleep(min(60, (2 ** (attempt % 6)) * 5))

        # ── Error handling ─────────────────────────────────────────────────
        if not success_batch:
            processor.logger.error(
                f"❌ MiniMax batch {i+1} failed after {max_retries} attempts: "
                f"{last_error_msg}"
            )
            pbar.close()
            raise RuntimeError(
                f"MiniMax translation halted at batch {i+1}: {last_error_msg}"
            )

    pbar.close()
    return final_result


__all__ = ["run_minimax_translation_pipeline"]
