import time
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm


def translate_with_batch_fallback_chain(
    processor,
    texts: List[str],
    target_lang: str,
    source_lang: str = "en",
    original_entries: Optional[List[Dict]] = None,
    output_srt: Optional[str] = None,
    existing_translations: Optional[Dict[int, str]] = None,
) -> List[str]:
    """Translate texts using per-batch model fallback with cache and dedup."""
    if not texts or target_lang == source_lang:
        return texts

    model_chain = ["deepseek", "minimax", "gemini", "grok"]
    batch_sizes = {
        "deepseek": 25,
        "minimax": 20,
        "gemini": 40,
        "grok": 25,
    }

    final_result = [None] * len(texts)

    if existing_translations:
        for idx, txt in existing_translations.items():
            if 0 <= idx < len(final_result) and txt and txt.strip():
                final_result[idx] = txt

    local_hits = 0
    for i, text in enumerate(texts):
        if final_result[i] is None:
            cached = processor._lookup_local_cache(text, target_lang)
            if cached:
                final_result[i] = cached
                local_hits += 1
    if local_hits:
        processor._cost_savings["local_cache_hits"] += local_hits
        processor.logger.info(f"💾 Local cache: {local_hits} translations reused (100% cost saved)")

    indices_to_translate = [i for i in range(len(texts)) if final_result[i] is None]
    if not indices_to_translate:
        processor._save_local_translation_cache()
        result_texts = [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]
        if output_srt and original_entries:
            try:
                with open(output_srt, "w", encoding="utf-8-sig") as f:
                    for idx_srt, entry in enumerate(original_entries, 1):
                        t_text = result_texts[idx_srt - 1] if idx_srt - 1 < len(result_texts) else entry["text"]
                        f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                processor.logger.info(f"✓ Cache-only save completed: {Path(output_srt).name}")
            except Exception as e:
                processor.logger.warning(f"Failed to save cache-only SRT: {e}")
        return result_texts

    unique_text_map: Dict[str, List[int]] = {}
    for i in indices_to_translate:
        t = texts[i]
        unique_text_map.setdefault(t, []).append(i)

    unique_texts = list(unique_text_map.keys())
    dedup_count = len(indices_to_translate) - len(unique_texts)
    if dedup_count > 0:
        processor.logger.info(
            f"🔁 Deduplication: {len(unique_texts)} unique → saves {dedup_count} redundant API calls"
        )

    unique_indices = list(range(len(unique_texts)))
    batch_indices_list = processor._create_balanced_batches(unique_indices, unique_texts, max(batch_sizes.values()))
    batch_count = len(batch_indices_list)

    pbar = tqdm(total=len(unique_texts), unit="item", desc=f"  Translating ({target_lang.upper()}) [Fallback Chain]")

    for batch_num, batch_indices in enumerate(batch_indices_list):
        batch = [unique_texts[idx] for idx in batch_indices]
        success_batch = False

        for model_name in model_chain:
            if success_batch:
                break

            try:
                batch_size = batch_sizes[model_name]
                pbar.set_postfix_str(f"Batch {batch_num + 1}/{batch_count} via {model_name.upper()}")

                trans_list = processor.translate_batch_single_attempt(
                    batch,
                    target_lang,
                    source_lang,
                    model_name,
                    batch_size,
                    max_retries=2,
                )

                for rel_idx, trans in enumerate(trans_list):
                    unique_text = batch[rel_idx]
                    processor._store_local_cache(unique_text, target_lang, trans)
                    for abs_idx in unique_text_map.get(unique_text, []):
                        final_result[abs_idx] = trans

                if output_srt and original_entries:
                    try:
                        with open(output_srt, "w", encoding="utf-8-sig") as f:
                            for idx, entry in enumerate(original_entries, 1):
                                trans = final_result[idx - 1]
                                t_text = trans if trans is not None else entry["text"]
                                f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                    except Exception as e:
                        pbar.write(f"⚠️ Could not save intermediate SRT: {e}")

                pbar.update(len(batch))
                success_batch = True

                done_frac = (batch_num + 1) / max(1, batch_count)
                batch_pct = int(55 + done_frac * 22)
                processor.logger.info(f"PROGRESS:{batch_pct}:🌐 Translation ({batch_num+1}/{batch_count})")
                time.sleep(1)

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                is_api_key = (
                    "401" in error_msg
                    or "401 Unauthorized" in error_msg
                    or "Invalid API Key" in error_msg
                )

                if is_api_key:
                    pbar.write(f"⚠️ Batch {batch_num + 1}: {model_name.upper()} - API Key issue, skipping.")
                else:
                    pbar.write(f"⚠️ Batch {batch_num + 1}: {model_name.upper()} failed - {error_msg[:80]}")

        if not success_batch:
            processor.logger.error(f"❌ Batch {batch_num + 1} FAILED: All models exhausted. Using original text.")
            for unique_text in batch:
                for abs_idx in unique_text_map.get(unique_text, []):
                    if final_result[abs_idx] is None:
                        final_result[abs_idx] = unique_text
            pbar.update(len(batch))

    pbar.close()
    processor._save_local_translation_cache()
    processor._log_cost_savings()

    return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]