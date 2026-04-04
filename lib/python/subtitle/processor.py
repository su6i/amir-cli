#!/usr/bin/env python3
"""
subtitle_processor_complete_working.py
Complete Working Version with ALL Features

This version includes:
- Full transcription support (Whisper + MLX)
- Fixed FFmpeg rendering
- Translation with caching
- All helper methods
"""

import os
import re
import subprocess
import time
import json
import logging
import gc
import socket

# Environment control for library verbosity
# (Set to 0 if full debug needed, 1 hides progress bars)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0" 

import tempfile
import shutil
import threading
import zipfile
from datetime import timedelta
from collections import deque
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from subtitle.config import (
    LANGUAGE_REGISTRY,
    LanguageConfig,
    get_language_config,
    has_target_language_chars,
    load_api_key,
)
from subtitle.cache import (
    clear_checkpoint,
    create_balanced_batches,
    get_checkpoint_path,
    load_local_translation_cache,
    load_checkpoint,
    local_cache_key,
    log_cost_savings,
    save_checkpoint,
    lookup_local_cache,
    save_local_translation_cache,
    store_local_cache,
)
from subtitle.concurrency import (
    acquire_global_workflow_slot,
    acquire_workflow_lock,
    is_pid_alive,
    release_global_workflow_slot,
    release_workflow_lock,
)
from subtitle.io import (
    bundle_outputs_zip,
    collect_existing_output_files,
    detect_video_dimensions,
    ensure_safe_input_filename,
    format_total_seconds,
    format_time,
    get_video_duration,
    normalize_digits,
    parse_to_sec,
    parse_srt_file,
    srt_duration_str,
    sanitize_stem_for_fs,
    to_persian_digits,
    validate_srt_file,
)
from subtitle.transcription import (
    build_mlx_worker_script,
    cleanup_paths,
    ensure_whisper_server,
    flush_partial_entries,
    get_whisper_server_socket_path,
    is_whisper_server_ready,
    parse_verbose_segment_line,
    parse_whisper_progress_time,
    resolve_mlx_repo_path,
    whisper_server_enabled,
)
from subtitle.translation import (
    apply_final_target_text_fixes,
    build_contextual_batch_text,
    filter_gemini_generation_models,
    parse_translated_batch_output,
    rank_gemini_model_name,
    resegment_translation,
    translate_batch_single_attempt as run_translate_batch_single_attempt,
    translate_with_batch_fallback_chain as run_translate_with_batch_fallback_chain,
    validate_and_retry_translations,
    write_partial_translation_srt,
    run_deepseek_translation_pipeline,
    run_gemini_translation_pipeline,
    run_litellm_translation_pipeline,
    run_minimax_translation_pipeline,
)
from subtitle.social import (
    call_llm_for_post,
    compose_post_file_header,
    discover_video_metadata,
    format_publish_date,
    generate_posts as run_generate_posts,
    get_post_prompt,
    sanitize_post,
    telegram_sections_complete,
)
from subtitle.workflow import (
    detect_subtitle_geometry,
    migrate_legacy_resolution_srt,
    prepare_source_srt,
    prepare_runtime_execution,
    resolve_workflow_base,
    run_finalize_stage,
    run_rendering_stage,
    run_translation_stage,
)
from subtitle.segmentation import (
    group_entries_into_paragraphs,
    is_abbrev_dot,
    merge_orphan_segments,
    peek_next_clause_words,
    take_n_words_with_punct_snap,
    take_words_up_to,
    vis_len,
)
from subtitle.sanitization import (
    apply_semantic_splitting,
    deduplicate_consecutive_entries,
    normalize_and_fix_timing,
    postprocess_orphans_and_collocations,
)
from subtitle.rendering import (
    build_ass_events,
    build_ass_header,
    build_ass_styles,
    build_secondary_map,
    compute_ass_layout,
)
from subtitle.text import clean_bidi, fix_persian_text, strip_english_echo
from subtitle.models import (
    ProcessingCheckpoint,
    ProcessingStage,
    STYLE_PRESETS,
    StyleConfig,
    SubtitleStyle,
    WordObj,
)

try:
    from dotenv import load_dotenv
    # Standardize environment load
    load_dotenv()
    
    #Check for Gemini SDK availability
    try:
        from google import genai
        HAS_GEMINI = True
    except ImportError:
        HAS_GEMINI = False

    # Check for LiteLLM availability
    try:
        from litellm import completion
        HAS_LITELLM = True
    except ImportError:
        HAS_LITELLM = False

except ImportError:
    HAS_GEMINI = False
    HAS_LITELLM = False
    
    # Try multiple .env locations even if dotenv not installed
    env_paths = [
        '.env',  # Current directory
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.path.dirname(__file__), '.env'),  # Script directory
        os.path.expanduser('~/.env'),  # Home directory
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            except:
                pass
            break

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# Check availability without full import to save memory
import importlib.util
HAS_MLX = importlib.util.find_spec("mlx_whisper") is not None
HAS_TORCH = importlib.util.find_spec("torch") is not None

try:
    import platform as platform_module
    HAS_PLATFORM = True
except ImportError:
    HAS_PLATFORM = False

# Non-heavy imports
from tqdm import tqdm
from openai import OpenAI

# ==================== CENTRALIZED MEDIA CONFIG ====================
# Import centralized media configuration for encoding standards
import sys
from pathlib import Path
# Add lib/python/ to sys.path to allow direct import of media_config
_media_config_path = str(Path(__file__).parent.parent)
if _media_config_path not in sys.path:
    sys.path.insert(0, _media_config_path)

try:
    from media_config import (
        get_bitrate_multiplier, 
        get_fallback_bitrate, 
        get_default_crf,
        get_default_quality,
        detect_best_hw_encoder
    )
except ImportError:
    # Fallback if media_config not found (backward compatibility)
    def get_bitrate_multiplier(): return 1.1
    def get_fallback_bitrate(): return "2.5M"
    def get_default_crf(): return 23
    def get_default_quality(): return 65
    def detect_best_hw_encoder(): return {'encoder': 'libx264', 'codec': 'h264', 'platform': 'cpu'}

# ==================== MAIN PROCESSOR ====================

class SubtitleProcessor:
    """Complete Working Subtitle Processor"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_size: str = 'turbo',
        cache_dir: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        style: SubtitleStyle = SubtitleStyle.LECTURE,
        max_lines: int = 2,
        alignment: Optional[int] = None,
        font_size: Optional[int] = None,
        sec_font_size: Optional[int] = None,
        shadow: Optional[int] = None,
        outline: Optional[int] = None,
        back_color: Optional[str] = None,
        primary_color: Optional[str] = None,
        fail_on_translation_error: bool = True,
        use_openai_fallback: bool = False,
        initial_prompt: Optional[str] = None,
        temperature: float = 0.0,
        min_duration: float = 1.0,
        llm: str = "deepseek",
        custom_model: Optional[str] = None,
        use_bert: bool = False,
        bert_model: Optional[str] = None,
        use_vad: bool = True
    ):
        self.api_key = api_key or self.load_api_key()
        # Support both naming conventions
        self.google_api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
        self.minimax_api_key = os.environ.get('MINIMAX_API_KEY', '')
        self.grok_api_key = os.environ.get('GROK_API_KEY', '')
        self.llm_choice = llm.lower()
        self.custom_model = custom_model # For LiteLLM testing
        
        # LLM Model names (configurable, not hardcoded)
        self.llm_models = {
            "deepseek": os.environ.get("AMIR_MODEL_DEEPSEEK", "deepseek-chat"),
            "minimax": os.environ.get("AMIR_MODEL_MINIMAX", "abab6.5s-chat"),
            "gemini": os.environ.get("AMIR_MODEL_GEMINI", "gemini-2.5-flash"),
            "grok": os.environ.get("AMIR_MODEL_GROK", "grok-4.1")
        }
        
        # BERT options (optional, lazy-loaded)
        self.use_bert = use_bert
        self.bert_model = bert_model or os.environ.get('AMIR_BERT_MODEL')
        self.use_vad = use_vad
        
        # LiteLLM API Key Normalization: Ensure DEEPSEEK_API_KEY for LiteLLM
        if self.api_key and 'DEEPSEEK_API_KEY' not in os.environ:
            os.environ['DEEPSEEK_API_KEY'] = self.api_key
        self.model_size = model_size
        
        # FIX: Copy the preset to avoid modifying the global dictionary
        base_style = STYLE_PRESETS.get(style, STYLE_PRESETS[SubtitleStyle.LECTURE])
        self.style_config = StyleConfig(**base_style.__dict__)
        
        self.en_font_scale = 1.0
        self.fa_font_name = 'Vazirmatn'
        self.fa_font_scale = 1.0
        
        # Override with media.json configuration if available
        try:
            from media_config import MediaConfig
            config = MediaConfig()
            
            # Load scale settings
            self.en_font_scale = float(config.get('video.subtitle.fonts.english.scale', 1.0))
            self.fa_font_name = config.get('video.subtitle.fonts.persian.name', 'Vazirmatn')
            self.fa_font_scale = float(config.get('video.subtitle.fonts.persian.scale', 1.0))
            
            # Load English font name override
            self.style_config.font_name = config.get('video.subtitle.fonts.english.name', self.style_config.font_name)
            
            # Try to load preset style overrides (e.g. 'Lecture', 'Vlog' base font_size)
            style_overrides = config.get(f"video.subtitle.styles.{self.style_config.name}", {})
            for k, v in style_overrides.items():
                if hasattr(self.style_config, k):
                    setattr(self.style_config, k, v)
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.warning(f"Could not load media.json subtitle styles: {e}")
            
        # Apply overrides from CLI arguments
        self.style_config.max_lines = max_lines
        if alignment is not None: self.style_config.alignment = alignment
        if font_size is not None: self.style_config.font_size = font_size
        if shadow is not None: self.style_config.shadow = shadow
        if outline is not None: self.style_config.outline = outline
        if back_color is not None: self.style_config.back_color = back_color
        if primary_color is not None: self.style_config.primary_color = primary_color
        
        # Finally, apply the english font scaling factor
        self.style_config.font_size = int(self.style_config.font_size * self.en_font_scale)
        
        # Priority for secondary font size: arg > media.json (style_config) > default (scaled by fa_font_scale)
        if sec_font_size:
            self.sec_font_size = sec_font_size
        else:
            base_sec_size = getattr(self.style_config, 'secondary_font_size', None)
            if base_sec_size is not None:
                self.sec_font_size = int(base_sec_size * self.fa_font_scale)
            else:
                # If no secondary size defined, default to 75% of primary size, scaled
                self.sec_font_size = int(self.style_config.font_size * 0.75 * self.fa_font_scale)
        
        self.fail_on_translation_error = fail_on_translation_error
        self.use_openai_fallback = use_openai_fallback
        self.initial_prompt = initial_prompt
        self.temperature = temperature
        self.min_duration = min_duration
        
        # Check for OpenAI key if fallback enabled
        if use_openai_fallback:
            self.openai_key = os.environ.get('OPENAI_API_KEY', '')
            if not self.openai_key:
                self.logger.warning("OpenAI fallback enabled but OPENAI_API_KEY environment variable is not defined.")
        
        self.cache_dir = Path(cache_dir or os.path.expanduser("~/.amir_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # === COST SAVING INFRASTRUCTURE ===
        # Local hash cache: avoids API calls for already-translated sentences
        self._local_cache_path = self.cache_dir / "translation_cache.json"
        self._local_cache: Dict[str, str] = {}
        self._local_cache_dirty = False  # Track if we need to save
        
        # Gemini explicit CachedContent: stores the system prompt server-side (reused per session)
        # key = target_lang, value = cache_name from Gemini API
        self._gemini_content_cache: Dict[str, str] = {}
        
        # Cost tracking (accumulated per session)
        self._cost_savings = {"local_cache_hits": 0, "deepseek_cache_hit_tokens": 0, "grok_cache_hit_tokens": 0, "gemini_cached_tokens": 0}
        
        # Target words per subtitle line (adaptive: set by run_workflow based on video orientation)
        self.target_words_per_line = 7
        # Global cross-process concurrency cap (opt-in via env).
        # Use AMIR_SUBTITLE_MAX_CONCURRENT=1 to serialize heavy jobs and reduce RAM spikes.
        try:
            _cap_raw = os.environ.get('AMIR_SUBTITLE_MAX_CONCURRENT', '').strip()
            self.max_concurrent_workflows = int(_cap_raw) if _cap_raw else 0
            if self.max_concurrent_workflows < 0:
                self.max_concurrent_workflows = 0
        except Exception:
            self.max_concurrent_workflows = 0
        self._model = None
        self.logger = logger or self._setup_logger()
        self._check_disk_space()
        
        # Load local translation cache (needs logger to be ready)
        self._load_local_translation_cache()
        
        self.logger.info(f"Initialization complete (model={model_size}, style={style.value})")

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("SubtitleProcessor")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
            console.setFormatter(fmt)
            logger.addHandler(console)
            
            log_file = self.cache_dir / "subtitle_processor.log"
            file_h = logging.FileHandler(log_file)
            file_h.setLevel(logging.DEBUG)
            file_h.setFormatter(fmt)
            logger.addHandler(file_h)
        
        return logger

    def _check_disk_space(self, min_gb: int = 10):
        try:
            total, used, free = shutil.disk_usage(self.cache_dir)
            free_gb = free // (2**30)
            if free_gb < min_gb:
                self.logger.warning(f"Resource threshold warning: available disk space is {free_gb}GB (minimum requirement: {min_gb}GB)")
        except:
            pass

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        return is_pid_alive(pid)

    def _acquire_workflow_lock(self, lock_key: str, source_path: str) -> str:
        return acquire_workflow_lock(lock_key, source_path)

    def _release_workflow_lock(self, lock_path: Optional[str]):
        release_workflow_lock(lock_path)

    def _acquire_global_workflow_slot(self, source_path: str) -> Optional[str]:
        cap = int(getattr(self, 'max_concurrent_workflows', 0) or 0)
        return acquire_global_workflow_slot(source_path, cap, logger=self.logger)

    def _release_global_workflow_slot(self, slot_path: Optional[str]):
        release_global_workflow_slot(slot_path)

    @staticmethod
    def _sanitize_stem_for_fs(stem: str) -> str:
        return sanitize_stem_for_fs(stem)

    def _ensure_safe_input_filename(self, file_path: str) -> str:
        return ensure_safe_input_filename(file_path, logger=self.logger)

    @staticmethod
    def _collect_existing_output_files(result: Dict[str, Any]) -> List[str]:
        return collect_existing_output_files(result)

    def _bundle_outputs_zip(self, base_path: str, files: List[str]) -> Optional[str]:
        return bundle_outputs_zip(base_path, files, logger=self.logger)

    def _detect_video_dimensions(self, video_path: str) -> tuple:
        return detect_video_dimensions(video_path)

    def _get_video_duration(self, video_path: str) -> float:
        return get_video_duration(video_path)

    @staticmethod
    def load_api_key(config_file: str = '.config') -> str:
        return load_api_key(config_file)

    # ==================== SHARED WHISPER SERVER ====================

    def _whisper_server_enabled(self) -> bool:
        return whisper_server_enabled()

    def _get_whisper_server_socket_path(self) -> str:
        return get_whisper_server_socket_path(self.model_size)

    def _is_whisper_server_ready(self, socket_path: str) -> bool:
        return is_whisper_server_ready(socket_path)

    def _ensure_whisper_server(self) -> Optional[str]:
        return ensure_whisper_server(self.model_size, logger=self.logger)

    def _transcribe_via_server(
        self,
        media_path: str,
        language: str = '',
        use_vad: bool = True,
        min_silence_duration_ms: int = 700,
        speech_pad_ms: int = 400,
    ) -> Tuple[List[WordObj], str]:
        """Request transcription from shared whisper server.

        Returns (words, detected_lang). Raises on transport/server errors.
        """
        socket_path = self._ensure_whisper_server()
        if not socket_path:
            raise RuntimeError("whisper server is not available")

        req = {
            "path": media_path,
            "language": (language or '').strip().lower() or None,
            "word_timestamps": True,
            "vad_filter": bool(use_vad),
            "vad_parameters": {
                "min_silence_duration_ms": int(min_silence_duration_ms),
                "speech_pad_ms": int(speech_pad_ms),
            },
            "initial_prompt": self.initial_prompt or "Clear punctuation and case sensitivity.",
            "temperature": self.temperature,
        }

        payload = json.dumps(req, ensure_ascii=False).encode("utf-8")
        chunks = []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(600)
            s.connect(socket_path)
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)

        raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
        if not raw:
            raise RuntimeError("empty response from whisper server")

        resp = json.loads(raw)
        if isinstance(resp, dict) and resp.get("error"):
            raise RuntimeError(str(resp.get("error")))

        word_dicts = resp.get("words", []) if isinstance(resp, dict) else []
        detected_lang = str(resp.get("language", "") or "").strip().lower() if isinstance(resp, dict) else ''
        words = [WordObj(float(w["start"]), float(w["end"]), str(w["word"])) for w in word_dicts]
        return words, detected_lang

    # ==================== MODEL MANAGEMENT ====================

    @property
    def model(self):
        """Lazy load Whisper model"""
        if self._model is None:
            force_faster = os.environ.get("AMIR_FORCE_FASTER_WHISPER", "0") == "1"
            if not force_faster and HAS_MLX and HAS_PLATFORM and platform_module.system() == "Darwin" and platform_module.machine() == "arm64":
                self.logger.info(f"Utilizing MLX acceleration for {self.model_size}")
                self._model = "MLX"
                return self._model
            
            from faster_whisper import WhisperModel
            self.logger.info(f"Loading Whisper neural model ({self.model_size})")
            device = "cpu"
            try:
                import torch
                if HAS_TORCH and torch.cuda.is_available():
                    device = "cuda"
            except:
                pass
            
            self._model = WhisperModel(self.model_size, device=device, compute_type="int8")
        
        return self._model

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    # ==================== CHECKPOINT ====================

    def save_checkpoint(self, checkpoint: ProcessingCheckpoint):
        try:
            save_checkpoint(self.cache_dir, checkpoint)
        except Exception as e:
            self.logger.error(f"Checkpoint save failed: {e}")

    def load_checkpoint(self, video_path: str) -> Optional[ProcessingCheckpoint]:
        return load_checkpoint(self.cache_dir, video_path)

    def clear_checkpoint(self, video_path: str):
        clear_checkpoint(self.cache_dir, video_path)

    def _get_checkpoint_path(self, video_path: str) -> Path:
        return get_checkpoint_path(self.cache_dir, video_path)

    # ==================== CACHE ====================

    def _create_balanced_batches(self, indices: List[int], texts: List[str], max_batch_size: int, max_chars: int = 5000) -> List[List[int]]:
        return create_balanced_batches(indices, texts, max_batch_size, max_chars=max_chars, logger=self.logger)

    # Cache system removed - users manage their own SRT files

    # ==================== COST SAVING HELPERS ====================

    def _local_cache_key(self, text: str, target_lang: str) -> str:
        return local_cache_key(text, target_lang)

    def _load_local_translation_cache(self):
        self._local_cache = load_local_translation_cache(self._local_cache_path, logger=self.logger)

    def _save_local_translation_cache(self):
        if not self._local_cache_dirty:
            return
        if save_local_translation_cache(self._local_cache_path, self._local_cache, logger=self.logger):
            self._local_cache_dirty = False

    def _lookup_local_cache(self, text: str, target_lang: str) -> Optional[str]:
        return lookup_local_cache(self._local_cache, text, target_lang)

    def _store_local_cache(self, text: str, target_lang: str, translation: str):
        if store_local_cache(self._local_cache, text, target_lang, translation):
            self._local_cache_dirty = True

    def _get_gemini_content_cache(self, target_lang: str) -> Optional[str]:
        """
        Get or create a Gemini server-side CachedContent for the system instruction.
        This caches the system prompt on Gemini's servers (TTL=60min),
        so all batch calls share the same cached system tokens = guaranteed cost savings.
        
        Returns the cache name (string) or None if unavailable.
        """
        if not HAS_GEMINI or not self.google_api_key:
            return None
        
        # Return existing cache for this session
        if target_lang in self._gemini_content_cache:
            return self._gemini_content_cache[target_lang]
        
        try:
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(api_key=self.google_api_key)
            
            system_instruction = self.get_translation_prompt(target_lang)
            model = self.llm_models["gemini"]
            
            # Create a CachedContent with the system instruction, TTL=60min
            cache = client.caches.create(
                model=model,
                config=genai_types.CreateCachedContentConfig(
                    display_name=f"amir_translation_{target_lang}",
                    system_instruction=system_instruction,
                    ttl="3600s",
                )
            )
            self._gemini_content_cache[target_lang] = cache.name
            self.logger.info(f"✅ Gemini explicit cache created for {target_lang.upper()}: {cache.name}")
            return cache.name
        except Exception as e:
            self.logger.debug(f"Gemini explicit cache unavailable (falling back to implicit): {e}")
            return None

    def _log_cost_savings(self):
        log_cost_savings(self._cost_savings, self.logger)

    def detect_source_language(self, video_path: str) -> str:
        """Detect source language from audio using a lightweight Whisper pass."""
        try:
            from faster_whisper import WhisperModel

            detector = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, info = detector.transcribe(
                video_path,
                language=None,
                task="transcribe",
                word_timestamps=False,
                beam_size=1,
                condition_on_previous_text=False,
                temperature=0.0,
            )

            # Start generator once so info metadata is reliably populated.
            try:
                next(iter(segments))
            except StopIteration:
                pass

            detected = str(getattr(info, "language", "") or "").strip().lower()
            if re.fullmatch(r"[a-z]{2,3}", detected):
                self.logger.info(f"🌐 Auto-detected source language: {detected}")
                return detected
        except Exception as e:
            self.logger.warning(f"⚠️ Source auto-detect failed, fallback=en: {e}")

        return "en"



    def transcribe_video(
        self,
        video_path: str,
        language: str = 'auto',
        correct: bool = False,
        detect_speakers: bool = False,
        dur: float = 0
    ) -> str:
        """Main transcription gate"""
        _lang = (language or 'auto').strip().lower()
        force_faster = os.environ.get("AMIR_FORCE_FASTER_WHISPER", "0") == "1"
        if (not force_faster) and HAS_MLX and HAS_PLATFORM and platform_module.system() == "Darwin" and platform_module.machine() == "arm64":
            try:
                return self.transcribe_video_mlx(video_path, _lang, correct, detect_speakers, dur_override=dur)
            except Exception as e:
                self.logger.warning(f"⚠️ MLX transcription failed, falling back to Whisper: {e}")
        elif force_faster:
            self.logger.info("🧠 Low-RAM mode: forcing faster-whisper path (MLX disabled for this run).")
        return self.transcribe_video_whisper(video_path, _lang, correct, detect_speakers)

    def _run_faster_whisper_slice(self, video_path: str, max_duration: int = 60) -> Tuple[List[WordObj], str]:
        """Extracts the first N seconds using FFmpeg and transcribes with Faster-Whisper + VAD to fix MLX hallucination bugs."""
        import subprocess
        import tempfile
        from faster_whisper import WhisperModel
        
        # 1. Extract audio slice
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            slice_path = f.name
        
        try:
            self.logger.info(f"🔪 Slicing first {max_duration}s for Faster-Whisper VAD anti-hallucination pass...")
            # ffmpeg -y -i input -t 60 -q:a 0 -map a temp.wav
            cmd = [
                'ffmpeg', '-y', '-i', video_path, '-t', str(max_duration),
                '-q:a', '0', '-vn', '-f', 'wav', slice_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # 2. Transcribe slice
            device = "cpu"
            try:
                import torch
                if HAS_TORCH and torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                pass
                
            model = WhisperModel(self.model_size, device=device, compute_type="int8")
            segments, info = model.transcribe(
                slice_path,
                word_timestamps=True,
                initial_prompt=self.initial_prompt or "Clear punctuation and case sensitivity.",
                temperature=self.temperature,
                vad_filter=self.use_vad,
                vad_parameters=dict(min_silence_duration_ms=700, speech_pad_ms=400)
            )
            
            detected_lang = str(getattr(info, 'language', '') or '').strip().lower()
            all_words = []
            for segment in segments:
                if segment.words:
                    for w in segment.words:
                        # Append the WordObj (start, end, word)
                        all_words.append(WordObj(w.start, w.end, w.word))
            
            self.logger.info(f"✨ VAD slice complete. Retrieved {len(all_words)} words in the first {max_duration}s.")
            return all_words, detected_lang
            
        except Exception as e:
            self.logger.warning(f"⚠️ Faster-Whisper slicing pass failed: {e}. Falling back to full MLX.")
            return [], ""
        finally:
            if os.path.exists(slice_path):
                try: os.remove(slice_path)
                except: pass

    def _run_faster_whisper_full(self, video_path: str, language: str = '') -> Tuple[List[WordObj], str]:
        """Full-video transcription using faster-whisper + VAD.
        
        This is the production-grade, hallucination-free transcription path.
        - Uses VAD to cleanly skip silence/non-speech sections that cause MLX 30s lock bugs.
        - Processes audio in 10-minute chunks (overlapping by 5s) so progress is shown.
        - Falls back gracefully to an empty list on error (caller handles fallback).
        """
        import tempfile
        from faster_whisper import WhisperModel
        
        _lang = (language or 'auto').strip().lower()
        _lang_for_engine = None if _lang in ('auto', 'detect', '') else _lang

        # Preferred path: shared whisper server (single model shared across processes).
        try:
            server_words, server_lang = self._transcribe_via_server(
                video_path,
                language=_lang_for_engine or '',
                use_vad=self.use_vad,
                min_silence_duration_ms=700,
                speech_pad_ms=400,
            )
            if server_words:
                self.logger.info(f"✅ Shared-server transcription complete: {len(server_words)} words")
                return server_words, (server_lang or '')
        except Exception as e:
            self.logger.warning(f"⚠️ Shared whisper server failed, using local model: {e}")

        # Get total duration for progress reporting
        total_dur = 0.0
        try:
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            res = subprocess.run(dur_cmd, capture_output=True, text=True)
            if res.stdout.strip():
                total_dur = float(res.stdout.strip())
        except Exception:
            pass

        self.logger.info(f"🔬 Full-video faster-whisper VAD pass ({total_dur:.0f}s)...")

        # Load model once
        device = "cpu"
        try:
            import torch
            if HAS_TORCH and torch.cuda.is_available():
                device = "cuda"
        except Exception:
            pass
        
        try:
            model = WhisperModel(self.model_size, device=device, compute_type="int8")
        except Exception as e:
            self.logger.warning(f"⚠️ faster-whisper model load failed: {e}. Falling back to MLX.")
            return [], ''

        CHUNK = 600   # 10-min chunks
        OVERLAP = 5   # 5s overlap to avoid cutting mid-word at boundaries
        all_words: List[WordObj] = []
        detected_lang = ''
        seen_ends: set = set()

        start = 0.0
        chunk_idx = 0
        tmp_wav = None
        try:
            while True:
                end = min(start + CHUNK, total_dur) if total_dur > 0 else start + CHUNK
                duration = end - start

                # Extract audio chunk
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_wav = f.name

                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-ss', str(start), '-t', str(duration + OVERLAP),
                    '-q:a', '0', '-vn', '-f', 'wav', tmp_wav
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                kw = dict(
                    word_timestamps=True,
                    initial_prompt=self.initial_prompt or "Clear punctuation and case sensitivity.",
                    temperature=self.temperature,
                    vad_filter=self.use_vad,
                    vad_parameters=dict(min_silence_duration_ms=700, speech_pad_ms=400),
                )
                if _lang_for_engine:
                    kw['language'] = _lang_for_engine
                
                segments, info = model.transcribe(tmp_wav, **kw)

                if chunk_idx == 0 and not detected_lang:
                    detected_lang = str(getattr(info, 'language', '') or '').strip().lower()

                chunk_words = 0
                for seg in segments:
                    if not seg.words:
                        continue
                    for w in seg.words:
                        abs_start = w.start + start
                        abs_end = w.end + start
                        # De-duplicate words from overlap window
                        key = round(abs_end, 2)
                        if key in seen_ends:
                            continue
                        seen_ends.add(key)
                        all_words.append(WordObj(abs_start, abs_end, w.word))
                        chunk_words += 1

                pct = int((end / total_dur) * 100) if total_dur > 0 else 0
                self.logger.info(f"PROGRESS:{5 + int(pct * 0.44)}:🎙️ VAD Transcription ({pct}%)")
                self.logger.info(f"  ✅ Chunk {chunk_idx+1}: +{chunk_words} words (total {len(all_words)})")

                os.remove(tmp_wav)
                tmp_wav = None

                chunk_idx += 1
                if total_dur > 0 and start + CHUNK >= total_dur:
                    break
                start += CHUNK
                if total_dur <= 0 and chunk_words == 0:
                    # No more audio
                    break

        except Exception as e:
            self.logger.warning(f"⚠️ faster-whisper full-video pass error: {e}. Falling back to MLX.")
            if tmp_wav and os.path.exists(tmp_wav):
                try: os.remove(tmp_wav)
                except: pass
            return [], ''

        self.logger.info(f"✅ Full-video VAD transcription complete: {len(all_words)} words, lang={detected_lang or 'auto'}")
        return all_words, detected_lang


    def transcribe_video_whisper(
        self,
        video_path: str,
        language: str = 'auto',
        correct: bool = False,
        detect_speakers: bool = False
    ) -> str:
        """Transcribe video with Whisper (Standard Torch)"""
        from faster_whisper import WhisperModel
        
        _lang = (language or 'auto').strip().lower()
        _lang_for_engine = None if _lang in ('auto', 'detect', '') else _lang
        self.logger.info(f"Transcription process initiated (ISO: {(_lang_for_engine or 'AUTO').upper()})")

        # Preferred path: shared server to avoid per-process model duplication.
        try:
            all_words, detected_lang = self._transcribe_via_server(
                video_path,
                language=_lang_for_engine or '',
                use_vad=True,
                min_silence_duration_ms=700,
                speech_pad_ms=400,
            )
            if all_words:
                out_lang = _lang if _lang_for_engine else (detected_lang if re.fullmatch(r"[a-z]{2,3}", detected_lang) else 'en')
                if _lang_for_engine is None and out_lang:
                    self.logger.info(f"🌐 Whisper detected source language: {out_lang}")

                entries = self.resegment_to_sentences(all_words, None)
                srt_path = os.path.splitext(video_path)[0] + f"_{out_lang}.srt"
                with open(srt_path, 'w', encoding='utf-8-sig') as f:
                    for i, entry in enumerate(entries, 1):
                        f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

                self.logger.info(f"Asset preservation complete: {Path(srt_path).name}")
                return srt_path
        except Exception as e:
            self.logger.warning(f"⚠️ Shared whisper server unavailable, loading local model: {e}")
        
        model = self.model
        if not hasattr(model, "transcribe"):
            # On Apple Silicon, self.model can be a sentinel string when MLX path is preferred.
            device = "cpu"
            try:
                import torch
                if HAS_TORCH and torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                pass
            model = WhisperModel(self.model_size, device=device, compute_type="int8")

        segments, info = model.transcribe(
            video_path,
            language=_lang_for_engine,
            word_timestamps=True,
            initial_prompt=self.initial_prompt or "Clear punctuation and case sensitivity.",
            temperature=self.temperature,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=700, speech_pad_ms=400)
        )

        detected_lang = str(getattr(info, 'language', '') or '').strip().lower()
        out_lang = _lang if _lang_for_engine else (detected_lang if re.fullmatch(r"[a-z]{2,3}", detected_lang) else 'en')
        if _lang_for_engine is None and out_lang:
            self.logger.info(f"🌐 Whisper detected source language: {out_lang}")
        
        all_words = []
        pbar = tqdm(total=int(info.duration), unit="s", desc="  Processing")
        
        last_end = 0
        for segment in segments:
            diff = int(segment.end) - last_end
            if diff > 0:
                pbar.update(diff)
                last_end = int(segment.end)
            
            if segment.words:
                all_words.extend(segment.words)
        
        if last_end < int(info.duration):
            pbar.update(int(info.duration) - last_end)
        
        pbar.close()
        
        entries = self.resegment_to_sentences(all_words, None)
        
        srt_path = os.path.splitext(video_path)[0] + f"_{out_lang}.srt"
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, entry in enumerate(entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        
        self.logger.info(f"Asset preservation complete: {Path(srt_path).name}")
        return srt_path

    def transcribe_video_mlx(self, video_path: str, language: str, correct: bool, detect_speakers: bool, dur_override: float = 0) -> str:
        """Transcription: faster-whisper + VAD for hallucination-free output (primary path),
        with MLX subprocess as fallback for speed on Apple Silicon."""
        _lang = (language or 'auto').strip().lower()
        _lang_for_worker = '' if _lang in ('auto', 'detect', '') else _lang
        self.logger.info(f"☢️ Initiating Transcription (Primary: faster-whisper VAD, Fallback: MLX | ISO: {(_lang_for_worker or 'AUTO').upper()})")

        # --- PRIMARY PASS: full-video faster-whisper + VAD ---
        vad_words, vad_lang = self._run_faster_whisper_full(video_path, language=_lang_for_worker)
        if not _lang_for_worker and vad_lang:
            _lang_for_worker = vad_lang
            self.logger.info(f"🌐 VAD auto-detected language: {_lang_for_worker}")

        all_words: List[WordObj] = vad_words
        detected_lang: str = vad_lang

        # --- FALLBACK: MLX subprocess if VAD produced no words ---
        if not all_words:
            self.logger.warning("⚠️ VAD produced no words. Falling back to MLX subprocess...")

            # 1. Create temporary JSON for results
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                result_json_path = f.name
            
            # 2. Create the worker script
            repo_path = resolve_mlx_repo_path(self.model_size)
            worker_script = build_mlx_worker_script(
                repo_path=repo_path,
                language=_lang_for_worker,
                video_path=video_path,
                result_json_path=result_json_path,
            )
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
                worker_path = f.name
                f.write(worker_script.encode('utf-8'))
                
            try:
                # 3. Run the worker with streaming output
                # Get video duration for progress bar
                dur = dur_override or 0
                if dur <= 0:
                    try:
                        dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
                        res = subprocess.run(dur_cmd, capture_output=True, text=True)
                        output = res.stdout.strip()
                        if output:
                            dur = float(output)
                    except:
                        pass
                
                if dur > 0:
                    self.logger.info(f"📊 Tracking progress over {dur:.1f}s duration.")
                else:
                    self.logger.warning("⚠️ Could not detect duration; progress bar will be limited.")

                cmd = ["python3", "-u", worker_path]
                # Use Popen to stream stdout/stderr
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                
                pbar = tqdm(total=100, unit="%", desc=f"  Transcribing ({(_lang_for_worker or 'AUTO').upper()})")

                # --- Incremental checkpoint setup ---
                partial_srt_path = os.path.splitext(video_path)[0] + f"_{_lang_for_worker or 'auto'}.partial.srt"
                partial_entries = []

                _last_emitted_pct = [4]  # Start below 5 so first emission fires at 5%
                stdout_tail = []
                while True:
                    line = proc.stdout.readline()
                    if not line and proc.poll() is not None:
                        break
                    
                    if line:
                        stdout_tail.append(line.strip())
                        if len(stdout_tail) > 80:
                            stdout_tail = stdout_tail[-80:]
                        # Log errors from worker if any
                        if "WORKER_ERROR" in line:
                            self.logger.error(f"  {line.strip()}")

                        # Incremental checkpoint: save every 20 parsed segments
                        seg = parse_verbose_segment_line(line)
                        if seg:
                            partial_entries.append(seg)
                            if len(partial_entries) % 20 == 0:
                                try:
                                    flush_partial_entries(partial_entries, partial_srt_path)
                                except Exception:
                                    pass
                            
                        curr_time = parse_whisper_progress_time(line)
                        if curr_time and dur > 0:
                            pct = min(100, (curr_time / dur) * 100)
                            pbar.n = int(pct)
                            pbar.refresh()
                            # Map 0-100% transcription → PROGRESS 5-50% (leaves headroom for translation)
                            _trans_pct = max(5, min(50, int(5 + pct * 0.45)))
                            if _trans_pct - _last_emitted_pct[0] >= 5:
                                self.logger.info(f"PROGRESS:{_trans_pct}:🎙️ Transcription ({int(pct)}%)")
                                _last_emitted_pct[0] = _trans_pct
                
                proc.wait()
                pbar.n = 100
                pbar.refresh()
                pbar.close()
                try:
                    flush_partial_entries(partial_entries, partial_srt_path)
                except Exception:
                    pass
                
                if proc.returncode != 0:
                    stderr = proc.stderr.read()
                    stdout_excerpt = "\n".join(stdout_tail[-30:])
                    combined = (f"stderr:\n{stderr.strip()}\n\nstdout:\n{stdout_excerpt.strip()}").strip()
                    self.logger.error(f"❌ Isolated worker failed: {combined}")
                    raise RuntimeError(f"Transcription worker failed: {combined}")
                
                # 4. Load results
                if not os.path.exists(result_json_path):
                    raise RuntimeError("Isolated worker exited without producing results.")
                    
                with open(result_json_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)

                if isinstance(payload, dict):
                    word_dicts = payload.get('words', [])
                    detected_lang = str(payload.get('language', '') or '').strip().lower()
                else:
                    word_dicts = payload
                    detected_lang = ''
                
                all_words = [WordObj(w['start'], w['end'], w['word']) for w in word_dicts]
                self.logger.info(f"✅ MLX fallback complete. {len(all_words)} words retrieved.")
                
            finally:
                # Cleanup worker files
                cleanup_paths([worker_path, result_json_path])
                # Remove incremental checkpoint now that the final SRT is written
                try:
                    if os.path.exists(partial_srt_path):
                        os.remove(partial_srt_path)
                except Exception:
                    pass

        entries = self.resegment_to_sentences(all_words, None)
        
        # Final cleanup for the main process just in case
        self.cleanup()
        
        # Use original video name for SRT output
        final_video_name = Path(video_path).stem
        if "safe_input" in video_path or "temp_" in video_path:
            final_video_name = re.sub(r'^(temp_\d+_|safe_)', '', final_video_name)
            
        out_lang = _lang if _lang_for_worker else (detected_lang if re.fullmatch(r"[a-z]{2,3}", detected_lang) else 'en')
        if _lang_for_worker == '' and out_lang:
            self.logger.info(f"🌐 Auto-detected source language: {out_lang}")
        srt_path = os.path.splitext(video_path)[0] + f"_{out_lang}.srt"
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, entry in enumerate(entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

        self.logger.info(f"MLX asset preservation complete: {Path(srt_path).name}")
        return srt_path

    def _remove_whisper_artifacts(self, text: str) -> str:
        """Remove Whisper transcription artifacts like \\h (hard breaks)"""
        if not text:
            return text
        # Remove \h (hard breaks) and replace with space
        text = re.sub(r'\\h+', ' ', text)
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def suppress_hallucinations(self, entries: List[Dict]) -> List[Dict]:
        """DeepSeek/Whisper hallucination suppressor"""
        if not entries: return []
        
        clean = []
        last_text = ""
        
        for e in entries:
            # First, remove Whisper artifacts
            e['text'] = self._remove_whisper_artifacts(e['text'])
            
            current_text = e['text'].strip().lower()
            # 1. Exact repetition check
            if current_text == last_text:
                continue
            
            # 2. Fuzzy repetition check (for slight variations)
            if len(current_text) > 10 and len(last_text) > 10:
                # If one is a substring of the other (very common loop pattern)
                if current_text in last_text or last_text in current_text:
                    # Keep the longer one if it adds information, otherwise skip
                    # heuristic: if length difference is small, it's likely a stutter/loop
                    if abs(len(current_text) - len(last_text)) < 5:
                        continue

            clean.append(e)
            last_text = current_text
            
        return clean

    def resegment_to_sentences(self, words: List, speaker_segments) -> List[Dict]:
        """Thin wrapper: delegates to segment_words_smart for backward compatibility."""
        return self.segment_words_smart(words)

    def merge_to_clauses(self, entries: List[Dict]) -> List[Dict]:
        """Thin wrapper: merge_to_clauses is now a no-op.
        segment_words_smart handles clause boundaries directly from word timestamps.
        Kept for call-site compatibility only."""
        self.logger.debug("merge_to_clauses: skipped (absorbed into segment_words_smart)")
        return entries

    def segment_words_smart(self, words: List) -> List[Dict]:
        """Single-pass smart segmentation: Whisper words → subtitle entries.

        Design principles
        -----------------
        1. ONE decision point per word — no separate merge/split passes that
           undo each other's work.
        2. Hard sentence boundaries (. ? ! …) always flush.
        3. Clause-starter guard: never break immediately before a subordinating
           conjunction / relative pronoun (who/which/that/because/…) unless the
           hard char ceiling is already exceeded.
        4. Soft breaks (comma/semicolon/colon) flush only when the current
           segment is long enough AND the next clause is long enough to stand alone.
        5. Time ceiling: flush if a segment spans > MAX_SEG_SEC seconds even
           without punctuation (handles run-on speech).
        6. Orphan prevention: segments with ≤ 2 words are merged into their
           neighbour after the main pass.
        """
        if not words:
            return []

        # ── tunables ─────────────────────────────────────────────────────────
        limit      = getattr(self.style_config, 'max_chars', 42)   # soft char target
        hard_limit = limit + 12          # absolute ceiling before forced break
        MIN_WORDS  = max(3, int(getattr(self, 'target_words_per_line', 4) or 4))
        MAX_SEG_SEC = 6.0                # time ceiling (no punctuation safety net)
        MIN_NEXT_CLAUSE = MIN_WORDS      # lookahead: next clause must be this long (words)
        # ─────────────────────────────────────────────────────────────────────

        _ABBREVS = frozenset({
            'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'st', 'vs',
            'etc', 'approx', 'dept', 'gov', 'lt', 'sgt', 'cpl', 'pvt',
            'co', 'corp', 'inc', 'ltd', 'gen', 'col', 'capt', 'maj',
        })

        # Words that OPEN a subordinate clause — never break immediately before them
        _CLAUSE_STARTERS = frozenset({
            'who', 'whom', 'whose', 'which', 'that',
            'when', 'where', 'why', 'how',
            'because', 'although', 'if', 'unless', 'until',
            'while', 'after', 'before', 'since', 'as',
            'what', 'whether',
        })

        # Words that START an independent clause — good break points when buffer is full
        _COORD_CONJUNCTIONS = frozenset({
            'and', 'but', 'or', 'nor', 'so', 'yet', 'for',
        })

        sentence_enders = ('?', '!', '...')
        soft_break_chars = (',', ';', ':')

        # ── main pass ────────────────────────────────────────────────────────
        entries: List[Dict] = []
        buf: List = []          # WordObj items
        buf_chars = 0

        def _flush_buf():
            nonlocal buf, buf_chars
            if not buf:
                return
            text = ' '.join(w.word.strip() for w in buf)
            text = re.sub(r'\s+', ' ', text).strip()
            entries.append({
                'start': self.format_time(buf[0].start),
                'end':   self.format_time(buf[-1].end),
                'text':  text,
            })
            buf = []
            buf_chars = 0

        total = len(words)
        for i, word_obj in enumerate(words):
            text = word_obj.word.strip()
            if not text:
                continue

            buf.append(word_obj)
            buf_chars += len(text) + 1

            is_last = (i == total - 1)

            # peek at next non-empty word
            next_text = ''
            for j in range(i + 1, min(i + 4, total)):
                nt = words[j].word.strip()
                if nt:
                    next_text = nt
                    break

            next_lower = next_text.lower()
            next_is_clause_starter = next_lower in _CLAUSE_STARTERS
            next_is_coord = next_lower in _COORD_CONJUNCTIONS

            # ── decision tree (evaluated top to bottom, first match wins) ──

            if is_last:
                _flush_buf()
                continue

            # 1. Hard sentence end → always break (even before clause starters)
            is_sentence_end = text.endswith(sentence_enders)
            if text.endswith('.') and not is_abbrev_dot(text, next_text, _ABBREVS):
                is_sentence_end = True
            if is_sentence_end:
                _flush_buf()
                continue

            # 2. Hard char ceiling exceeded:
            #    Before flushing, check if a sentence-ender is within 4 words —
            #    if so, defer the flush so we land on a clean boundary instead
            #    of cutting mid-phrase.
            if buf_chars > hard_limit:
                found_end_nearby = False
                for k in range(i + 1, min(i + 5, total)):
                    w = words[k].word.strip()
                    if not w:
                        continue
                    if w.endswith(('.', '?', '!', '...')):
                        found_end_nearby = True
                        break
                    if w.endswith((',', ';', ':')):
                        break
                # Allow up to 20 extra chars to reach a nearby sentence end
                if found_end_nearby and buf_chars < hard_limit + 20:
                    continue
                _flush_buf()
                continue

            # 3. Time ceiling — long silence / run-on speech
            seg_dur = buf[-1].end - buf[0].start
            if seg_dur >= MAX_SEG_SEC and not next_is_clause_starter:
                _flush_buf()
                continue

            # 4. Coordinating conjunction at start of next fragment:
            #    good break if buffer is already substantial
            buf_words = len(buf)
            if next_is_coord and buf_words >= MIN_WORDS and buf_chars >= limit * 0.7:
                _flush_buf()
                continue

            # 5. Soft break (comma/semicolon/colon) after enough content,
            #    AND the next clause is long enough to stand on its own,
            #    AND the next word is NOT a clause starter.
            if (text.endswith(soft_break_chars)
                    and buf_words >= MIN_WORDS
                    and buf_chars >= limit * 0.6
                    and not next_is_clause_starter):
                next_clause_len = peek_next_clause_words(words, i)
                if next_clause_len >= MIN_NEXT_CLAUSE:
                    _flush_buf()
                    continue

        # ── post-pass: orphan prevention ─────────────────────────────────────
        entries = merge_orphan_segments(
            entries,
            hard_limit,
            min_words=max(3, int(getattr(self, 'target_words_per_line', 4) or 4)),
        )

        # ── hallucination suppression + timing fix ───────────────────────────
        entries = self.suppress_hallucinations(entries)
        entries = self.sanitize_entries(entries)

        self.logger.info(
            f"✂️  segment_words_smart: {total} words → {len(entries)} subtitle entries"
        )
        return entries

    def sanitize_entries(self, entries: List[Dict]) -> List[Dict]:
        """Fix overlaps, enforce minimum duration, and semantically split long lines"""
        min_duration = self.min_duration
        max_chars = getattr(self.style_config, 'max_chars', 42)

        if not entries:
            return []

        entries = apply_semantic_splitting(
            entries,
            max_chars=max_chars,
            split_at_best_point_fn=self._split_at_best_point,
        )

        cleaned = normalize_and_fix_timing(
            entries,
            min_duration=min_duration,
            parse_to_sec_fn=self.parse_to_sec,
            format_time_fn=self.format_time,
        )

        deduped = deduplicate_consecutive_entries(cleaned)
        removed_count = len(cleaned) - len(deduped)
        if removed_count > 0:
            self.logger.warning(f"⚠️ Removed {removed_count} duplicate entries (Whisper hallucination suppression)")

        return postprocess_orphans_and_collocations(
            deduped,
            max_chars=max_chars,
            load_collocations_fn=self._load_collocations,
            remove_whisper_artifacts_fn=self._remove_whisper_artifacts,
            clean_bidi_fn=self._clean_bidi,
            fix_persian_text_fn=self.fix_persian_text,
        )


    @staticmethod
    def parse_to_sec(t_str: str) -> float:
        return parse_to_sec(t_str)

    @staticmethod
    def format_time(seconds: float) -> str:
        return format_time(seconds)

    @staticmethod
    def _normalize_digits(text: str) -> str:
        return normalize_digits(text)

    def _merge_split_numbers(self, segments: List[Dict]) -> List[Dict]:
        """
        Heuristic to merge segments that look like split numbers.
        Example: "is 1" + ",500" -> "is 1,500"
        Addresses transcription errors where large numbers are split across lines.
        """
        if not segments: return []
        merged = []
        i = 0
        while i < len(segments):
            curr = segments[i]
            if i + 1 < len(segments):
                next_seg = segments[i+1]
                # Check if current ends with digit and next starts with comma/dot + digit
                text1 = curr['text'].strip()
                text2 = next_seg['text'].strip()
                
                # Check patterns for split numbers (e.g. "1" and ",000")
                if text1 and text1[-1].isdigit() and text2 and (text2.startswith(',') or text2.startswith('.')):
                     # Likely split number
                     # Merge entries: extend time and concatenate text
                     new_seg = curr.copy()
                     new_seg['end'] = next_seg['end']
                     new_seg['text'] = text1 + text2 # Concatenate directly (no space for "1,000")
                     
                     self.logger.info(f"🔄 Smart Merge: '{text1}' + '{text2}' -> '{new_seg['text']}'")
                     merged.append(new_seg)
                     i += 2 # Skip next segment as it's merged
                     continue
            
            merged.append(curr)
            i += 1
        return merged

    def _load_collocations(self) -> set:
        """Load small collocations list from data file into a set of lowercase bigrams."""
        if getattr(self, '_collocations_cache', None) is not None:
            return self._collocations_cache

        # repository layout: lib/python/subtitle -> go up 2 to reach lib
        coll_path = Path(__file__).parent.parent.parent / 'data' / 'collocations_small.txt'
        coll = set()
        try:
            if coll_path.exists():
                with open(coll_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        coll.add(line.lower())
        except Exception:
            pass

        self._collocations_cache = coll
        return coll

    def _find_best_split_point(self, text: str, max_chars: int = 42) -> int:
        """Find the most semantically sound point to split a long line."""
        if len(text) <= max_chars:
            return -1

        # 1. Candidate selection: Look in the middle 60% of the string
        start_idx = int(len(text) * 0.2)
        end_idx = int(len(text) * 0.8)
        
        collocations = self._load_collocations()
        
        candidates = []
        for match in re.finditer(r'\s', text[start_idx:end_idx]):
            pos = start_idx + match.start()
            
            # Base score: Distance from absolute center (lower distance is better)
            center = len(text) / 2
            score = 100 - abs(pos - center)
            
            # --- PUNCTUATION BONUSES ---
            char_before = text[pos-1] if pos > 0 else ""
            if char_before in ('.', '!', '?', '...'): score += 80
            if char_before in (',', '،', ';', ':', '-'): score += 50
            
            # --- COLLOCATION PENALTY ---
            # Don't break common pairs
            words_before = text[:pos].split()
            words_after = text[pos+1:].split()
            if words_before and words_after:
                pair = f"{words_before[-1].lower()} {words_after[0].lower()}"
                if pair in collocations:
                    score -= 150 # Massive penalty
            
            candidates.append((pos, score))
            
        if not candidates:
            return -1
            
        # Return index of highest scoring space
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _split_at_best_point(self, entry: Dict, max_chars: int = 42) -> List[Dict]:
        """Recursively split an entry at its most semantic middle point."""
        text = self._clean_bidi(entry['text'])
        if len(text) <= max_chars:
            return [entry]
            
        split_pos = self._find_best_split_point(text, max_chars)
        if split_pos == -1:
            # Word-boundary-only fallback: never split inside a word.
            # Try nearest spaces around the center, then nearest before max_chars.
            center = len(text) // 2
            left_space = text.rfind(' ', 0, center)
            right_space = text.find(' ', center)

            candidates = [p for p in (left_space, right_space) if p > 0]
            if not candidates:
                split_pos = text.rfind(' ', 0, max_chars)
                if split_pos <= 0:
                    # Single-token text: keep it unsplit rather than breaking characters.
                    return [entry]
            else:
                split_pos = min(candidates, key=lambda p: abs(p - center))
            
        # Time interpolation
        s_sec = self.parse_to_sec(entry['start'])
        e_sec = self.parse_to_sec(entry['end'])
        duration = e_sec - s_sec
        mid_time = s_sec + (duration * (split_pos / len(text)))
        
        part1 = {
            'index': entry.get('index', '0'),
            'start': entry['start'],
            'end': self.format_time(mid_time),
            'text': entry['text'][:split_pos].strip()
        }
        part2 = {
            'index': entry.get('index', '0'),
            'start': self.format_time(mid_time),
            'end': entry['end'],
            'text': entry['text'][split_pos:].strip()
        }
        
        return self._split_at_best_point(part1, max_chars) + self._split_at_best_point(part2, max_chars)

    def _ensure_bert(self):
        """Lazy-load a masked-LM model for lightweight collocation scoring if requested.

        The model is only loaded if AMIR_USE_BERT env var is truthy.
        """
        if getattr(self, '_bert_inited', False):
            return getattr(self, '_bert_available', False)

        self._bert_inited = True
        self._bert_available = False
        # Use instance flags first; fall back to env var for backward compatibility
        use_bert = getattr(self, 'use_bert', False) or (os.environ.get('AMIR_USE_BERT', '0') in ('1','true','True'))
        if not use_bert:
            return False

        try:
            from transformers import AutoTokenizer, AutoModelForMaskedLM
            model_name = getattr(self, 'bert_model', None) or os.environ.get('AMIR_BERT_MODEL', 'bert-base-uncased')
            self._bert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._bert_model = AutoModelForMaskedLM.from_pretrained(model_name)
            self._bert_model.eval()
            self._bert_available = True
        except Exception:
            self._bert_available = False

        return self._bert_available

    def _bert_masked_lm_score(self, phrase: str) -> Optional[float]:
        """Compute a simple pseudo-log-prob score for `phrase` using masked-LM.

        Returns average negative log probability (lower is better). If model unavailable, returns None.
        """
        if not self._ensure_bert():
            return None

        try:
            import torch
            toks = self._bert_tokenizer.tokenize(phrase)
            if not toks:
                return None
            scores = []
            for i, tok in enumerate(toks):
                toks_masked = toks.copy()
                toks_masked[i] = self._bert_tokenizer.mask_token
                inputs = self._bert_tokenizer.convert_tokens_to_ids([self._bert_tokenizer.cls_token] + toks_masked + [self._bert_tokenizer.sep_token])
                input_ids = torch.tensor([inputs])
                with torch.no_grad():
                    outputs = self._bert_model(input_ids)
                    logits = outputs.logits
                # index of original token in vocab
                orig_id = self._bert_tokenizer.convert_tokens_to_ids(tok)
                # masked position index in input_ids
                mask_pos = 1 + i
                logit = logits[0, mask_pos, orig_id].item()
                # convert to negative logit as proxy (higher is better)
                scores.append(-float(logit))
            return sum(scores) / max(1, len(scores))
        except Exception:
            return None

    def _parse_translated_batch_output(self, output: str, expected_count: int, threshold: float = 0.8) -> List[str]:
        return parse_translated_batch_output(
            output=output,
            expected_count=expected_count,
            normalize_digits=self._normalize_digits,
            logger=self.logger,
            threshold=threshold,
        )

    # ==================== TRANSLATION ====================

    def translate_with_deepseek(self, texts: List[str], target_lang: str, source_lang: str = 'en', batch_size: int = 25, original_entries: List[Dict] = None, output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Batched translation with cache and incremental saving"""
        if not texts or target_lang == source_lang:
            return texts
        
        # Delegate to dedicated pipeline
        return run_deepseek_translation_pipeline(
            processor=self,
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang,
            batch_size=batch_size,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations
        )

    def _get_available_gemini_models(self, client) -> List[str]:
        """Fetch and rank available models from Google API with smart filtering"""
        try:
            all_models = list(client.models.list())
            candidates = filter_gemini_generation_models(all_models)
            ranked = sorted(candidates, key=rank_gemini_model_name, reverse=True)
            
            # Fallback hardcoded defaults if API returns nothing (safety net)
            defaults = [
                "models/gemini-2.0-pro-exp-02-05", "models/gemini-2.0-flash", 
                "models/gemini-1.5-pro", "models/gemini-1.5-flash"
            ]
            
            final_list = []
            seen = set()
            for r in ranked:
                if r not in seen:
                    final_list.append(r)
                    seen.add(r)
            for d in defaults:
                if d not in seen:
                    final_list.append(d)
                    seen.add(d)
                    
            return final_list
        except Exception as e:
            self.logger.warning(f"Failed to fetch models dynamically: {e}")
            return [
                "models/gemini-2.0-pro-exp-02-05", "models/gemini-2.0-flash", 
                "models/gemini-1.5-pro", "models/gemini-1.5-flash"
            ]

    def translate_with_gemini(self, texts: List[str], target_lang: str, source_lang: str = 'en', batch_size: int = 40, original_entries: List[Dict] = None, output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Batched translation with MODERN google-genai SDK and DYNAMIC model fallback"""
        if not texts or target_lang == source_lang:
            return texts
        
        # Delegate to dedicated pipeline
        return run_gemini_translation_pipeline(
            processor=self,
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang,
            batch_size=batch_size,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations
        )

    # ==================== LITELLM TRANSLATION (DEBUG/TEST) ====================

    def translate_with_litellm(self, texts: List[str], target_lang: str, source_lang: str = 'en', batch_size: int = 20, original_entries: List[Dict] = None, output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Universal LLM bridge via LiteLLM for debugging and testing"""
        if not texts or target_lang == source_lang:
            return texts
        
        # Delegate to dedicated pipeline
        return run_litellm_translation_pipeline(
            processor=self,
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang,
            batch_size=batch_size,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations
        )

    # ==================== MINIMAX TRANSLATION ====================

    def translate_with_minimax(self, texts: List[str], target_lang: str, source_lang: str = 'en',
                                batch_size: int = 15, original_entries: List[Dict] = None,
                                output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Translate subtitle texts using MiniMax LLM (OpenAI-compatible API)."""
        if not texts or target_lang == source_lang:
            return texts
        
        # Delegate to dedicated pipeline
        return run_minimax_translation_pipeline(
            processor=self,
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang,
            batch_size=batch_size,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations
        )

    # ==================== GROK TRANSLATION ====================

    def translate_with_grok(self, texts: List[str], target_lang: str, source_lang: str = 'en',
                             batch_size: int = 20, original_entries: List[Dict] = None,
                             output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Translation via Grok API (xAI - grok-4-1-fast-reasoning) with DeepSeek fallback"""
        if not self.grok_api_key:
            self.logger.warning("GROK_API_KEY not found. Falling back to DeepSeek.")
            return self.translate_with_deepseek(texts, target_lang, source_lang, 25, original_entries, output_srt, existing_translations)

        client = OpenAI(api_key=self.grok_api_key, base_url="https://api.x.ai/v1")
        model_name = "grok-4-1-fast-reasoning"

        indices = list(range(len(texts)))
        final_result = [None] * len(texts)

        if existing_translations:
            for idx, txt in existing_translations.items():
                if 0 <= idx < len(final_result) and txt and txt.strip():
                    final_result[idx] = txt

        indices_to_translate = [i for i in indices if final_result[i] is None]
        if not indices_to_translate:
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

        batch_indices_list = self._create_balanced_batches(indices_to_translate, texts, batch_size)
        batch_count = len(batch_indices_list)
        pbar = tqdm(total=len(indices_to_translate), unit="item", desc=f"  Groq-Translating ({target_lang.upper()})")

        for i, batch_indices in enumerate(batch_indices_list):
            batch = [texts[idx] for idx in batch_indices]

            first_abs = batch_indices[0]
            last_abs  = batch_indices[-1]
            ctx_before = texts[max(0, first_abs - 3): first_abs]
            ctx_after  = texts[last_abs + 1: last_abs + 4]
            ctx_section = ""
            if ctx_before or ctx_after:
                parts = []
                if ctx_before:
                    parts.append("Previous lines (context only, do NOT translate):\n" +
                                 "\n".join(f"  • {t}" for t in ctx_before))
                if ctx_after:
                    parts.append("Following lines (context only, do NOT translate):\n" +
                                 "\n".join(f"  • {t}" for t in ctx_after))
                ctx_section = "\n".join(parts) + "\n\nLines to translate:\n"

            batch_text = ctx_section + "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})

            max_retries = 5
            success_batch = False
            last_error_msg = ""

            for attempt in range(1, max_retries + 1):
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=self.temperature,
                        max_tokens=2000
                    )
                    output = response.choices[0].message.content.strip()
                    trans_list = self._parse_translated_batch_output(output, len(batch))

                    if None in trans_list:
                        trans_list = [trans_list[j] if trans_list[j] is not None else batch[j] for j in range(len(trans_list))]

                    if target_lang == 'fa':
                        processed_list = []
                        for t in trans_list:
                            if not t or not t.strip():
                                processed_list.append(t)
                            elif not any('\u0600' <= c <= '\u06FF' for c in t):
                                processed_list.append(t)
                            else:
                                processed_list.append(self.fix_persian_text(self.strip_english_echo(t)))
                        trans_list = processed_list

                    if len(trans_list) >= len(batch):
                        for rel_idx, trans in enumerate(trans_list[:len(batch)]):
                            final_result[batch_indices[rel_idx]] = trans

                        if output_srt and original_entries:
                            tgt_entries_live = original_entries[:]
                            for k, v in enumerate(final_result):
                                if v is not None and k < len(tgt_entries_live):
                                    tgt_entries_live[k] = {**tgt_entries_live[k], 'text': v}
                            with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                for idx2, entry in enumerate(tgt_entries_live, 1):
                                    f.write(f"{idx2}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

                        pbar.update(len(batch))
                        success_batch = True
                        time.sleep(0.2)
                        break
                    else:
                        delay = min(20 + attempt * 5, 120)
                        self.logger.warning(f"⚠️ Grok batch {i+1} incomplete: got {len(trans_list)}/{len(batch)}. Retrying in {delay}s...")
                        time.sleep(delay)

                except Exception as e:
                    last_error_msg = f"{type(e).__name__}: {str(e)}"
                    if "401" in last_error_msg or "Invalid API Key" in last_error_msg:
                        raise
                    delay = min(20 + attempt * 5, 120)
                    self.logger.warning(f"Grok batch {i+1} attempt {attempt}/{max_retries} failed: {last_error_msg}")
                    time.sleep(delay)

            if not success_batch:
                self.logger.warning(f"⚠️ Grok batch {i+1} failed ({last_error_msg}). Falling back to DeepSeek...")
                try:
                    ds_texts = batch
                    ds_result = self.translate_with_deepseek(ds_texts, target_lang, source_lang, len(ds_texts))
                    for rel_idx, trans in enumerate(ds_result[:len(batch)]):
                        final_result[batch_indices[rel_idx]] = trans
                    pbar.update(len(batch))
                except Exception as de:
                    pbar.close()
                    raise RuntimeError(f"Grok+DeepSeek both failed on batch {i+1}: {de}")

        pbar.close()
        return final_result

    def get_translation_prompt(self, target_lang: str) -> str:
        """Universal translation prompt with structural constraints"""
        lang_config = get_language_config(target_lang)
        lang_name = lang_config.name
        
        # Special handling for Persian (informal tone)
        if target_lang == 'fa':
            return (
                f"You are a professional {lang_name} subtitle translator.\n"
                "SYSTEM: Tehrani informal tone.\n"
                "FORMAT: Return ONLY a valid JSON object where keys are the input line numbers and values are the translations.\n"
                "EXAMPLE: {\"1\": \"سلام\", \"2\": \"چطوری؟\"}\n"
                f"RULE: For ACRONYMS ONLY (API, AGI, CapEx), write the {lang_name} translation first, then the English acronym in parentheses. "
                "For ALL other words, translate directly into Persian WITHOUT any English in parentheses.\n"
                "CRITICAL 1: You MUST translate EACH numbered item independently. The output JSON must have the EXACT SAME NUMBER of keys as the input items.\n"
                "CRITICAL 2: Each item is a RAW SUBTITLE SEGMENT — it may be an incomplete sentence fragment that continues from the previous line or continues into the next. "
                "Translate ONLY the exact words given. Do NOT complete the thought. Do NOT add words from context. Do NOT summarize multiple items into one.\n"
                "CRITICAL 3: The translation for line N MUST cover the SAME semantic content as the input for line N — nothing more, nothing less. "
                "If the input is short (e.g. 'guy but it almost'), the translation must also be short and faithful.\n"
                "CRITICAL 4: NEVER echo or repeat the original English source text in your output.\n"
                "CRITICAL 5: NEVER put English words inside parentheses as clarification. "
                "Do NOT write things like 'اطلاعاتی (intelligence)' — just write 'اطلاعاتی'. "
                "If a fragment seems incomplete, translate what is given faithfully without annotation.\n"
                "NO commentary, NO extra text."
            )

        # Generic prompt for other languages
        return (
            f"You are a professional {lang_name} subtitle translator.\n"
            "FORMAT: Return ONLY a valid JSON object where keys are the input line numbers and values are the translations.\n"
            "EXAMPLE: {\"1\": \"Hello\", \"2\": \"How are you?\"}\n"
            "CRITICAL 1: You MUST translate EACH line strictly independently. Do NOT merge two lines into one key. The output JSON must have the EXACT SAME NUMBER of keys as the input TARGET LINES, with NO skipped numbers.\n"
            "CRITICAL 2: Each item is a RAW SUBTITLE SEGMENT and may be an incomplete sentence fragment. "
            "Translate ONLY the exact words given — do NOT complete the thought or add words from surrounding context.\n"
            "CRITICAL 3: The translation for line N MUST correspond EXACTLY to the English text in line N. Do NOT shift translations up or down keys.\n"
            "CRITICAL 4: NEVER add parenthetical clarifications with English words. Translate directly without annotation.\n"
            "NO commentary, NO extra text."
        )

    @staticmethod
    def fix_persian_text(text: str) -> str:
        return fix_persian_text(text)

    @staticmethod
    def strip_english_echo(text: str) -> str:
        return strip_english_echo(text)

    @staticmethod
    def _clean_bidi(t: str) -> str:
        return clean_bidi(t)

    def translate_single_with_context(self, text: str, prev_lines: List[str], next_lines: List[str], target_lang: str, source_lang: str) -> str:
        """Translate a single line with context context to avoid literal translation issues"""
        if not text or not text.strip():
            return text
            
        context_prompt = ""
        if prev_lines:
            context_prompt += "Previous context:\n" + "\n".join([f"- {l}" for l in prev_lines]) + "\n"
        
        context_prompt += f"\n>>> TARGET LINE TO TRANSLATE ({source_lang.upper()} -> {target_lang.upper()}):\n{text}\n"
        
        if next_lines:
            context_prompt += "\nNext context:\n" + "\n".join([f"- {l}" for l in next_lines])
            
        lang_config = get_language_config(target_lang)
        lang_name = lang_config.name
        
        system_prompt = (
            f"You are a professional {lang_name} subtitle translator.\n"
            "Translate the 'TARGET LINE' using the provided context for flow and tone.\n"
            "RULES:\n"
            "1. Output ONLY the translation of the 'TARGET LINE'.\n"
            "2. Do NOT translate context lines.\n"
            "3. Do NOT add notes, explanations, or quotes.\n"
            "4. Match the tone of the context.\n"
        )
        
        if target_lang == 'fa':
            system_prompt += "5. Use informal/conversational Persian (Tehrani dialect).\n"
            system_prompt += "6. For technical terms, place the English term in parentheses AFTER the Persian translation (e.g. 'هزینه‌ها (CapEx)').\n"
        
        # Select Provider
        try:
            val = None
            if HAS_GEMINI and self.google_api_key and self.llm_choice == "gemini":
                from google import genai
                client = genai.Client(api_key=self.google_api_key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash", # Fast model for single lines
                    contents=f"{system_prompt}\n\n{context_prompt}"
                )
                val = response.text.strip()
                
            elif HAS_LITELLM and self.llm_choice == "litellm":
                from litellm import completion
                model_name = self.custom_model or "gpt-4o-mini"
                response = completion(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context_prompt}
                    ]
                )
                val = response.choices[0].message.content.strip()
                
            else:
                # Default DeepSeek
                client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context_prompt}
                    ],
                    temperature=0.3
                )
                val = response.choices[0].message.content.strip()

            # Clean up
            if target_lang == 'fa' and val:
                val = self.fix_persian_text(val)
                
            return val
            
        except Exception as e:
            self.logger.error(f"Single line translation failed: {e}")
            return None

    # ==================== ASS CREATION ====================

    def create_ass_with_font(self, srt_path: str, ass_path: str, lang: str, secondary_srt: Optional[str] = None, time_offset: float = 0.0, video_width: int = 0, video_height: int = 0, top_raise_px: int = 0, bottom_raise_px: int = 0):
        """Generate ASS file"""
        title = f"{get_language_config(lang).name} + {get_language_config('fa').name}" if secondary_srt else get_language_config(lang).name
        self.logger.info(f"Generating ASS asset ({title})...")

        style = self.style_config

        layout = compute_ass_layout(
            style=style,
            lang=lang,
            secondary_srt=secondary_srt,
            video_width=video_width,
            video_height=video_height,
            en_font_scale=getattr(self, 'en_font_scale', 1.0),
            fa_font_scale=getattr(self, 'fa_font_scale', 1.0),
            fa_font_name=getattr(self, 'fa_font_name', 'Vazirmatn'),
            top_raise_px=top_raise_px,
            bottom_raise_px=bottom_raise_px,
        )
        styles_block = build_ass_styles(
            style=style,
            secondary_srt=secondary_srt,
            fa_style=layout['fa_style'],
            margin_h=layout['margin_h'],
            fa_margin_v=layout['fa_margin_v'],
            top_margin_v=layout['top_margin_v'],
        )
        header = build_ass_header(styles_block, secondary_srt)

        secondary_map = {}
        if secondary_srt and os.path.exists(secondary_srt):
            sec = self.parse_srt(secondary_srt)
            secondary_map = build_secondary_map(sec)

        entries = self.parse_srt(srt_path)

        events = build_ass_events(
            entries=entries,
            secondary_map=secondary_map,
            lang=lang,
            style=style,
            is_portrait=layout['is_portrait'],
            secondary_srt=secondary_srt,
            time_offset=time_offset,
            clean_bidi_fn=SubtitleProcessor._clean_bidi,
            fix_persian_text_fn=self.fix_persian_text,
            max_lines=getattr(self.style_config, 'max_lines', 1),
        )

        with open(ass_path, 'w', encoding='utf-8') as f:
            # Add BOM for good measure
            f.write('\ufeff' + header + "\n".join(events))

        self.logger.info(f"ASS asset generation complete: {Path(ass_path).name}")

    @staticmethod
    def _to_persian_digits(value) -> str:
        return to_persian_digits(value)

    @staticmethod
    def _srt_duration_str(entries: List[Dict], lang: str = 'fa') -> str:
        return srt_duration_str(entries, lang=lang)

    @staticmethod
    def _format_total_seconds(total_sec: float, lang: str = 'fa') -> str:
        return format_total_seconds(total_sec, lang=lang)

    def parse_srt(self, srt_path: str) -> List[Dict]:
        return parse_srt_file(srt_path)

    def validate_srt(self, srt_path: str, expected_count: int, target_lang: str = 'fa') -> bool:
        return validate_srt_file(
            srt_path=srt_path,
            expected_count=expected_count,
            target_lang=target_lang,
            has_target_language_chars_fn=has_target_language_chars,
            logger=self.logger,
        )

    # ==================== MAIN WORKFLOW (FIXED) ====================

    def cleanup(self):
        """Force-unloading model and freeing system memory"""
        # Unload model if held in main process
        if hasattr(self, '_model') and self._model is not None:
            self.logger.info("♻️ Force-unloading model to reclaim memory...")
            self._model = None

        # Metal / MLX cache
        if HAS_MLX:
            try:
                import mlx.core as mx
                mx.clear_cache()
            except Exception:
                pass

        # CUDA cache
        if HAS_TORCH:
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        # Python GC
        gc.collect()
            
    def _ingest_partial_srt(self, source_entries: List[Dict], target_srt_path: str, target_lang: str):
        """Recover existing translations from a partial SRT file to avoid re-translation costs"""
        recovered = {}
        if not os.path.exists(target_srt_path):
            return recovered

        try:
            partial_entries = self.parse_srt(target_srt_path)
            recovered_count = 0
            
            # HALLUCINATION FILTER: Pre-calculate text counts to detect repetitions
            counts = {}
            for e in partial_entries:
                t = e['text'].strip()
                if t: counts[t] = counts.get(t, 0) + 1
            
            # Identify texts that repeat too much (more than 5% of file or > 5 times for long strings)
            hallucinated_texts = set()
            for t, c in counts.items():
                if len(t) > 10 and c > max(5, len(partial_entries) * 0.05):
                    hallucinated_texts.add(t)
            
            if hallucinated_texts:
                self.logger.debug(f"ℹ️ Smart Resume: Skipping {len(hallucinated_texts)} unique hallucinated strings during ingestion.")

            # Map ACTUAL SRT index to text for faster lookup
            partial_map = {e['index']: e['text'] for e in partial_entries}

            for i, src_entry in enumerate(source_entries):
                partial_text = partial_map.get(src_entry['index'])
                if not partial_text:
                    continue

                # Check if it's actually translated and NOT a hallucination
                is_translated = False
                if target_lang == 'fa':
                    # Has Persian chars and is NOT in hallucinated set
                    if partial_text.strip() not in hallucinated_texts and has_target_language_chars(partial_text, target_lang):
                        is_translated = True
                else:
                    # General case: If it's different from source, not empty, and not hallucination
                    if partial_text.strip() not in hallucinated_texts and partial_text.strip() != src_entry['text'].strip() and len(partial_text) > 0:
                        is_translated = True

                if is_translated:
                    # Save recovered by zero-based index
                    recovered[i] = partial_text
                    recovered_count += 1
            
            if recovered_count > 0:
                self.logger.info(f"💰 Smart Resume: Recovered {recovered_count} existing translations from '{Path(target_srt_path).name}'. Saving costs!")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not ingest partial SRT for resume: {e}")

        return recovered
        

    def run_workflow(
        self,
        video_path: str,
        source_lang: str,
        target_langs: List[str] = None,
        render: bool = False,
        force: bool = False,
        correct: bool = False,
        detect_speakers: bool = False,
        limit_start: Optional[float] = None,
        limit_end: Optional[float] = None,
        platforms: Optional[List[str]] = None,
        post_only: bool = False,
        prompt_file: Optional[str] = None,
        post_langs: Optional[List[str]] = None,
        save_formats: Optional[List[str]] = None,
        render_resolution: Optional[int] = None,
        render_quality: Optional[int] = None,
        render_fps: Optional[int] = None,
        render_split_mb: Optional[int] = None,
        pad_bottom: int = 0,
        subtitle_raise_top_px: int = 0,
        subtitle_raise_bottom_px: int = 0,
        use_vad: bool = True,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Complete workflow with fixed path handling and memory management"""
        self.use_vad = use_vad

        def _emit_progress(pct: int, msg: str):
            """Emit a structured progress line parseable by consumers (e.g. su6i_yar.py)."""
            self.logger.info(f"PROGRESS:{pct}:{msg}")
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        ctx = resolve_workflow_base(
            self,
            video_path=video_path,
            source_lang=source_lang,
            target_langs=target_langs,
            post_only=post_only,
            render_resolution=render_resolution,
        )
        video_path = ctx["video_path"]
        source_lang = ctx["source_lang"]
        target_langs = ctx["target_langs"]
        _source_auto_requested = ctx["source_auto_requested"]
        _is_srt_input = ctx["is_srt_input"]
        original_base = ctx["original_base"]
        original_dir = ctx["original_dir"]
        original_stem = ctx["original_stem"]
        lock_key = ctx["lock_key"]

        self.logger.info(f"Processing sequence initiated: {Path(video_path).name}")
        
        result = {}
        temp_vid = None
        workflow_lock_path = None
        global_slot_path = None
        
        def _migrate_legacy_resolution_srt(lang_code: str, expected_path: str) -> bool:
            return migrate_legacy_resolution_srt(
                self,
                original_base=original_base,
                original_dir=original_dir,
                lang_code=lang_code,
                expected_path=expected_path,
            )

        _vw, _vh = detect_subtitle_geometry(self, video_path=video_path, target_langs=target_langs)
        
        try:
            # Optional global throttling across all videos to avoid RAM spikes.
            global_slot_path = self._acquire_global_workflow_slot(video_path)

            # Prevent accidental concurrent processing of the same source
            # across multiple terminals.
            workflow_lock_path = self._acquire_workflow_lock(lock_key, video_path)

            runtime_ctx = prepare_runtime_execution(
                self,
                video_path=video_path,
                source_lang=source_lang,
                target_langs=target_langs,
                original_stem=original_stem,
                original_base=original_base,
                is_srt_input=_is_srt_input,
                source_auto_requested=_source_auto_requested,
                post_only=post_only,
                platforms=platforms,
                prompt_file=prompt_file,
                post_langs=post_langs,
                limit_start=limit_start,
                limit_end=limit_end,
            )
            if runtime_ctx["post_only_done"]:
                return {}

            current_video_input = runtime_ctx["current_video_input"]
            temp_vid = runtime_ctx["temp_vid"]
            _limit_start = runtime_ctx["limit_start"]
            _has_limit = runtime_ctx["has_limit"]
            source_lang = runtime_ctx["source_lang"]
            target_langs = runtime_ctx["target_langs"]
            
            # 1. Source SRT preparation (reuse/transcribe + sanitize/merge)
            src_srt = prepare_source_srt(
                self,
                result=result,
                original_base=original_base,
                source_lang=source_lang,
                force=force,
                current_video_input=current_video_input,
                limit_start=_limit_start,
                limit_end=limit_end,
                correct=correct,
                detect_speakers=detect_speakers,
                has_limit=_has_limit,
                is_srt_input=_is_srt_input,
                migrate_legacy_resolution_srt_fn=_migrate_legacy_resolution_srt,
                emit_progress=_emit_progress,
            )
            
            # 2. Translation
            run_translation_stage(
                self,
                result=result,
                source_lang=source_lang,
                target_langs=target_langs,
                src_srt=src_srt,
                original_base=original_base,
                force=force,
                emit_progress=_emit_progress,
                migrate_legacy_resolution_srt_fn=_migrate_legacy_resolution_srt,
            )
            
            # POST-TRANSLATION VALIDATION: Ensure 100% translation before proceeding
            validate_and_retry_translations(
                self,
                source_lang=source_lang,
                target_langs=target_langs,
                result=result,
                src_srt=src_srt,
            )
            
            # Final Save with structural and BiDi check BEFORE rendering
            apply_final_target_text_fixes(
                self,
                source_lang=source_lang,
                target_langs=target_langs,
                result=result,
            )
            
            # 3. RENDERING (skip when input is SRT-only — no video source available)
            if render and not _is_srt_input:
                _render_ok = run_rendering_stage(
                    self,
                    result=result,
                    source_lang=source_lang,
                    target_langs=target_langs,
                    src_srt=src_srt,
                    original_base=original_base,
                    current_video_input=current_video_input,
                    force=force,
                    limit_start=_limit_start,
                    video_width=_vw or 0,
                    video_height=_vh or 0,
                    render_resolution=render_resolution,
                    render_quality=render_quality,
                    render_fps=render_fps,
                    render_split_mb=render_split_mb,
                    pad_bottom=pad_bottom,
                    subtitle_raise_top_px=subtitle_raise_top_px,
                    subtitle_raise_bottom_px=subtitle_raise_bottom_px,
                    emit_progress=_emit_progress,
                    detect_best_hw_encoder_fn=detect_best_hw_encoder,
                    get_default_quality_fn=get_default_quality,
                )
                if not _render_ok:
                    return None

            run_finalize_stage(
                self,
                result=result,
                original_base=original_base,
                original_stem=original_stem,
                original_dir=original_dir,
                source_lang=source_lang,
                target_langs=target_langs,
                platforms=platforms,
                prompt_file=prompt_file,
                post_langs=post_langs,
                save_formats=save_formats,
            )

            self.logger.info("Execution sequence finalized.")
            return result
        
        except Exception as e:
            self.logger.error(f"❌ Failed: {e}")
            raise
        
        finally:
            self._release_workflow_lock(workflow_lock_path)
            self._release_global_workflow_slot(global_slot_path)
            if temp_vid and os.path.exists(temp_vid):
                try:
                    os.remove(temp_vid)
                except:
                    pass


    # ==================== SOCIAL MEDIA POST GENERATION ====================
    # To add a new platform (YouTube, LinkedIn, Instagram, …):
    #   1. Add a new branch in _get_post_prompt() with the platform key.
    #   2. Pass that key in the `platforms` list when calling generate_posts().
    #   That's it — no other changes needed.

    # Language names are resolved via get_language_config(lang).name — no hardcoded dicts needed.

    def _get_post_prompt(self, platform: str, title: str, srt_lang_name: str, full_text: str,
                          prompt_file: Optional[str] = None, srt_lang: str = 'fa',
                          duration: str = '', all_srt_langs: Optional[List[str]] = None,
                          source_lang: str = ''):
        return get_post_prompt(
            self,
            platform=platform,
            title=title,
            srt_lang_name=srt_lang_name,
            full_text=full_text,
            prompt_file=prompt_file,
            srt_lang=srt_lang,
            duration=duration,
            all_srt_langs=all_srt_langs,
            source_lang=source_lang,
        )

    def _call_llm_for_post(self, system: str, user: str) -> Optional[str]:
        return call_llm_for_post(
            self,
            system=system,
            user=user,
            has_gemini=HAS_GEMINI,
            genai_module=genai if HAS_GEMINI else None,
        )

    @staticmethod
    def _sanitize_post(text: str, platform: str) -> str:
        return sanitize_post(text, platform)

    @staticmethod
    def _telegram_sections_complete(text: str) -> tuple:
        return telegram_sections_complete(text)

    @staticmethod
    def _format_publish_date(value: str) -> str:
        return format_publish_date(value)

    def _discover_video_metadata(self, original_base: str, srt_path: Optional[str] = None) -> Dict[str, str]:
        return discover_video_metadata(self, original_base, srt_path)

    @staticmethod
    def _compose_post_file_header(platform: str, metadata: Dict[str, str], fallback_title: str) -> str:
        return compose_post_file_header(platform, metadata, fallback_title)

    def generate_posts(
        self,
        original_base: str,
        source_lang: str,
        result: Dict[str, Any],
        platforms: Optional[List[str]] = None,
        prompt_file: Optional[str] = None,
        post_langs: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Generate social media posts for the requested SRT languages × every platform.

        By default only a Persian (FA) post is generated.  Pass ``post_langs``
        to include additional languages.

        Output filenames:  ``{original_base}_{srt_lang}_{platform}.txt``
        Example:           ``KI_video_fa_telegram.txt``, ``KI_video_de_telegram.txt``

        Args:
            original_base: Dir + stem without language suffix.
            source_lang:   Audio language code.
            result:        Dict[lang → srt_path] from run_workflow.  May be empty
                           when called in ``--post-only`` mode (paths discovered
                           from disk in that case).
            platforms:     Platform keys to generate for. Default: ``['telegram']``.
            post_langs:    SRT language codes to write posts for.
                           Default ``None`` → only ``['fa']``.
                           Pass e.g. ``['fa', 'de']`` to include German as well.

        Returns:
            Dict mapping ``'{lang}_{platform}'`` → saved ``.txt`` path.
        """
        return run_generate_posts(
            self,
            original_base=original_base,
            source_lang=source_lang,
            result=result,
            platforms=platforms,
            prompt_file=prompt_file,
            post_langs=post_langs,
        )

    def generate_telegram_post(self, original_base, source_lang, result):
        """Deprecated — use generate_posts() directly. Kept for backward compatibility."""
        return self.generate_posts(original_base, source_lang, result, platforms=['telegram'])

    # ==================== BATCH FALLBACK CHAIN ====================

    def translate_batch_single_attempt(
        self,
        batch: List[str],
        target_lang: str,
        source_lang: str = 'en',
        model_name: str = "deepseek",
        batch_size: int = 25,
        max_retries: int = 2
    ) -> List[str]:
        return run_translate_batch_single_attempt(
            self,
            batch=batch,
            target_lang=target_lang,
            source_lang=source_lang,
            model_name=model_name,
            batch_size=batch_size,
            max_retries=max_retries,
            has_gemini=HAS_GEMINI,
        )

    # ==================== TRANSLATE-THEN-RESEGMENT ====================
    # Industry-standard approach: translate full sentences, then re-segment
    # back onto original timecodes using character-proportional splitting.

    @staticmethod
    def _group_entries_into_paragraphs(entries: List[Dict]) -> List[List[int]]:
        return group_entries_into_paragraphs(entries)

    @staticmethod
    def _take_words_up_to(words: List[str], target_chars: int) -> tuple:
        return take_words_up_to(words, target_chars)

    @staticmethod
    def _take_n_words_with_punct_snap(words: List[str], target_n: int, min_n: int, max_n: int = None) -> tuple:
        return take_n_words_with_punct_snap(words, target_n, min_n, max_n)

    @staticmethod
    def _vis_len(s: str) -> int:
        return vis_len(s)

    def _resegment_translation(
        self,
        entries: List[Dict],
        paragraph_groups: List[List[int]],
        translated_paragraphs: List[str]
    ) -> List[str]:
        return resegment_translation(
            entries=entries,
            paragraph_groups=paragraph_groups,
            translated_paragraphs=translated_paragraphs,
            slot_max_chars=self.style_config.max_chars,
            vis_len=self._vis_len,
        )

    def translate_with_batch_fallback_chain(
        self,
        texts: List[str],
        target_lang: str,
        source_lang: str = 'en',
        original_entries: List[Dict] = None,
        output_srt: str = None,
        existing_translations: Dict[int, str] = None
    ) -> List[str]:
        return run_translate_with_batch_fallback_chain(
            self,
            texts=texts,
            target_lang=target_lang,
            source_lang=source_lang,
            original_entries=original_entries,
            output_srt=output_srt,
            existing_translations=existing_translations,
        )



# ==================== HELPER ====================

def create_processor(**kwargs) -> SubtitleProcessor:
    """
    Create processor with configurable options
    
    Args:
        api_key: DeepSeek API key
        model_size: Whisper model size (base, small, medium, large-v3)
        style: SubtitleStyle enum
        max_lines: Maximum subtitle lines
        fail_on_translation_error: If True, raise exception on translation failure (default: True)
                                   If False, skip failed translations and continue
    
    Example:
        # Strict mode (default): Stop on any error
        processor = create_processor(fail_on_translation_error=True)
        
        # Lenient mode: Skip failed translations
        processor = create_processor(fail_on_translation_error=False)
    """
    return SubtitleProcessor(**kwargs)


if __name__ == "__main__":
    print("✅ Complete Working Subtitle Processor")
    print("All features implemented and ready to use!")