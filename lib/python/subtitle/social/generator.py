import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from subtitle.config import get_language_config


def generate_posts(
    processor,
    original_base: str,
    source_lang: str,
    result: Dict[str, Any],
    platforms: Optional[List[str]] = None,
    prompt_file: Optional[str] = None,
    post_langs: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Generate social media posts for requested subtitle languages and platforms."""
    if platforms is None:
        platforms = ["telegram"]

    wanted_langs: List[str] = post_langs if post_langs else ["fa"]

    stem = Path(original_base).name
    stem = re.sub(r"_(subbed|[a-z]{2,3})$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_\d{2}\.\d{2}\.\d{4}$", "", stem)
    title = re.sub(r"[_\-]+", " ", stem).strip()

    bidi = "\u200f\u200e\u200d\u202b\u202a\u202c\u202e\u202d\u2067\u2066\u2069"

    srt_langs = [
        lang
        for lang, path in result.items()
        if isinstance(path, str)
        and path.endswith(".srt")
        and os.path.exists(path)
        and lang in wanted_langs
    ]

    if not srt_langs:
        for lang in wanted_langs:
            cand = f"{original_base}_{lang}.srt"
            if os.path.exists(cand) and lang not in srt_langs:
                srt_langs.append(lang)

    if not srt_langs:
        processor.logger.warning("⚠️ No SRT files found — skipping post generation.")
        return {}

    saved: Dict[str, str] = {}

    for srt_lang in srt_langs:
        try:
            srt_path = result.get(srt_lang) or f"{original_base}_{srt_lang}.srt"
            if not os.path.exists(srt_path):
                continue

            entries = processor.parse_srt(srt_path)
            video_metadata = processor._discover_video_metadata(original_base, srt_path)

            meta_dur = video_metadata.get("duration_sec", 0.0)
            if meta_dur > 0:
                duration = processor._format_total_seconds(meta_dur, lang=srt_lang)
            else:
                duration = processor._srt_duration_str(entries, lang=srt_lang)

            lines = []
            for e in entries:
                t = e["text"]
                for c in bidi:
                    t = t.replace(c, "")
                lines.append(t.strip())
            full_text = "\n".join(lines[:80]) + ("\n..." if len(lines) > 80 else "")
            full_text = full_text.encode("utf-8", errors="replace").decode("utf-8")
            title_clean = title.encode("utf-8", errors="replace").decode("utf-8")

            srt_lang_name = get_language_config(srt_lang).name

            for platform in platforms:
                try:
                    system, user = processor._get_post_prompt(
                        platform,
                        title_clean,
                        srt_lang_name,
                        full_text,
                        prompt_file=prompt_file,
                        srt_lang=srt_lang,
                        duration=duration,
                        all_srt_langs=srt_langs,
                        source_lang=source_lang,
                        metadata=video_metadata,
                    )
                except ValueError as ve:
                    processor.logger.warning(str(ve))
                    continue
                except Exception as pe:
                    processor.logger.warning(f"⚠️ Prompt build failed for {platform}/{srt_lang}: {pe}")
                    continue

                try:
                    post_text = processor._call_llm_for_post(system, user)
                except Exception as le:
                    processor.logger.warning(f"⚠️ LLM call failed for {platform}/{srt_lang}: {le}")
                    continue

                if not post_text:
                    processor.logger.warning(f"⚠️ Empty response for {platform}/{srt_lang} — skipping")
                    continue

                try:
                    post_text = processor._sanitize_post(post_text, platform)

                    if platform == "telegram":
                        ok, missing = processor._telegram_sections_complete(post_text)
                        if not ok:
                            processor.logger.warning(
                                f"⚠️ Post incomplete (missing: {', '.join(missing)}) — retrying…"
                            )
                            tail_markers = {"\u2728", "\U0001f4cc", "\u23f1", "hashtags (#)"}
                            is_tail_only = all(any(m in label for m in tail_markers) for label in missing)

                            if is_tail_only:
                                retry_user = (
                                    "The post below was truncated — it is missing its final sections.\n"
                                    "Continue it from where it stopped; output ONLY the continuation "
                                    "(do not repeat what is already written).\n\n"
                                    "Missing sections to add in order:\n"
                                    + ("\n".join(f"  • {lbl}" for lbl in missing))
                                    + "\n\nThe full required tail is:\n"
                                    "✨ [one sentence — main subject of this video]\n\n"
                                    "📌 [one sentence — for which audience this is relevant]\n\n"
                                    f"⏱️ Duration: {duration}\n\n"
                                    "#[tag1] #[tag2] #[tag3] #[tag4] #[tag5]\n\n"
                                    f"TRUNCATED POST:\n{post_text}"
                                )
                            else:
                                retry_user = (
                                    f"The post you wrote is INCOMPLETE. Missing: {', '.join(missing)}\n\n"
                                    "Rewrite the COMPLETE post from scratch following the original instructions.\n\n"
                                    f"ORIGINAL REQUEST:\n{user}"
                                )

                            try:
                                retry = processor._call_llm_for_post(system, retry_user)
                                if retry:
                                    retry_sanitized = processor._sanitize_post(retry, platform)
                                    if is_tail_only:
                                        merged = post_text.rstrip() + "\n\n" + retry_sanitized.strip()
                                        ok2, still = processor._telegram_sections_complete(merged)
                                        if ok2 or len(still) < len(missing):
                                            post_text = merged
                                    else:
                                        ok2, still = processor._telegram_sections_complete(retry_sanitized)
                                        if ok2 or len(still) < len(missing):
                                            post_text = retry_sanitized
                                    if not processor._telegram_sections_complete(post_text)[0]:
                                        _, still = processor._telegram_sections_complete(post_text)
                                        processor.logger.warning(
                                            f"⚠️ Retry still incomplete (missing: {', '.join(still)})"
                                        )
                            except Exception as re_err:
                                processor.logger.warning(f"⚠️ Retry failed: {re_err}")

                    post_path = f"{original_base}_{srt_lang}_{platform}.txt"
                    post_header = processor._compose_post_file_header(platform, video_metadata, title_clean)
                    with open(post_path, "w", encoding="utf-8") as f:
                        f.write(post_header + post_text)
                    saved[f"{srt_lang}_{platform}"] = post_path
                    label = f"پست {platform} ({srt_lang.upper()})"
                    processor.logger.info(f"📝 {label} saved: {Path(post_path).name}")
                    preview_text = post_header + post_text if post_header else post_text
                    print(f"\n{'━'*60}\n📝  {label}:\n{'━'*60}\n{preview_text}\n{'━'*60}\n")
                except Exception as write_err:
                    processor.logger.warning(f"⚠️ Could not save post for {platform}/{srt_lang}: {write_err}")

        except Exception as lang_err:
            processor.logger.warning(f"⚠️ Skipping lang={srt_lang} due to unexpected error: {lang_err}")
            continue

    return saved