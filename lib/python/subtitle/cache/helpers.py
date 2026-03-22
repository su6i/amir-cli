import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional


def create_balanced_batches(
    indices: List[int],
    texts: List[str],
    max_batch_size: int,
    max_chars: int = 5000,
    logger=None,
) -> List[List[int]]:
    """Split indices into balanced batches by count and char budget."""
    batches: List[List[int]] = []
    current_batch: List[int] = []
    current_chars = 0

    for idx in indices:
        text_len = len(texts[idx])
        if len(current_batch) >= max_batch_size or (
            current_batch and current_chars + text_len > max_chars
        ):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(idx)
        current_chars += text_len

    if current_batch:
        batches.append(current_batch)

    if logger is not None:
        logger.debug(
            f"⚖️ Batch Balancer: Created {len(batches)} optimal batches for {len(indices)} entries."
        )

    return batches


def local_cache_key(text: str, target_lang: str) -> str:
    """Stable hash key for local translation cache."""
    return hashlib.md5(f"{text}|||{target_lang}".encode("utf-8")).hexdigest()


def load_local_translation_cache(cache_path: Path, logger=None) -> Dict[str, str]:
    """Load persisted local translation cache from disk."""
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if logger is not None:
                    logger.debug(f"💾 Local translation cache loaded: {len(data)} entries")
                return data
    except Exception as e:
        if logger is not None:
            logger.warning(f"Could not load local translation cache: {e}")
    return {}


def save_local_translation_cache(cache_path: Path, cache_data: Dict[str, str], logger=None) -> bool:
    """Persist local translation cache to disk. Returns True on success."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=None)
        return True
    except Exception as e:
        if logger is not None:
            logger.warning(f"Could not save local translation cache: {e}")
        return False


def lookup_local_cache(cache_data: Dict[str, str], text: str, target_lang: str) -> Optional[str]:
    """Return cached translation or None."""
    return cache_data.get(local_cache_key(text, target_lang))


def store_local_cache(cache_data: Dict[str, str], text: str, target_lang: str, translation: str) -> bool:
    """Store a single translation in local cache. Returns True if changed."""
    if translation and translation.strip():
        cache_data[local_cache_key(text, target_lang)] = translation
        return True
    return False


def log_cost_savings(cost_savings: Dict[str, int], logger) -> None:
    """Print accumulated cost savings summary."""
    total_local = cost_savings.get("local_cache_hits", 0)
    ds_cached = cost_savings.get("deepseek_cache_hit_tokens", 0)
    grok_cached = cost_savings.get("grok_cache_hit_tokens", 0)
    gem_cached = cost_savings.get("gemini_cached_tokens", 0)

    if total_local + ds_cached + grok_cached + gem_cached == 0:
        return

    logger.info("──────────────────────────────────────────")
    logger.info("💰 Cost Savings Report:")
    if total_local:
        logger.info(f"   • Local cache hits: {total_local} lines (100% saved)")
    if ds_cached:
        logger.info(f"   • DeepSeek cached tokens: {ds_cached:,} (90% cheaper)")
    if grok_cached:
        logger.info(f"   • Grok cached tokens: {grok_cached:,} (discounted)")
    if gem_cached:
        logger.info(f"   • Gemini cached tokens: {gem_cached:,} (guaranteed discount)")
    logger.info("──────────────────────────────────────────")
