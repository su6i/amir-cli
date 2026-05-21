import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _download_yt_source_srt(processor, video_path: str, source_lang: str, dest_srt: str) -> bool:
    """Attempt to download YouTube subtitles for source_lang via yt-dlp.

    Strategy:
    1. Manual (human-curated) subtitles for source_lang
    2. Auto-generated subtitles for source_lang as fallback

    Returns True if dest_srt was written, False otherwise.
    """
    try:
        import shutil as _shutil
        yt_dlp_bin = _shutil.which("yt-dlp")
        if not yt_dlp_bin:
            processor.logger.warning("⚠️  yt-dlp not found in PATH; cannot fetch YouTube subtitles.")
            return False

        # Derive the video URL from the video file's .info.json sidecar if available.
        # The info.json is written by yt-dlp alongside the video file.
        video_path_obj = Path(video_path)
        info_json = video_path_obj.with_suffix("").with_suffix(".mp4.info.json")
        if not info_json.exists():
            # Try common suffixed variants (e.g. _480p.mp4.info.json)
            for candidate in video_path_obj.parent.glob(f"{video_path_obj.stem}*.info.json"):
                info_json = candidate
                break

        url = None
        if info_json.exists():
            try:
                import json
                with open(info_json, "r", encoding="utf-8") as _f:
                    _meta = json.load(_f)
                url = _meta.get("webpage_url") or _meta.get("original_url")
            except Exception:
                pass

        if not url:
            processor.logger.warning(
                "⚠️  Cannot determine YouTube URL from info.json sidecar; skipping yt-dlp subtitle fetch."
            )
            return False

        base_no_ext = str(video_path_obj.with_suffix("").with_suffix(""))
        # Derive the same canonical base used by the rest of the pipeline
        # (strip resolution/quality suffixes like _480p, _720p from the basename)
        import re as _re
        base_no_ext = _re.sub(r'_\d{3,4}p$', '', base_no_ext)

        langs_to_try = [source_lang, f"{source_lang}-orig"]
        langs_csv = ",".join(langs_to_try)

        with tempfile.TemporaryDirectory() as _tmpdir:
            tmp_base = os.path.join(_tmpdir, "sub")

            # Pass 1: manual (human-curated) subtitles
            processor.logger.info(f"📥 Trying YouTube manual subtitles for: {source_lang}")
            _run_yt_dlp_sub_fetch(yt_dlp_bin, url, tmp_base, langs_csv, auto=False)

            found = _find_best_srt(_tmpdir, source_lang)
            if not found:
                # Pass 2: auto-generated subtitles
                processor.logger.info(f"📥 Manual missing; trying auto subtitles for: {source_lang}")
                _run_yt_dlp_sub_fetch(yt_dlp_bin, url, tmp_base, langs_csv, auto=True)
                found = _find_best_srt(_tmpdir, source_lang)

            if found:
                shutil.copy2(found, dest_srt)
                processor.logger.info(
                    f"✅ YouTube subtitle fetched → {Path(dest_srt).name}"
                )
                return True

        processor.logger.warning(f"❌ No YouTube subtitles found for lang: {source_lang}")
        return False

    except Exception as e:
        processor.logger.warning(f"⚠️  yt-dlp subtitle fetch failed: {e}")
        return False


def _run_yt_dlp_sub_fetch(yt_dlp_bin: str, url: str, base_out: str, langs_csv: str, auto: bool) -> None:
    """Run yt-dlp to download subtitles into base_out directory."""
    cmd = [
        yt_dlp_bin,
        "--quiet",
        "--skip-download",
        "--convert-subs", "srt",
        "--sleep-subtitles", "1",
        "-o", f"{base_out}.%(ext)s",
    ]
    if auto:
        cmd += ["--write-auto-subs", "--no-write-subs"]
    else:
        cmd += ["--write-subs", "--no-write-auto-subs"]
    cmd += ["--sub-langs", langs_csv, url]
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=60)
    except Exception:
        pass


def _find_best_srt(directory: str, lang: str) -> str:
    """Return the best matching SRT file for lang in directory, or empty string.

    Also searches for the canonical ISO form of legacy YT codes (e.g. iw → he),
    because yt-dlp normalises language codes in output filenames.
    """
    from subtitle.quality import normalize_yt_lang
    search_codes = [lang]
    normalized = normalize_yt_lang(lang)
    if normalized != lang:
        search_codes.append(normalized)

    for code in search_codes:
        for pattern in [f"*.{code}.srt", f"*.{code}-orig.srt", f"*.{code}*.srt"]:
            for path in Path(directory).glob(pattern):
                if path.stat().st_size > 50:
                    return str(path)
    return ""


def _find_info_json(video_path: str) -> Optional[str]:
    """Return path to yt-dlp info.json sidecar if it exists, else None."""
    p = Path(video_path)
    # e.g. video_480p.mp4 → video_480p.mp4.info.json
    direct = p.parent / (p.name + ".info.json")
    if direct.exists():
        return str(direct)
    # Fallback: glob for any *.info.json in same directory
    for candidate in p.parent.glob("*.info.json"):
        return str(candidate)
    return None


def _get_url_from_info_json(info_json_path: str) -> Optional[str]:
    try:
        with open(info_json_path, encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("webpage_url") or meta.get("original_url")
    except Exception:
        return None


def _available_yt_tracks(info_json_path: str) -> Dict[str, List[str]]:
    """Return {lang_code: [ext, ...]} for all available subtitle tracks."""
    try:
        with open(info_json_path, encoding="utf-8") as f:
            meta = json.load(f)
        result: Dict[str, List[str]] = {}
        for section in ("subtitles", "automatic_captions"):
            for lang, fmts in meta.get(section, {}).items():
                exts = [f.get("ext", "") for f in fmts if isinstance(f, dict)]
                result.setdefault(lang, []).extend(exts)
        return result
    except Exception:
        return {}


def _download_one_yt_track(
    yt_dlp_bin: str,
    url: str,
    lang_code: str,
    output_dir: str,
    prefer_manual: bool = True,
) -> Optional[str]:
    """Download a single YouTube subtitle track and return local SRT path."""
    base = os.path.join(output_dir, "sub")
    for auto in ([False, True] if prefer_manual else [True]):
        cmd = [
            yt_dlp_bin, "--quiet", "--skip-download",
            "--convert-subs", "srt", "--sleep-subtitles", "1",
            "-o", f"{base}.%(ext)s",
        ]
        if auto:
            cmd += ["--write-auto-subs", "--no-write-subs"]
        else:
            cmd += ["--write-subs", "--no-write-auto-subs"]
        cmd += ["--sub-langs", lang_code, url]
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=60)
        except Exception:
            pass
        found = _find_best_srt(output_dir, lang_code)
        if found:
            return found
    return None


def _auto_yt_check(
    processor,
    video_path: str,
    source_lang: str,
    src_srt: str,
    quality_threshold: float,
    emit_progress,
) -> bool:
    """Try YouTube subtitles before Whisper; write src_srt if usable.

    Strategy:
    1. Locate info.json and extract URL + available tracks.
    2. Download source_lang track + English track (if source is not English).
    3. Quality-check each track.
    4. Single-language path: one track covers >=72% with score>=threshold → use directly.
    5. Multilingual path: two complementary tracks together cover >=75% → build language
       timeline, then call processor.transcribe_by_language_timeline().
    6. Returns True if src_srt has been written (no Whisper needed).
    """
    import shutil as _sh
    from subtitle.quality import (
        QualityResult,
        assess_subtitle_quality,
        build_language_timeline,
        normalize_yt_lang,
        timeline_is_multilingual,
        yt_codes_for_lang,
    )

    # Locate yt-dlp
    yt_dlp_bin = _sh.which("yt-dlp")
    if not yt_dlp_bin:
        return False

    # Locate info.json
    info_json = _find_info_json(video_path)
    if not info_json:
        return False

    url = _get_url_from_info_json(info_json)
    if not url:
        return False

    available = _available_yt_tracks(info_json)
    if not available:
        return False

    video_duration = 0.0
    try:
        video_duration = float(processor._get_video_duration(video_path) or 0)
    except Exception:
        pass
    if video_duration <= 0:
        return False

    # Determine which tracks to download
    # Always try source_lang + its YouTube aliases; add 'en'/'en-orig' if source is not English
    candidates: List[str] = []
    for code in yt_codes_for_lang(source_lang):
        if code in available:
            candidates.append(code)
            break  # one source-lang code is enough
    if source_lang not in ("en",):
        for en_code in ("en-orig", "en"):
            if en_code in available and en_code not in candidates:
                candidates.append(en_code)
                break

    if not candidates:
        processor.logger.info("📭 No relevant YouTube subtitle tracks found in info.json.")
        return False

    processor.logger.info(
        f"🎬 Auto-checking YouTube subtitles: {candidates} (threshold={quality_threshold:.2f})"
    )
    emit_progress(3, "🎬 Checking YouTube subtitles...")

    downloaded: Dict[str, str] = {}   # {normalized_lang: local_srt_path}
    qualities: Dict[str, QualityResult] = {}

    with tempfile.TemporaryDirectory() as tmp:
        for code in candidates:
            srt = _download_one_yt_track(yt_dlp_bin, url, code, tmp)
            if not srt:
                processor.logger.info(f"  ↳ {code}: not available")
                continue
            norm = normalize_yt_lang(code)
            q = assess_subtitle_quality(srt, video_duration)
            processor.logger.info(
                f"  ↳ {code} ({norm}): score={q.score:.2f} "
                f"coverage={q.coverage:.0%} wpm={q.wpm:.0f} {q.reason}"
            )
            downloaded[norm] = srt
            qualities[norm] = q

        if not downloaded:
            processor.logger.info("📭 No YouTube subtitle tracks could be downloaded.")
            return False

        # ── Decision 1: single high-quality track ──────────────────────────
        best_lang = max(qualities, key=lambda l: qualities[l].score)
        best_q = qualities[best_lang]

        if best_q.score >= quality_threshold and best_q.coverage >= 0.72:
            processor.logger.info(
                f"✅ Using YouTube subtitle directly: {best_lang} "
                f"(score={best_q.score:.2f}, coverage={best_q.coverage:.0%})"
            )
            _sh.copy2(downloaded[best_lang], src_srt)
            return True

        # ── Decision 2: complementary tracks → language timeline ───────────
        # For language-map purposes (Whisper will do the actual transcription)
        # we only need coverage, not high quality score.
        total_coverage = sum(q.coverage for q in qualities.values())
        decent_tracks = {l: downloaded[l] for l, q in qualities.items() if q.coverage >= 0.10}

        if len(decent_tracks) >= 2 and total_coverage >= 0.75:
            processor.logger.info(
                f"🌐 Multilingual YouTube tracks detected "
                f"({list(decent_tracks.keys())} combined coverage={total_coverage:.0%}). "
                "Building language timeline for per-segment Whisper transcription..."
            )
            timeline = build_language_timeline(decent_tracks, video_duration)

            if not timeline_is_multilingual(timeline):
                # Timeline collapsed to single language — treat as single-lang
                single_lang = timeline[0].lang if timeline else best_lang
                if single_lang in downloaded:
                    _sh.copy2(downloaded[single_lang], src_srt)
                    return True

            # Transcribe each segment with the correct language
            emit_progress(5, "🌐 Multilingual transcription via language timeline...")
            all_words = processor.transcribe_by_language_timeline(
                video_path, timeline
            )
            if all_words:
                entries = processor.resegment_to_sentences(all_words, None)
                with open(src_srt, "w", encoding="utf-8-sig") as f:
                    for idx, entry in enumerate(entries, 1):
                        f.write(
                            f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n"
                        )
                processor.logger.info(
                    f"✅ Language-timeline transcription complete → {Path(src_srt).name}"
                )
                return True

        # ── Decision 3: partial/low-quality tracks → one as language map ──
        # Use available tracks (even if low coverage/score) to get language
        # boundaries for Whisper. Works even if source_lang track failed to
        # download — English-only at high coverage still signals "mostly English"
        # and the source_lang segment can be inferred from the gap.
        has_src = source_lang in qualities
        has_en = "en" in qualities
        if has_en and source_lang not in ("en",):
            en_q = qualities["en"]
            src_q = qualities.get(source_lang)
            # Trigger if: English covers substantial portion AND either source
            # track has real coverage OR English doesn't cover everything
            # (implying another language fills the gap).
            src_coverage = src_q.coverage if src_q else 0.0
            en_triggers = en_q.coverage > 0.20 and en_q.coverage < 0.98
            src_triggers = src_coverage > 0.05 and src_coverage < 0.80
            if en_triggers or src_triggers:
                src_cov_str = f"{src_q.coverage:.0%}" if src_q else "n/a"
                processor.logger.info(
                    f"🗺️  Low-coverage multilingual hint "
                    f"({source_lang}={src_cov_str}, en={en_q.coverage:.0%}). "
                    "Building language timeline for Whisper..."
                )
                map_tracks: Dict[str, str] = {"en": downloaded["en"]}
                if source_lang in downloaded:
                    map_tracks[source_lang] = downloaded[source_lang]
                timeline = build_language_timeline(map_tracks, video_duration)

                # Fallback: if timeline collapsed to single language (e.g. only
                # en track available), infer source_lang intro from the gap before
                # the first English entry (e.g. Hebrew 0-38s, then English).
                if not timeline_is_multilingual(timeline) and source_lang not in downloaded:
                    from subtitle.quality import LangSegment, _parse_srt
                    en_entries = _parse_srt(downloaded["en"])
                    if en_entries:
                        first_en_start = en_entries[0]["start"]
                        if first_en_start > 15:
                            processor.logger.info(
                                f"🗺️  Inferred {source_lang} intro from en-track gap "
                                f"(0–{first_en_start:.0f}s → {source_lang}, "
                                f"{first_en_start:.0f}s–end → en)"
                            )
                            from subtitle.quality import LangSegment
                            timeline = [
                                LangSegment(0.0, first_en_start, source_lang),
                                LangSegment(first_en_start, video_duration, "en"),
                            ]

                if timeline_is_multilingual(timeline):
                    emit_progress(5, "🌐 Multilingual transcription via language timeline...")
                    all_words = processor.transcribe_by_language_timeline(
                        video_path, timeline
                    )
                    if all_words:
                        entries = processor.resegment_to_sentences(all_words, None)
                        with open(src_srt, "w", encoding="utf-8-sig") as f:
                            for idx, entry in enumerate(entries, 1):
                                f.write(
                                    f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n"
                                )
                        processor.logger.info(
                            f"✅ Language-timeline transcription complete → {Path(src_srt).name}"
                        )
                        return True

    processor.logger.info(
        f"⚠️  YouTube subtitles not good enough (best={best_q.score:.2f}). "
        "Falling back to Whisper."
    )
    return False


def prepare_source_srt(
    processor,
    result: Dict[str, Any],
    original_base: str,
    source_lang: str,
    force: bool,
    current_video_input: str,
    limit_start: float,
    limit_end,
    correct: bool,
    detect_speakers: bool,
    has_limit: bool,
    is_srt_input: bool,
    migrate_legacy_resolution_srt_fn: Callable[[str, str], bool],
    emit_progress,
    yt_subs: bool = False,
    yt_auto: bool = True,
    yt_quality_threshold: float = 0.65,
) -> str:
    """Prepare source SRT via reuse or transcription and apply source pre-processing."""
    src_srt = f"{original_base}_{source_lang}.srt"
    migrate_legacy_resolution_srt_fn(source_lang, src_srt)
    processor.logger.info(f"🔎 Source transcription candidate: {src_srt}")

    if os.path.exists(src_srt) and not force:
        try:
            if os.path.getsize(src_srt) < 50:
                processor.logger.warning(
                    "Existing asset verification failed (undersized); initiating regeneration."
                )
                os.remove(src_srt)
            else:
                processor.logger.info(f"Source asset validation successful: {Path(src_srt).name}")
        except Exception:
            pass
    elif os.path.exists(src_srt) and force:
        processor.logger.info(f"🔄 Force mode enabled; overriding existing asset: {Path(src_srt).name}")
        os.remove(src_srt)

    if not os.path.exists(src_srt):
        # Auto-check YouTube subtitles first (when info.json sidecar is present).
        # Skipped when: --no-yt-auto, --yt-subs already active, --force, --limit, SRT input.
        if (
            yt_auto
            and not yt_subs
            and not is_srt_input
            and not has_limit
        ):
            try:
                _yt_done = _auto_yt_check(
                    processor=processor,
                    video_path=current_video_input,
                    source_lang=source_lang,
                    src_srt=src_srt,
                    quality_threshold=yt_quality_threshold,
                    emit_progress=emit_progress,
                )
                if _yt_done and os.path.exists(src_srt):
                    src_is_fresh = True
                    # Jump to post-processing below by skipping the yt_subs/Whisper branches.
                    pass
            except Exception as _e:
                processor.logger.warning(f"⚠️  Auto YouTube check failed, falling back: {_e}")

        if not os.path.exists(src_srt) and yt_subs:
            # The pre-fetcher in video.sh may not have downloaded the source-language SRT
            # (e.g. user ran --yt-subs but the prefetch only covered target langs like 'fa').
            # Try to fetch it directly before falling back to Whisper.
            processor.logger.info(
                f"⬇️  --yt-subs: source SRT not pre-fetched; attempting yt-dlp download for '{source_lang}'..."
            )
            _yt_downloaded = _download_yt_source_srt(
                processor=processor,
                video_path=current_video_input,
                source_lang=source_lang,
                dest_srt=src_srt,
            )
            if not _yt_downloaded:
                processor.logger.warning(
                    f"⚠️  No YouTube subtitles found for '{source_lang}'. Falling back to Whisper transcription."
                )
                yt_subs = False  # allow Whisper branch below

        if not os.path.exists(src_srt) and not yt_subs:
            processor.logger.info(
                "🎙️ Reusable source transcription not found after probe; Whisper transcription will run."
            )
            actual_dur = (limit_end - limit_start) if limit_end is not None else 0
            emit_progress(5, "🎙️ Transcription with Whisper...")
            generated_srt = processor.transcribe_video(
                current_video_input,
                source_lang,
                correct,
                detect_speakers,
                dur=actual_dur,
            )

            processor.cleanup()

            generated_is_path = isinstance(generated_srt, (str, os.PathLike)) and os.path.exists(str(generated_srt))
            generated_is_raw_srt = isinstance(generated_srt, str) and "-->" in generated_srt and "\n" in generated_srt

            if generated_is_path:
                generated_srt_path = os.path.abspath(os.fspath(generated_srt))
                if generated_srt_path != os.path.abspath(src_srt):
                    processor.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
                    shutil.move(generated_srt_path, src_srt)
            elif generated_is_raw_srt:
                processor.logger.info(f"📝 Writing transcription content to: {Path(src_srt).name}")
                with open(src_srt, "w", encoding="utf-8-sig") as f:
                    f.write(generated_srt)
            else:
                raise FileNotFoundError(
                    "transcribe_video did not return a valid SRT path or raw SRT content"
                )

        src_is_fresh = True
    else:
        processor.logger.info(f"✅ Reusing source transcription without Whisper: {Path(src_srt).name}")
        src_is_fresh = False

    src_entries = processor.parse_srt(src_srt)
    if not isinstance(src_entries, list):
        src_entries = []

    # Re-segment reused source subtitles only when explicitly requested.
    # Re-applying segmentation on every run can progressively alter cue cadence.
    resegment_reused = str(os.environ.get("AMIR_RESEGMENT_REUSED_SOURCE", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }

    if not src_is_fresh and src_entries:
        if resegment_reused:
            resegged_src = processor.resegment_existing_entries(src_entries)
            if isinstance(resegged_src, list) and resegged_src:
                src_entries = resegged_src
                processor.logger.info(
                    f"♻️ Re-segmented reused source subtitles: {Path(src_srt).name}"
                )
        else:
            processor.logger.info(
                "ℹ️ Reused source re-segmentation skipped (set AMIR_RESEGMENT_REUSED_SOURCE=1 to enable)."
            )

    if has_limit and is_srt_input:
        def ts_to_sec(ts: str) -> float:
            ts = ts.replace(",", ".")
            parts = ts.split(":")
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

        before = len(src_entries)
        src_entries = [
            e
            for e in src_entries
            if ts_to_sec(e["start"]) >= limit_start
            and (limit_end is None or ts_to_sec(e["start"]) < limit_end)
        ]
        processor.logger.info(
            f"⏱️  Filtered {before} → {len(src_entries)} entries within "
            f"[{limit_start}s, {'end' if limit_end is None else str(limit_end) + 's'}]"
        )

    # Avoid repeated semantic splitting on already-produced source SRT by default.
    extra_sanitize = str(os.environ.get("AMIR_SOURCE_EXTRA_SANITIZE", "0")).strip().lower() in {
        "1", "true", "yes", "on"
    }
    if extra_sanitize:
        sanitized = processor.sanitize_entries(src_entries)
        if isinstance(sanitized, list):
            src_entries = sanitized

    merged = processor._merge_split_numbers(src_entries)
    if isinstance(merged, list):
        src_entries = merged

    avg_words = sum(len((e.get("text") or "").split()) for e in src_entries) / max(1, len(src_entries))
    src_is_fragmented = len(src_entries) >= 60 and avg_words < 2.3

    if src_is_fragmented and not src_is_fresh:
        processor.logger.info(
            f"📐 Detected fragmented source timeline (avg words/entry={avg_words:.2f}); "
            "applying clause merge."
        )
    
    if src_is_fragmented:
        merged_clauses = processor.merge_to_clauses(src_entries)
        if isinstance(merged_clauses, list):
            src_entries = merged_clauses

        re_sanitized = processor.sanitize_entries(src_entries)
        if isinstance(re_sanitized, list):
            src_entries = re_sanitized
            
    # Always commit the sanitized output back to disk to enforce geometry bounds
    with open(src_srt, "w", encoding="utf-8-sig") as f:
        for idx, entry in enumerate(src_entries, 1):
            f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

    result[source_lang] = src_srt
    return src_srt