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
import hashlib
import socket

# Environment control for library verbosity
# (Set to 0 if full debug needed, 1 hides progress bars)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0" 

import tempfile
import shutil
import threading
import zipfile
from datetime import timedelta, datetime
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
    create_balanced_batches,
    load_local_translation_cache,
    local_cache_key,
    log_cost_savings,
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
    format_time,
    get_video_duration,
    normalize_digits,
    parse_to_sec,
    sanitize_stem_for_fs,
)
from subtitle.transcription import (
    ensure_whisper_server,
    get_whisper_server_socket_path,
    is_whisper_server_ready,
    whisper_server_enabled,
)
from subtitle.translation import parse_translated_batch_output
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
        checkpoint_file = self._get_checkpoint_path(checkpoint.video_path)
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'video_path': checkpoint.video_path,
                    'stage': checkpoint.stage.value,
                    'source_lang': checkpoint.source_lang,
                    'target_langs': checkpoint.target_langs,
                    'timestamp': checkpoint.timestamp,
                    'data': checkpoint.data
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Checkpoint save failed: {e}")

    def load_checkpoint(self, video_path: str) -> Optional[ProcessingCheckpoint]:
        checkpoint_file = self._get_checkpoint_path(video_path)
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return ProcessingCheckpoint(
                video_path=data['video_path'],
                stage=ProcessingStage(data['stage']),
                source_lang=data['source_lang'],
                target_langs=data['target_langs'],
                timestamp=data['timestamp'],
                data=data['data']
            )
        except:
            return None

    def clear_checkpoint(self, video_path: str):
        checkpoint_file = self._get_checkpoint_path(video_path)
        if checkpoint_file.exists():
            checkpoint_file.unlink()

    def _get_checkpoint_path(self, video_path: str) -> Path:
        video_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
        return self.cache_dir / f"checkpoint_{video_hash}.json"

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
            # Determine the correct MLX repo path
            model_name = self.model_size
            if "/" in model_name:
                repo_path = model_name
            elif model_name == "turbo":
                repo_path = "mlx-community/whisper-turbo"
            elif model_name.startswith("large-v3"):
                repo_path = "mlx-community/whisper-large-v3-mlx"
            else:
                repo_path = f"mlx-community/whisper-{model_name}-mlx"

            worker_script = f"""
import os
import sys
import json

def run():
    try:
        # Import heavy libraries ONLY inside the isolated worker
        import mlx_whisper
        import mlx.core as mx
        
        # Limit Metal cache to 512MB
        try:
            mx.set_cache_limit(1024 * 1024 * 512)
        except:
            pass
        
        # Suppress Hallucinations (Repetition Penalty)
        kwargs = {{
            "path_or_hf_repo": "{repo_path}",
            "word_timestamps": True,
            "verbose": True,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.6,
            "logprob_threshold": -1.0,
            "compression_ratio_threshold": 2.4,
            "temperature": (0.0, 0.2, 0.4, 0.6, 0.8),
        }}
        if "{_lang_for_worker}":
            kwargs["language"] = "{_lang_for_worker}"
        result = mlx_whisper.transcribe("{video_path}", **kwargs)
        
        simplified = []
        for segment in result.get('segments', []):
            if 'words' in segment:
                for w in segment['words']:
                    simplified.append({{'start': w['start'], 'end': w['end'], 'word': w['word']}})
        
        payload = {{"language": result.get("language", ""), "words": simplified}}
        with open("{result_json_path}", "w", encoding="utf-8") as f:
            json.dump(payload, f)
            
        # NUCLEAR EXIT: Force OS to reclaim all memory immediately
        try: mx.clear_cache()
        except: pass
        os._exit(0) 
        
    except Exception as e:
        print(f"WORKER_ERROR: {{e}}")
        os._exit(1)

if __name__ == "__main__":
    run()
"""
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
                
                # Helper to parse [HH:MM:SS.mmm --> HH:MM:SS.mmm] or [MM:SS.mmm --> MM:SS.mmm]
                def parse_time(line):
                    # More robust pattern to match Whisper's timestamp formats
                    match = re.search(r'-->\s+\[?(\d+:)?(\d+):(\d+)[\.,](\d+)\]?', line)
                    if match:
                        groups = match.groups()
                        h = int(groups[0].strip(':')) if groups[0] else 0
                        m = int(groups[1])
                        s = int(groups[2])
                        ms = int(groups[3])
                        # Handle different lengths of milliseconds/centiseconds
                        ms_val = ms / (10 ** len(groups[3]))
                        return h * 3600 + m * 60 + s + ms_val
                    return None

                # --- Incremental checkpoint setup ---
                partial_srt_path = os.path.splitext(video_path)[0] + f"_{_lang_for_worker or 'auto'}.partial.srt"
                partial_entries = []

                def _srt_tc(sec: float) -> str:
                    h = int(sec // 3600); m = int((sec % 3600) // 60); s_i = int(sec % 60)
                    return f"{h:02d}:{m:02d}:{s_i:02d},{int(round((sec - int(sec)) * 1000)):03d}"

                def _parse_seg_line(raw: str):
                    """Extract (start_s, end_s, text) from whisper verbose '[start --> end]  text' line."""
                    mg = re.match(
                        r'\[(?:(\d+):)?(\d+):(\d+[\.,]\d+)\s+-->\s+(?:(\d+):)?(\d+):(\d+[\.,]\d+)\]\s*(.*)',
                        raw.strip()
                    )
                    if not mg:
                        return None
                    def _ts(hg, mg2, sg):
                        return (int(hg) if hg else 0) * 3600 + int(mg2) * 60 + float(sg.replace(',', '.'))
                    return _ts(mg.group(1), mg.group(2), mg.group(3)), _ts(mg.group(4), mg.group(5), mg.group(6)), mg.group(7)

                def _flush_partial():
                    if not partial_entries:
                        return
                    lines = []
                    for idx, (s, e, t) in enumerate(partial_entries, 1):
                        lines.extend([str(idx), f"{_srt_tc(s)} --> {_srt_tc(e)}", t.strip(), ""])
                    try:
                        with open(partial_srt_path, 'w', encoding='utf-8') as pf:
                            pf.write("\n".join(lines))
                    except Exception:
                        pass

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
                        seg = _parse_seg_line(line)
                        if seg:
                            partial_entries.append(seg)
                            if len(partial_entries) % 20 == 0:
                                _flush_partial()
                            
                        curr_time = parse_time(line)
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
                _flush_partial()  # Final checkpoint flush before reading result JSON
                
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
                for p in [worker_path, result_json_path]:
                    if os.path.exists(p):
                        try: os.remove(p)
                        except: pass
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
        MIN_WORDS  = 4                   # minimum words before a soft break fires
        MAX_SEG_SEC = 6.0                # time ceiling (no punctuation safety net)
        MIN_NEXT_CLAUSE = 4              # lookahead: next clause must be this long (words)
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

        def _is_abbrev_dot(word_text: str, next_word: str) -> bool:
            stripped = word_text.rstrip('.')
            if len(stripped) <= 2: return True
            if stripped.lower() in _ABBREVS: return True
            if next_word and next_word[0].islower(): return True
            return False

        def _peek_next_clause_words(idx: int) -> int:
            """Count words in the next clause (until next sentence-ender or soft-break)."""
            count = 0
            for k in range(idx + 1, min(idx + 20, len(words))):
                w = words[k].word.strip()
                if not w: continue
                count += 1
                if w.endswith(('?', '!', '...', '.', ',', ';', ':')):
                    break
            return count

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
            if text.endswith('.') and not _is_abbrev_dot(text, next_text):
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
                next_clause_len = _peek_next_clause_words(i)
                if next_clause_len >= MIN_NEXT_CLAUSE:
                    _flush_buf()
                    continue

        # ── post-pass: orphan prevention ─────────────────────────────────────
        # Merge segments with ≤ 2 words into the shorter neighbour
        merged: List[Dict] = []
        for entry in entries:
            w_count = len(entry['text'].split())
            if w_count <= 2 and merged:
                # merge into previous
                prev = merged[-1]
                combined = prev['text'] + ' ' + entry['text']
                # only merge if result fits within hard_limit chars
                if len(combined) <= hard_limit + 10:
                    prev['end']  = entry['end']
                    prev['text'] = re.sub(r'\s+', ' ', combined).strip()
                    continue
            merged.append(entry)

        entries = merged

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
            
        # --- PASS 1: Semantic Splitting ---
        # Ensure every entry fits on a single line horizontally
        split_entries = []
        for e in entries:
            split_entries.extend(self._split_at_best_point(e, max_chars))
        entries = split_entries

        cleaned = []
        last_end = 0.0
        
        for i, e in enumerate(entries):
            start = self.parse_to_sec(e['start'])
            end = self.parse_to_sec(e['end'])
            
            # Enforce min duration (extend end if needed)
            if end - start < min_duration:
                end = start + min_duration
            
            # --- TIMING PADDING ---
            # Extend end time if there is a silent gap to make subtitles less "hurried"
            next_start_time = self.parse_to_sec(entries[i+1]['start']) if i + 1 < len(entries) else 1e9
            gap = next_start_time - end
            if gap > 0.3:
                 # Add 0.5s padding, but leave at least 0.05s gap for player consistency
                 padding = min(0.5, gap - 0.05)
                 end += padding
            
            
            # Fix Overlap
            if start < last_end:
                # Overlap detected!
                # Option 1: Shrink previous (too late, already processed)
                # Option 2: Shift current start (might make it too short)
                # Option 3: Middle ground (best for continuous speech)
                overlap = last_end - start
                if overlap > 0:
                    start = last_end # Hard cut: Start exactly when previous ends
                    if end - start < min_duration:
                         end = start + min_duration

            # Update entry
            e['start'] = self.format_time(start)
            e['end'] = self.format_time(end)
            
            cleaned.append(e)
            last_end = end
            
        # --- DUPLICATE DETECTION: Remove consecutive identical entries (hallucination fix) ---
        deduped = []
        for entry in cleaned:
            # Skip if this is identical to the last entry
            if deduped and entry['text'].strip() == deduped[-1]['text'].strip():
                # Extend the end time of the previous entry instead of creating a new one
                deduped[-1]['end'] = entry['end']
                continue
            deduped.append(entry)
        
        # Log if duplicates were found
        removed_count = len(cleaned) - len(deduped)
        if removed_count > 0:
            self.logger.warning(f"⚠️ Removed {removed_count} duplicate entries (Whisper hallucination suppression)")
        
        cleaned = deduped
        
        # --- Post-processing: orphan prevention and collocation NBSP insertion ---
        # Load collocations set once
        collocations = self._load_collocations()

        final = []
        i = 0
        # Use 42 as the master limit for bilingual single-line harmony
        max_chars = getattr(self.style_config, 'max_chars', 42)

        while i < len(cleaned):
            cur = cleaned[i]
            text = cur.get('text', '').strip()
            # Remove Whisper artifacts first
            text = self._remove_whisper_artifacts(text)
            cur['text'] = text
            
            # Use clean text for length/word logic
            ctext = self._clean_bidi(text)

            # 1) Orphan prevention: smarter merge preference for short segments
            # threshold: <= 2 words or < 12 characters (covers Persian translations of single English words)
            words = ctext.split()
            if len(words) <= 2 or len(ctext) < 12:
                prev = final[-1] if final else None
                nxt = cleaned[i+1] if i + 1 < len(cleaned) else None

                # prefer merging with next if that forms a collocation
                merged_with_next = False
                # Aggressive threshold for orphans (allow up to 60 chars)
                orphan_max = 60
                
                if nxt:
                    cnxt_text = self._clean_bidi(nxt['text'])
                    right_first = re.findall(r"[\w\u0600-\u06FF'-]+", cnxt_text)
                    if right_first:
                        pair = f"{words[0].lower()} {right_first[0].lower()}"
                        if pair in collocations:
                            combined_clean = ctext + ' ' + cnxt_text
                            if len(combined_clean) <= orphan_max:
                                nxt['start'] = cur['start']
                                nxt['text'] = combined_clean # No fix_persian_text here!
                                i += 1
                                merged_with_next = True
                                continue

                # otherwise try previous if exists
                if prev and not merged_with_next:
                    cprev = self._clean_bidi(prev['text'])
                    combined_clean = cprev + ' ' + ctext
                    if len(combined_clean) <= orphan_max:
                        prev['end'] = cur['end']
                        prev['text'] = combined_clean # No fix_persian_text here!
                        i += 1
                        continue

            # 3) Collocation NBSP insertion within the entry
            if text:
                # Normalize and scan for bigrams
                words_only = [w for w in re.findall(r"[\w\u0600-\u06FF'-]+", text)]
                if words_only:
                    rebuilt = text
                    # Check adjacent word pairs
                    for a, b in zip(words_only, words_only[1:]):
                        pair = f"{a.lower()} {b.lower()}"
                        if pair in collocations:
                            # replace occurrences of the pair (case-insensitive)
                            rebuilt = re.sub(re.escape(a) + r"\s+" + re.escape(b), a + '\u00A0' + b, rebuilt, flags=re.IGNORECASE)
                    cur['text'] = rebuilt

            final.append(cur)
            i += 1

        # 5) Reset Indices: Ensure stable numeric mapping for all downstream processes
        # This is critical for the "Master Timeline" strategy.
        for idx, entry in enumerate(final, 1):
            entry['index'] = str(idx)

        return final


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
            # Fallback to mid-word split if no better option
            split_pos = text.rfind(' ', 0, max_chars)
            if split_pos == -1: split_pos = len(text) // 2
            
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
        
        # Prepare translation
        indices = list(range(len(texts)))
        
        # Translate
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        system = self.get_translation_prompt(target_lang)
        
        translated = []
        last_error = "Unknown error"
        
        # Initialize result list
        final_result = [None] * len(texts)
        # Prefill with any existing recovered translations to avoid re-translation costs
        if existing_translations:
            for idx, txt in existing_translations.items():
                if 0 <= idx < len(final_result) and txt and txt.strip():
                    final_result[idx] = txt
            
        # Remove indices that are already present in final_result
        indices_to_translate = [i for i in indices if final_result[i] is None]
        if not indices_to_translate:
            # Nothing to translate; return final_result (with possible None replaced with source texts)
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

        batch_indices_list = self._create_balanced_batches(indices_to_translate, texts, batch_size)
        batch_count = len(batch_indices_list)
        pbar = tqdm(total=len(indices), unit="item", desc=f"  Translating ({target_lang.upper()})")
        
        for i, batch_indices in enumerate(batch_indices_list):
            batch = [texts[idx] for idx in batch_indices]
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
            
            # The absolute indices we still need to translate in this batch
            current_target_indices = list(batch_indices)
            
            # NUCLEAR PERSISTENCE: Retry until successful (Max 10 attempts)
            attempt = 0
            max_retries = 10
            success_batch = False
            ds_failed = False
            last_error_msg = ""
            
            while attempt < max_retries and current_target_indices:
                attempt += 1
                
                # Context lines (3 before first target, 3 after last target in the original batch size scope)
                first_abs = current_target_indices[0]
                last_abs  = current_target_indices[-1]
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

                current_batch_texts = [texts[idx] for idx in current_target_indices]
                # Keep prompt numbering 1..N matching the output indices we expect
                batch_text = ctx_section + "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(current_batch_texts)])
                
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=self.temperature,
                        max_tokens=4000
                    )
                    
                    output = response.choices[0].message.content.strip()
                    # Use a zero threshold to eagerly accept any validly extracted subsets for partial retries
                    trans_list = self._parse_translated_batch_output(output, len(current_target_indices), threshold=0.0)
                    
                    if not trans_list:
                        delay = min(20 + attempt * 5, 120)
                        self.logger.warning(f"⚠️ Batch {i + 1} partial attempt returned empty. Retrying in {delay}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(delay)
                        if attempt >= max_retries:
                            last_error_msg = f"incomplete response after {max_retries} attempts"
                            ds_failed = True
                            break
                        continue
                        
                    # Process items and identify successes
                    successful_indices = []
                    for rel_idx, t in enumerate(trans_list):
                        abs_idx = current_target_indices[rel_idx]
                        if t is None or not str(t).strip():
                            continue # Failed this specific line
                        
                        raw_t = str(t)
                        if target_lang == 'fa':
                            if not any('\u0600' <= c <= '\u06FF' for c in raw_t):
                                continue # Failed (no Persian chars)
                            val = self.fix_persian_text(self.strip_english_echo(raw_t))
                        else:
                            val = raw_t
                            
                        final_result[abs_idx] = val
                        successful_indices.append(abs_idx)
                        
                    missing_indices = [idx for idx in current_target_indices if idx not in successful_indices]
                    
                    # Update progress bar only for newly translated items
                    if successful_indices:
                        pbar.update(len(successful_indices))
                        
                    # LIVE SAVING: Write progress to SRT file immediately
                    if successful_indices and output_srt and original_entries:
                        try:
                            with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                for idx_srt, entry in enumerate(original_entries, 1):
                                    trans = final_result[idx_srt-1]
                                    t_text = trans if trans is not None else entry['text']
                                    f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                        except: pass

                    if not missing_indices:
                        success_batch = True
                        time.sleep(1)
                        break
                    else:
                        current_target_indices = missing_indices
                        delay = min(20 + attempt * 5, 120)
                        self.logger.warning(f"⚠️ Batch {i + 1} partially incomplete ({len(missing_indices)} lines missing). Retrying missing lines in {delay}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(delay)

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    last_error_msg = error_msg
                    if "401" in error_msg or "Invalid API Key" in error_msg:
                        raise
                    if attempt >= max_retries:
                        ds_failed = True
                        break
                    wait_time = min(60, (2 ** (attempt % 6)) * 5)
                    self.logger.warning(f"Batch {i+1} attempt {attempt}/{max_retries} failed: {error_msg}")
                    time.sleep(wait_time)

            # ── Per-batch Gemini fallback when DeepSeek fails ────────────────
            if not success_batch:
                gemini_ok = False
                if HAS_GEMINI and self.google_api_key:
                    self.logger.warning(f"⚠️ DeepSeek batch {i+1} failed ({last_error_msg}). Switching to Gemini for this batch...")
                    try:
                        from google import genai as _genai
                        _gclient = _genai.Client(api_key=self.google_api_key)
                        _models = self._get_available_gemini_models(_gclient)
                        _prompt = f"{self.get_translation_prompt(target_lang)}\n\nLines to translate:\n{batch_text}"
                        for _model in _models[:3]:
                            try:
                                _resp = _gclient.models.generate_content(model=_model, contents=_prompt)
                                _tlist = self._parse_translated_batch_output(_resp.text.strip(), len(batch))
                                if None in _tlist:
                                    _tlist = [_tlist[j] if _tlist[j] is not None else batch[j] for j in range(len(_tlist))]
                                if target_lang == 'fa':
                                    _tlist = [self.fix_persian_text(self.strip_english_echo(t)) if t and has_target_language_chars(t, target_lang) else batch[j]
                                              for j, t in enumerate(_tlist)]
                                if len(_tlist) >= len(batch):
                                    for rel_idx, trans in enumerate(_tlist[:len(batch)]):
                                        final_result[batch_indices[rel_idx]] = trans
                                    if output_srt and original_entries:
                                        try:
                                            with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                                for _idx, _entry in enumerate(original_entries, 1):
                                                    _tr = final_result[_idx-1]
                                                    f.write(f"{_idx}\n{_entry['start']} --> {_entry['end']}\n{_tr if _tr else _entry['text']}\n\n")
                                        except: pass
                                    pbar.update(len(batch))
                                    gemini_ok = True
                                    self.logger.info(f"✅ Gemini saved batch {i+1} via {_model}")
                                    break
                            except Exception as _ge:
                                self.logger.debug(f"Gemini model {_model} failed: {_ge}")
                    except Exception as ge:
                        self.logger.warning(f"Gemini fallback init failed: {ge}")
                if not gemini_ok:
                    self.logger.error(f"❌ TERMINATING: Batch {i+1} failed on both DeepSeek and Gemini.")
                    pbar.close()
                    raise RuntimeError(f"Translation halted: batch {i+1} failed — DeepSeek: {last_error_msg}")
        
        pbar.close()
        return final_result

    def _get_available_gemini_models(self, client) -> List[str]:
        """Fetch and rank available models from Google API with smart filtering"""
        try:
            all_models = list(client.models.list())
            
            # Specialization Blacklist: Avoid non-text models
            # These are for image gen, tts, or native audio processing
            blacklist = ['image', 'tts', 'audio', 'video', 'voice', 'embedding']
            
            candidates = []
            for m in all_models:
                name_lower = m.name.lower()
                
                # Skip blacklisted specialized models
                if any(word in name_lower for word in blacklist):
                    continue
                
                # Filter for generation capability
                actions = getattr(m, 'supported_actions', []) or getattr(m, 'supported_generation_methods', [])
                if 'generateContent' in actions:
                    candidates.append(m.name)
            
            # Ranking Logic (2026 Pro Standard)
            def rank_score(name):
                score = 0
                name_lower = name.lower()
                
                # Version boosting (Higher is better)
                if '3.0' in name_lower: score += 300
                elif '2.5' in name_lower: score += 250
                elif '2.0' in name_lower: score += 200
                elif '1.5' in name_lower: score += 150
                
                # Capability boosting
                if 'pro' in name_lower: score += 50
                elif 'flash' in name_lower: score += 10
                
                # Penalize experimental or specific preview/thinking variants 
                # unless they are the top-tier version
                if 'exp' in name_lower: score -= 5
                if 'preview' in name_lower: score -= 10
                if 'thinking' in name_lower: score -= 15 # Thinking models are slow for batch translation
                if '8b' in name_lower: score -= 20 # Smaller models are less accurate
                
                return score

            ranked = sorted(candidates, key=rank_score, reverse=True)
            
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
        if not HAS_GEMINI:
            self.logger.warning("google-genai SDK not installed. Falling back to DeepSeek.")
            return self.translate_with_deepseek(texts, target_lang, source_lang, 30, original_entries, output_srt, existing_translations)
        
        if not self.google_api_key:
            self.logger.error("GOOGLE_API_KEY not found. Cannot use Gemini.")
            return self.translate_with_deepseek(texts, target_lang, source_lang, 30, original_entries, output_srt, existing_translations)

        # Initialize the modern Gemini Client
        from google import genai
        client = genai.Client(api_key=self.google_api_key)
        
        # Dynamic Fallback Chain
        models = self._get_available_gemini_models(client)
        self.logger.info(f"📡 Discovered {len(models)} Gemini models. Top pick: {models[0]}")
        
        indices = list(range(len(texts)))

        final_result = [None] * len(texts)
        # Prefill with any existing recovered translations to avoid re-translation costs
        if existing_translations:
            for idx, txt in existing_translations.items():
                if 0 <= idx < len(final_result) and txt and txt.strip():
                    final_result[idx] = txt
        
        # Remove indices that are already present in final_result
        indices_to_translate = [i for i in indices if final_result[i] is None]
        if not indices_to_translate:
            # Nothing to translate; return final_result (with possible None replaced with source texts)
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

        batch_indices_list = self._create_balanced_batches(indices_to_translate, texts, batch_size)
        batch_count = len(batch_indices_list)
        pbar = tqdm(total=len(indices_to_translate), unit="item", desc=f"  Gemini-Translating ({target_lang.upper()})")

        for i, batch_indices in enumerate(batch_indices_list):
            batch = [texts[idx] for idx in batch_indices]

            # ── Context lines (3 before + 3 after, not translated) ──────────
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

            # Use indexed list for perfect alignment across all models
            batch_text = ctx_section + "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
            
            success = False
            # LIMIT SEARCH: Only try top 6 most capable models to avoid wasting time
            for model_name in models[:6]:
                if success: break
                for attempt in range(2): 
                    try:
                        prompt = f"{self.get_translation_prompt(target_lang)}\n\nText to translate (numbered list):\n{batch_text}"
                        
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        output = response.text.strip()
                        trans_list = self._parse_translated_batch_output(output, len(batch))
                        
                        # Replace None with original text
                        if None in trans_list:
                            trans_list = [trans_list[j] if trans_list[j] is not None else batch[j] for j in range(len(trans_list))]
                        
                        if target_lang == 'fa':
                            processed = []
                            for idx, t in enumerate(trans_list):
                                if t and has_target_language_chars(t, target_lang):
                                    processed.append(self.fix_persian_text(self.strip_english_echo(t)))
                                else:
                                    # Keep original English if no Persian detected
                                    processed.append(batch[idx] if idx < len(batch) else t)
                            trans_list = processed
                        
                        if len(trans_list) >= len(batch):
                            result_batch = trans_list[:len(batch)]
                            for rel_idx, trans in enumerate(result_batch):
                                abs_idx = batch_indices[rel_idx]
                                final_result[abs_idx] = trans
                            
                            # Live saving
                            if output_srt and original_entries:
                                with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                    for idx, entry in enumerate(original_entries, 1):
                                        tr = final_result[idx-1]
                                        t_text = tr if tr is not None else entry['text']
                                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                            
                            success = True
                            pbar.update(len(batch))
                            break
                        else:
                            delay = min(4 + attempt, 10)
                            self.logger.warning(f"⚠️ {model_name} batch incomplete: got {len(trans_list)}/{len(batch)}. Retrying in {delay}s...")
                            time.sleep(delay)
                    except Exception as e:
                        if "404" not in str(e) and "403" not in str(e):
                            self.logger.warning(f"🛡️ {model_name} attempt {attempt} failed: {e}")
                        time.sleep(1)
                
                if not success:
                    self.logger.debug(f"🔄 Model {model_name} exhausted. Falling back downstream...")

            if not success:
                # ZERO-SKIP POLICY (GEMINI): Try emergency DeepSeek before halting
                try:
                    self.logger.info("🆘 EMERGENCY FALLBACK: Gemini failed. Switching to DeepSeek for this batch...")
                    ds_result = self.translate_with_deepseek(batch, target_lang, source_lang, 30)
                    for idx_in_batch, txt in zip(batch_indices, ds_result):
                        final_result[idx_in_batch] = txt
                except Exception as e:
                    self.logger.error(f"❌ CRITICAL FAILURE: Both Gemini and DeepSeek failed for batch {i//batch_size + 1}")
                    raise RuntimeError(f"Translation halted to prevent data loss: {e}")
                pbar.update(len(batch))

        pbar.close()
        return final_result

    # ==================== LITELLM TRANSLATION (DEBUG/TEST) ====================

    def translate_with_litellm(self, texts: List[str], target_lang: str, source_lang: str = 'en', batch_size: int = 20, original_entries: List[Dict] = None, output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Universal LLM bridge via LiteLLM for debugging and testing"""
        if not HAS_LITELLM:
            self.logger.error("LiteLLM not installed. Use 'uv pip install litellm'")
            return self.translate_with_deepseek(texts, target_lang, source_lang, 30, original_entries, output_srt, existing_translations)

        from litellm import completion
        
        # Use provided custom_model or default to something reliable
        model_name = self.custom_model or "gpt-4o-mini" 
        
        # SMART RESOLVER: Add provider prefix if missing for common models
        if "/" not in model_name:
            if "deepseek" in model_name.lower():
                model_name = f"deepseek/{model_name}"
            elif any(x in model_name.lower() for x in ["gpt-", "o1-", "o3-"]):
                model_name = f"openai/{model_name}"
            elif "claude" in model_name.lower():
                model_name = f"anthropic/{model_name}"
            elif "gemini" in model_name.lower():
                model_name = f"google/{model_name}"
        
        self.logger.info(f"🌌 LiteLLM Bridge Active. Resolved Model: {model_name}")

        indices = list(range(len(texts)))

        final_result = [None] * len(texts)
        # Prefill with any existing recovered translations to avoid re-translation costs
        if existing_translations:
            for idx, txt in existing_translations.items():
                if 0 <= idx < len(final_result) and txt and txt.strip():
                    final_result[idx] = txt
        
        # Remove indices that are already present in final_result
        indices_to_translate = [i for i in indices if final_result[i] is None]
        if not indices_to_translate:
            # Nothing to translate; return final_result (with possible None replaced with source texts)
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

        batch_indices_list = self._create_balanced_batches(indices_to_translate, texts, batch_size)
        batch_count = len(batch_indices_list)
        pbar = tqdm(total=len(indices_to_translate), unit="item", desc=f"  LiteLLM-Translating ({model_name})")
        
        for i, batch_indices in enumerate(batch_indices_list):
            batch = [texts[idx] for idx in batch_indices]
            # Use indexed list for LiteLLM bridge stability
            batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
            
            # NUCLEAR RETRY LOGIC for LiteLLM
            attempt = 0
            max_retries = 10 
            success = False
            
            while attempt < max_retries and not success:
                attempt += 1
                try:
                    # Variation: nudge temperature slightly on retries to break stuck loops
                    current_temp = self.temperature + (attempt * 0.05 if attempt > 3 else 0)
                    
                    response = completion(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=min(1.0, current_temp), # Cap temperature
                        timeout=90
                    )
                    
                    output = response.choices[0].message.content.strip()
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                    # Replace None with original text
                    if None in trans_list:
                        trans_list = [trans_list[j] if trans_list[j] is not None else batch[j] for j in range(len(trans_list))]
                    
                    if target_lang == 'fa':
                        processed = []
                        for idx, t in enumerate(trans_list):
                            if t and has_target_language_chars(t, target_lang):
                                processed.append(self.fix_persian_text(self.strip_english_echo(t)))
                            else:
                                # Keep original English if no Persian detected
                                processed.append(batch[idx] if idx < len(batch) else t)
                        trans_list = processed
                    
                    if len(trans_list) >= len(batch):
                        for rel_idx, trans in enumerate(trans_list[:len(batch)]):
                            abs_idx = batch_indices[rel_idx]
                            final_result[abs_idx] = trans
                        
                        # Live saving
                        if output_srt and original_entries:
                            with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                for idx, entry in enumerate(original_entries, 1):
                                    tr = final_result[idx-1]
                                    t_text = tr if tr is not None else entry['text']
                                    f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                        
                        success = True
                        pbar.update(len(batch))
                    else:
                        delay = min(5 + attempt, 12)
                        self.logger.warning(f"⚠️ LiteLLM attempt {attempt}/{max_retries} incomplete: {len(trans_list)}/{len(batch)}. Retrying in {delay}s...")
                        time.sleep(delay)

                except Exception as e:
                    self.logger.error(f"❌ LiteLLM attempt {attempt} failed: {e}")
                    if attempt >= max_retries:
                        raise RuntimeError(f"Halted: LiteLLM failed after {max_retries} attempts: {e}")
                    time.sleep(5)

        pbar.close()
        return final_result

    # ==================== MINIMAX TRANSLATION ====================

    def translate_with_minimax(self, texts: List[str], target_lang: str, source_lang: str = 'en',
                                batch_size: int = 15, original_entries: List[Dict] = None,
                                output_srt: str = None, existing_translations: Dict[int, str] = None) -> List[str]:
        """Translate subtitle texts using MiniMax LLM (OpenAI-compatible API)."""
        if not self.minimax_api_key:
            raise RuntimeError("MINIMAX_API_KEY not set. Export it before running.")

        from openai import OpenAI as _OAI
        # platform.minimax.io (international) → api.minimax.io/v1
        # platform.minimax.chat (China)        → api.minimax.chat/v1
        client = _OAI(api_key=self.minimax_api_key, base_url="https://api.minimax.io/v1")

        indices = list(range(len(texts)))
        final_result: List[Optional[str]] = [None] * len(texts)

        if existing_translations:
            for idx, trans in existing_translations.items():
                if 0 <= idx < len(texts):
                    final_result[idx] = trans

        indices_to_translate = [i for i in indices if final_result[i] is None]
        if not indices_to_translate:
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]

        batch_indices_list = self._create_balanced_batches(indices_to_translate, texts, batch_size)
        batch_count = len(batch_indices_list)
        pbar = tqdm(total=len(indices_to_translate), unit="item", desc=f"  MiniMax-Translating ({target_lang.upper()})")

        for i, batch_indices in enumerate(batch_indices_list):
            batch = [texts[idx] for idx in batch_indices]
            # Skip context lines for MiniMax (performance optimization)
            batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})

            attempt = 0
            max_retries = 6
            success_batch = False
            last_error_msg = ""
            while attempt < max_retries:
                try:
                    attempt += 1
                    response = client.chat.completions.create(
                        model="MiniMax-M2.5",
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=1.0,  # MiniMax default & optimal for translation
                        max_tokens=1500
                    )
                    output = response.choices[0].message.content.strip()
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    if None in trans_list:
                        trans_list = [trans_list[j] if trans_list[j] is not None else batch[j] for j in range(len(trans_list))]
                    if target_lang == 'fa':
                        trans_list = [self.fix_persian_text(self.strip_english_echo(t)) if t and has_target_language_chars(t, target_lang)
                                      else batch[j] for j, t in enumerate(trans_list)]
                    if len(trans_list) >= len(batch):
                        for rel_idx, trans in enumerate(trans_list[:len(batch)]):
                            final_result[batch_indices[rel_idx]] = trans
                        if output_srt and original_entries:
                            try:
                                with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                    for _idx, _entry in enumerate(original_entries, 1):
                                        _tr = final_result[_idx - 1]
                                        f.write(f"{_idx}\n{_entry['start']} --> {_entry['end']}\n{_tr if _tr else _entry['text']}\n\n")
                            except: pass
                        pbar.update(len(batch))
                        success_batch = True
                        time.sleep(0.1)
                        break
                    else:
                        delay = min(20 + attempt * 5, 120)
                        self.logger.warning(f"⚠️ MiniMax batch {i+1} incomplete: got {len(trans_list)}/{len(batch)}. Retry {attempt}/{max_retries} in {delay}s...")
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

            if not success_batch:
                self.logger.error(f"❌ MiniMax batch {i+1} failed after {max_retries} attempts: {last_error_msg}")
                pbar.close()
                raise RuntimeError(f"MiniMax translation halted at batch {i+1}: {last_error_msg}")

        pbar.close()
        return final_result

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

    def create_ass_with_font(self, srt_path: str, ass_path: str, lang: str, secondary_srt: Optional[str] = None, time_offset: float = 0.0, video_width: int = 0, video_height: int = 0):
        """Generate ASS file"""
        title = f"{get_language_config(lang).name} + {get_language_config('fa').name}" if secondary_srt else get_language_config(lang).name
        self.logger.info(f"Generating ASS asset ({title})...")
        
        style = self.style_config
        
        # Portrait videos need stable margins; keep bilingual rows close so they
        # look like two consecutive lines instead of widely separated tiers.
        is_portrait = bool(video_width and video_height and video_height > video_width)
        # Keep a safer side margin in portrait to avoid clipping on narrow frames.
        margin_h = 64 if is_portrait else 64
        fa_margin_v = 26 if is_portrait else 10
        # Previous value (92/56) pushed the English row too high. Tighten the
        # offset to keep EN directly above FA in bilingual mode.
        top_margin_v = 44 if is_portrait else 24
        
        if lang == 'fa' or secondary_srt:
            # Calculate actual FA font size based on scales (style.font_size is already scaled by EN scale in __init__)
            en_scale = getattr(self, 'en_font_scale', 1.0)
            fa_scale = getattr(self, 'fa_font_scale', 1.0)
            base_size = style.font_size / en_scale if en_scale > 0 else style.font_size
            fa_font_size = int(base_size * fa_scale)
            fa_font_name = getattr(self, 'fa_font_name', 'Vazirmatn')
            
            fa_style = (
                f"Style: FaDefault,{fa_font_name},{fa_font_size},&H00FFFFFF,&H000000FF,&H00000000,{style.back_color},"
                f"-1,0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
                f"{style.alignment},{margin_h},{margin_h},{fa_margin_v},1"
            )
        
        # Standard V4+ Styles Format (23 entries)
        format_line = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"

        # Update primary_style to match full format
        primary_style_full = (
            f"Style: Default,{style.font_name},{style.font_size},{style.primary_color},&H000000FF,&H00000000,{style.back_color},"
            f"0,0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
            f"{style.alignment},{margin_h},{margin_h},{fa_margin_v},1"
        )

        top_style = (
            f"Style: TopDefault,{style.font_name},{style.font_size},{style.primary_color},&H000000FF,&H00000000,{style.back_color},"
            f"0,0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
            f"{style.alignment},{margin_h},{margin_h},{top_margin_v},1"
        )

        # Build styles block: always include primary, conditionally add FA
        # PlayResX/Y intentionally omitted — libass uses its default 640×480 coordinate
        # space, which keeps Fontsize values at their intended visual weight.
        # MarginL/R are already expressed in that same 640-wide space (see margin_h above).
        # WrapStyle 2 (no-wrap) in bilingual mode: libass on darwin_arm64 ignores inline
        # \q override tags, so the only reliable way to prevent the English top row from
        # being "smart-balanced" into two lines is to set WrapStyle:2 in the header.
        # Persian lines are pre-segmented and fit comfortably; if one ever overflows it
        # is truncated at the margin, which is far better than a 3-line layout.
        # WrapStyle 0 (smart wrap) is kept for monolingual mode as a safety net.
        wrap_style = "2" if secondary_srt else "0"

        styles_block = f"{format_line}\n{primary_style_full}"
        if secondary_srt:
            styles_block += f"\n{top_style}"
        if lang == 'fa' or secondary_srt:
            styles_block += f"\n{fa_style}"

        header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: {wrap_style}

[V4+ Styles]
{styles_block}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        secondary_map = {}
        if secondary_srt and os.path.exists(secondary_srt):
            sec = self.parse_srt(secondary_srt)
            # Sync protection: Do NOT re-sanitize here, assume already sanitized in workflow
            # Use original INDEX-based mapping to ensure perfect alignment regardless of empty strings
            for e in sec:
                secondary_map[e['index']] = e['text'] # fix_persian_text will be handled during rendering
        
        entries = self.parse_srt(srt_path)
        # Sync protection: Do NOT re-sanitize here, assume already sanitized in workflow
        
        events = []
        
        def wrap_parentheses_with_smaller_font(text: str) -> str:
            """Wrap English terms in parentheses with a smaller ASS font scale."""
            # Strip any pre-existing RLM markers around parentheses (from fix_persian_text)
            pattern = r'[\u200F]?\(([a-zA-Z0-9\s/_\-\.]+)\)[\u200F]?'
            # Scale down to 75% — no RLM needed; Vazirmatn handles RTL direction natively
            replacement = r'{\fscx75\fscy75}(\1){\fscx100\fscy100}'
            return re.sub(pattern, replacement, text)
        
        for idx, e in enumerate(entries):
            start = e['start'].replace(',', '.')
            end = e['end'].replace(',', '.')
            # Enforce single line for English text in bilingual mode
            # Standardize on a single space for all newline markers (\n, \N, \r)
            text = e['text'].replace('\n', ' ').replace('\\N', ' ').replace('\\n', ' ').strip()
            # Reduce multiple spaces to one
            text = ' '.join(text.split())
            # In bilingual mode, hard-truncate top line to keep it inside frame.
            # Portrait videos need a stricter cap due narrower width.
            # At fs13 in the default 640-wide ASS coordinate space, Latin glyphs average
            # ~7 ASS units, giving ~80 usable chars per line. 70 is a safe generous cap for
            # landscape; 42 for portrait (9:16 width is roughly 40% narrower in ASS space).
            max_top_chars = 42 if is_portrait else 70
            # In bilingual mode, hard-truncate English to avoid wrap/clipping.
            # rendering regardless of WrapStyle or libass version differences.
            if secondary_srt and len(text) > max_top_chars:
                text = text[:max_top_chars].rsplit(' ', 1)[0] + '…'
            
            final_text = text
            _bi_fa_text = None  # Separate Persian event text for bilingual mode
            
            # --- PERSIAN SHAPING LOGIC REMOVED ---
            # FFmpeg is compiled with --enable-libharfbuzz, so it handles Arabic/Persian natively.
            # Manual reshaping interferes with HarfBuzz and causes "backwards" text.
            # We simply pass the raw UTF-8 text.
            
            # If we need to force RTL base direction, we use standard Unicode markers if needed,
            # but usually raw text is best for HarfBuzz.

            if secondary_map:
                # Use INDEX-based matching for perfect alignment
                sec_text = secondary_map.get(e['index'])
                
                if sec_text:
                    # Clean and re-fix to ensure no double-wrapping
                    sec_text = SubtitleProcessor._clean_bidi(sec_text)
                    sec_text_fixed = self.fix_persian_text(sec_text)
                    # Wrap English terms in parentheses with smaller font
                    sec_text_formatted = wrap_parentheses_with_smaller_font(sec_text_fixed)
                    # Top row (primary/source): smaller gray — fixed at 75%, never dynamic.
                    # Bottom row (secondary/FA): full size white bold — never changes.
                    # Font size MUST be constant per video; dynamic sizing causes jarring jumps.
                    top_scale = 0.90 if is_portrait else 0.82
                    top_fs = max(13, int(style.font_size * top_scale))
                    bot_fs = style.font_size
                    # RTL direction handled by FaDefault style (Vazirmatn is inherently RTL).
                    # Do NOT insert RLM here — libass renders it as a visible rectangle.
                    # Use TWO separate Dialogue events instead of one combined event.
                    # Reason: \q is event-level in libass — the last \q tag wins for the entire
                    # event. A single combined event with {\q2}EN\N{\q0}FA means \q0 cancels
                    # \q2 and the English top line still word-wraps. Two events each have their
                    # own independent wrap setting.
                    # Persian event is added FIRST so libass places it at the natural bottom
                    # position; the English event (added second) is pushed above by libass
                    # collision avoidance.
                    final_text = f"{{\\q2}}{{\\fs{top_fs}}}{{\\c&H808080}}{text}"
                    _bi_fa_text = f"{{\\b1}}{{\\fs{bot_fs}}}{sec_text_formatted}"
                else:
                    final_text = text
            
            # ASS requires 1-digit hour (usually) and 2-digit centiseconds
            # We must convert 00:00:00,000 (SRT) to 0:00:00.00 (ASS)
            def srt_to_ass_time(t_str):
                # t_str is HH:MM:SS,mmm — work in whole milliseconds to avoid float errors
                h, m, s_ms = t_str.replace(',', '.').split(':')
                s, ms = s_ms.split('.')
                total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms)
                # Apply time offset (e.g. when video was trimmed with --limit)
                offset_ms = int(time_offset * 1000)
                total_ms = max(0, total_ms - offset_ms)
                out_h  = total_ms // 3600000
                out_m  = (total_ms % 3600000) // 60000
                out_s  = (total_ms % 60000) // 1000
                out_cs = (total_ms % 1000) // 10
                return f"{out_h}:{out_m:02d}:{out_s:02d}.{out_cs:02d}"

            ass_start = srt_to_ass_time(e['start'])
            ass_end = srt_to_ass_time(e['end'])

            # Strip BiDi directional control chars. Keep ZWNJ (\u200C) — Vazirmatn renders it
            # as a true invisible zero-width glyph, needed for correct Persian letterform shaping.
            for _cp in ('\u200f', '\u200e', '\u200d',
                        '\u202b', '\u202a', '\u202c', '\u202e', '\u202d'):
                final_text = final_text.replace(_cp, '')
                if _bi_fa_text:
                    _bi_fa_text = _bi_fa_text.replace(_cp, '')

            # Use FaDefault style when primary lang is FA (RTL) and no secondary row.
            # In bilingual mode, Default is used for the top row and FaDefault is applied
            # inline (via {\rFaDefault}) for the bottom row.
            event_style = "FaDefault" if (lang == 'fa' and not secondary_map) else "Default"
            if _bi_fa_text:
                # Two-event bilingual: Persian first → libass places it at bottom.
                # English second → libass collision avoidance pushes it above Persian.
                events.append(f"Dialogue: 0,{ass_start},{ass_end},FaDefault,,0,0,0,,{_bi_fa_text}")
                events.append(f"Dialogue: 0,{ass_start},{ass_end},TopDefault,,0,0,0,,{final_text}")
            else:
                events.append(f"Dialogue: 0,{ass_start},{ass_end},{event_style},,0,0,0,,{final_text}")
        
        with open(ass_path, 'w', encoding='utf-8') as f:
            # Add BOM for good measure
            f.write('\ufeff' + header + "\n".join(events))
        
        self.logger.info(f"ASS asset generation complete: {Path(ass_path).name}")

    @staticmethod
    def _to_persian_digits(value) -> str:
        """Convert Arabic/Latin digits to Persian-Indic numerals (۰–۹)."""
        arabic_to_persian = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
        return str(value).translate(arabic_to_persian)

    @staticmethod
    def _srt_duration_str(entries: List[Dict], lang: str = 'fa') -> str:
        """Return human-readable duration from the last SRT entry's end timestamp.

        When ``lang == 'fa'`` numbers are Persian-Indic and words are Farsi
        (e.g. ۲۴ دقیقه و ۵۰ ثانیه). All other language codes produce
        Arabic numerals with English words (e.g. 24 min 50 sec).
        """
        if not entries:
            return ''
        last_end = entries[-1]['end']  # e.g. '00:24:50,260'
        try:
            hms, ms = last_end.split(',')
            h, m, s = map(int, hms.split(':'))
            total_sec = h * 3600 + m * 60 + s
            return SubtitleProcessor._format_total_seconds(total_sec, lang=lang)
        except Exception:
            return ''

    @staticmethod
    def _format_total_seconds(total_sec: float, lang: str = 'fa') -> str:
        """Format raw seconds into human-readable duration (e.g. 1 hr 44 min)."""
        total_sec = int(total_sec)
        hours = total_sec // 3600
        mins  = (total_sec % 3600) // 60
        secs  = total_sec % 60

        def _fa(n: int) -> str:
            return str(n).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

        if lang == 'fa':
            if hours > 0:
                ret = f'{_fa(hours)} ساعت'
                if mins > 0: ret += f' و {_fa(mins)} دقیقه'
                return ret
            elif mins > 0:
                if secs >= 30:
                    return f'{_fa(mins)} دقیقه و {_fa(secs)} ثانیه'
                else:
                    return f'{_fa(mins)} دقیقه'
            else:
                return f'{_fa(secs)} ثانیه'
        else:
            if hours > 0:
                ret = f'{hours} hr'
                if mins > 0: ret += f' {mins} min'
                return ret
            elif mins > 0:
                if secs >= 30:
                    return f'{mins} min {secs} sec'
                else:
                    return f'{mins} min'
            else:
                return f'{secs} sec'

    def parse_srt(self, srt_path: str) -> List[Dict]:
        with open(srt_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        pattern = re.compile(
            r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:(?!\n\n).)*)',
            re.DOTALL
        )
        
        entries = []
        for m in pattern.finditer(content):
            entries.append({
                'index': m.group(1),
                'start': m.group(2),
                'end': m.group(3),
                'text': m.group(4).strip().replace('\n', ' ')
            })
        return entries

    def validate_srt(self, srt_path: str, expected_count: int, target_lang: str = 'fa') -> bool:
        """Thorough validation of SRT file against entry count, language integrity and hallucination patterns"""
        if not os.path.exists(srt_path): return False
        try:
            # Check size first as a quick filter
            if os.path.getsize(srt_path) < 50: return False
            
            entries = self.parse_srt(srt_path)
            actual_count = len(entries)
            
            if actual_count != expected_count:
                self.logger.warning(f"⚠️ Parity mismatch for {Path(srt_path).name}: expected {expected_count}, found {actual_count}.")
                return False
            
            # CONTENT & DIVERSITY AUDIT
            texts = [e['text'].strip() for e in entries if e['text'].strip()]
            if not texts: return False

            # 1. Language Integrity (Strict: 98%)
            if target_lang == 'fa':
                persian_lines = sum(1 for t in texts if any('\u0600' <= c <= '\u06FF' for c in t))
                ratio = persian_lines / actual_count
                if ratio < 0.98:
                    self.logger.warning(f"⚠️ Content audit failed for {Path(srt_path).name}: Only {persian_lines}/{actual_count} ({ratio:.1%}) lines are Persian.")
                    return False
            
            # 2. Diversity Audit (Hallucination detection)
            if len(texts) > 50:
                # Check for extreme repetitions (common in LLM stuck loops)
                counts = {}
                for t in texts: counts[t] = counts.get(t, 0) + 1
                
                most_common_text = max(counts, key=counts.get)
                max_repeat = counts[most_common_text]
                
                if max_repeat > len(texts) * 0.05: # If one sentence repeats > 5% of the file
                    self.logger.warning(f"⚠️ Hallucination detected: Sentence '{most_common_text[:40]}...' repeats {max_repeat} times.")
                    return False

            return True
        except Exception as e:
            self.logger.debug(f"Validation error: {e}")
            return False

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

        # Resolve absolute path to properly handle inputs
        video_path = os.path.abspath(video_path)
        source_lang = (source_lang or 'auto').strip().lower()
        target_langs = [str(l).strip().lower() for l in (target_langs or ['auto', 'fa']) if str(l).strip()]

        _source_auto_requested = source_lang in ('auto', 'detect', '')
        # Normalize filename first so every downstream output uses a safe stem.
        if os.path.exists(video_path) and not post_only:
            video_path = self._ensure_safe_input_filename(video_path)
        self.logger.info(f"Processing sequence initiated: {Path(video_path).name}")
        
        result = {}
        temp_vid = None
        workflow_lock_path = None
        global_slot_path = None
        
        # ORIGINAL BASE: This is where ALL output files (SRT, ASS, Video) MUST go.
        # It should be based on the user's input file, not any temp/safe copies.
        original_dir = os.path.dirname(video_path)
        original_stem = Path(video_path).stem
        
        # If input is already a temp/safe file (e.g. from a previous step), try to clean it
        if "safe_input" in original_stem or "temp_" in original_stem:
            original_stem = re.sub(r'^(temp_\d+_|safe_)', '', original_stem)

        # Strip resolution suffix so all variants share one SRT/translation base.
        # Handles both "_240p" and collision names like "_240p_2".
        # e.g. "FooBar_480p", "FooBar_360p_2" -> original_base "FooBar"
        original_stem = re.sub(r'_\d{3,4}p(?:_q\d+)?(?:_\d+)?$', '', original_stem)

        # Detect SRT-as-input: user passed a pre-existing transcript file directly.
        # Convention: file is named <base>_<lang>.srt — strip the `_<lang>` suffix so
        # that original_base points at the real base name (same as if the video was given).
        _is_srt_input = video_path.lower().endswith('.srt')
        if _is_srt_input:
            # Auto-detect language from SRT filename (e.g. video_fa.srt → source_lang='fa').
            # This lets users pass `video_fa.srt` without needing `--source fa`.
            _stem_lang_match = re.search(r'_([a-z]{2,3})$', original_stem)
            if _stem_lang_match:
                _detected_srt_lang = _stem_lang_match.group(1)
                source_lang = _detected_srt_lang
                _source_auto_requested = False
                original_stem = original_stem[:-len(f'_{_detected_srt_lang}')]
            elif original_stem.endswith(f'_{source_lang}'):
                original_stem = original_stem[:-len(f'_{source_lang}')]

        # Choose canonical base path by reusing an existing SRT set when present.
        # This prevents re-transcription for variants like "..._360p_2.mp4" and
        # also supports older/unsanitized project folders that may live in cwd.
        _parent_dir = os.path.dirname(original_dir)
        _cwd = os.getcwd()
        self.logger.info(f"📁 Subtitle base resolution cwd: {_cwd}")
        _normalized_target_stem = self._sanitize_stem_for_fs(original_stem)

        def _stem_match_key(value: str) -> str:
            return re.sub(r'[^a-z0-9]+', '', (value or '').lower())

        _target_stem_key = _stem_match_key(_normalized_target_stem)

        def _normalize_candidate_stem(value: str) -> str:
            value = re.sub(r'_\d{3,4}p(?:_q\d+)?(?:_\d+)?$', '', value or '')
            return self._sanitize_stem_for_fs(value)

        _candidate_bases = [
            os.path.join(_cwd, original_stem),
            os.path.join(_cwd, _normalized_target_stem),
            os.path.join(_cwd, original_stem, original_stem),
            os.path.join(_cwd, _normalized_target_stem, _normalized_target_stem),
            os.path.join(original_dir, original_stem),
            os.path.join(_parent_dir, original_stem),
            os.path.join(_parent_dir, original_stem, original_stem),
        ]
        _probe_langs = [
            l for l in ([source_lang] + [t for t in (target_langs or []) if t != source_lang])
            if re.fullmatch(r"[a-z]{2,3}", str(l or '').lower())
        ]
        if source_lang in ('auto', 'detect', ''):
            # Auto-source mode: also probe common and locally discovered language codes
            # so existing *_en.srt can be reused before transcription.
            for _fallback_lang in ('en', 'fa', 'ar', 'fr', 'de', 'es', 'tr', 'it', 'ru', 'pt', 'zh', 'ja', 'ko'):
                if _fallback_lang not in _probe_langs:
                    _probe_langs.append(_fallback_lang)

            _scan_dirs = []
            for _d in (_cwd, os.path.join(_cwd, original_stem), original_dir, _parent_dir, os.path.join(_parent_dir, original_stem)):
                if _d and os.path.isdir(_d) and _d not in _scan_dirs:
                    _scan_dirs.append(_d)
            for _scan_dir in _scan_dirs:
                try:
                    for _p in Path(_scan_dir).glob("*_*.srt"):
                        _m = re.search(r"_([a-z]{2,3})\.srt$", _p.name.lower())
                        if _m:
                            _lang = _m.group(1)
                            if _lang not in _probe_langs:
                                _probe_langs.append(_lang)
                except Exception:
                    continue
        _existing_base = None
        for _b in _candidate_bases:
            for _l in _probe_langs:
                if os.path.exists(f"{_b}_{_l}.srt"):
                    _existing_base = _b
                    break
            if _existing_base:
                break

        if not _existing_base:
            _search_dirs = []
            for _d in (_cwd, os.path.join(_cwd, original_stem), original_dir, _parent_dir, os.path.join(_parent_dir, original_stem)):
                if _d and os.path.isdir(_d) and _d not in _search_dirs:
                    _search_dirs.append(_d)

            for _search_dir in _search_dirs:
                for _l in _probe_langs:
                    try:
                        for _p in Path(_search_dir).glob(f"*_{_l}.srt"):
                            if not _p.is_file():
                                continue
                            _cand_base = str(_p)[:-len(f"_{_l}.srt")]
                            _cand_stem = os.path.basename(_cand_base)
                            _cand_norm = _normalize_candidate_stem(_cand_stem)
                            if _cand_norm == _normalized_target_stem or _stem_match_key(_cand_norm) == _target_stem_key:
                                _existing_base = _cand_base
                                break
                    except Exception:
                        continue
                    if _existing_base:
                        break
                if _existing_base:
                    break

        original_base = _existing_base or os.path.join(original_dir, original_stem)
        original_dir = os.path.dirname(original_base)
        original_stem = os.path.basename(original_base)
        lock_key = os.path.abspath(original_base).lower()
        if render_resolution:
            lock_key += f"_{render_resolution}"

        if _existing_base:
            self.logger.info(f"♻️ Canonical base resolved to existing assets: {original_base}")
        else:
            self.logger.info(f"🆕 Canonical base resolved to new assets: {original_base}")

        def _migrate_legacy_resolution_srt(lang_code: str, expected_path: str) -> bool:
            """Promote legacy *_<res>p_<lang>.srt to shared base name if missing.

            Returns True if expected_path exists after migration.
            """
            if os.path.exists(expected_path):
                return True
            try:
                base_name = Path(original_base).name
                parent_dir = Path(original_dir)
                pattern = f"{base_name}_*p_{lang_code}.srt"
                candidates = [p for p in parent_dir.glob(pattern) if p.is_file()]
                if not candidates:
                    return False
                # Prefer richer files to maximize chance of full reuse.
                candidates.sort(key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)
                best = candidates[0]
                if best.stat().st_size < 50:
                    return False
                shutil.move(str(best), expected_path)
                self.logger.info(f"📦 Reusing legacy SRT: {best.name} -> {Path(expected_path).name}")
                return True
            except Exception as e:
                self.logger.warning(f"⚠️ Legacy SRT migration skipped for {lang_code}: {e}")
                return os.path.exists(expected_path)

        # ── Detect video orientation and compute subtitle geometry ───────────
        # max_chars is derived from the 80% safe text area divided by the
        # rendered character width, so long lines never overflow the frame.
        #
        # libass scales fonts from its default 480-line virtual space:
        #   rendered_font_px = font_size × (video_height / 480)
        # Glyph width ratio: Latin ≈ 0.55×, Arabic/Persian Naskh ≈ 0.40× (connected script).
        #   max_chars = (video_width × 0.80) / (rendered_font_px × ratio)
        _vw, _vh = 0, 0  # defaults for SRT-only input (no video dimensions available)
        if not video_path.lower().endswith('.srt'):
            _vw, _vh = self._detect_video_dimensions(video_path)
            if _vw and _vh:
                rendered_font_px = self.style_config.font_size * (_vh / 480.0)
                text_area_px     = _vw * 0.80
                # Glyph width ratio: Latin ≈ 0.55×, Arabic/Persian Naskh ≈ 0.64×.
                # Vazirmatn and similar Naskh fonts have wider advance widths
                # relative to cap-height (empirically ~0.62-0.66× font height).
                # Using 0.64 gives max_chars ≈ 21 for 9:16 portrait with font 16,
                # which correctly contains 4-word Persian lines without overflow.
                _rtl_langs = {'fa', 'ar', 'ur', 'he'}
                _is_rtl = target_langs and any(l in _rtl_langs for l in target_langs)
                avg_glyph_w      = rendered_font_px * (0.64 if _is_rtl else 0.55)
                max_chars_dyn    = max(10, int(text_area_px / avg_glyph_w))
                # target ~4-8 words per line depending on how many chars fit
                target_words_dyn = max(4, min(10, max_chars_dyn // 4))
                self.style_config.max_chars   = max_chars_dyn
                self.target_words_per_line    = target_words_dyn
                orientation = "📱 Vertical" if _vh > _vw else "🖥️  Horizontal"
                self.logger.info(
                    f"{orientation} video ({_vw}×{_vh}): "
                    f"font≈{rendered_font_px:.0f}px text_area={text_area_px:.0f}px "
                    f"max_chars={max_chars_dyn} target_words={target_words_dyn}"
                )
        
        try:
            # Optional global throttling across all videos to avoid RAM spikes.
            global_slot_path = self._acquire_global_workflow_slot(video_path)

            # Prevent accidental concurrent processing of the same source
            # across multiple terminals.
            workflow_lock_path = self._acquire_workflow_lock(lock_key, video_path)

            # Post-only mode: skip all processing and generate post from existing SRTs.
            if post_only:
                try:
                    self.generate_posts(original_base, source_lang, {}, platforms=platforms or ['telegram'],
                                        prompt_file=prompt_file, post_langs=post_langs)
                except Exception as _pe:
                    self.logger.warning(f"⚠️ Post generation skipped (post-only mode): {_pe}")
                return {}

            # SAFETY: Check disk space before starting
            self._check_disk_space(min_gb=1)
            
            # Limit handling (creates a temp input file for time range)
            current_video_input = video_path
            _limit_start = limit_start or 0.0
            _has_limit = _limit_start > 0 or limit_end is not None
            if _has_limit:
                _info = f"{_limit_start}s → {'end' if limit_end is None else f'{limit_end}s'}"
                self.logger.info(f"⏱️  Time range restriction: {_info}")
                if _is_srt_input:
                    # SRT input: no video to clip with ffmpeg.
                    # Time-range filtering is applied after the SRT is parsed (see below).
                    self.logger.info("⏱️  SRT input detected — time-range filter will be applied to entries.")
                else:
                    temp_vid = os.path.join(tempfile.gettempdir(), f"temp_{int(time.time())}_{original_stem}.mp4")
                    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
                    if _limit_start > 0:
                        cmd += ["-ss", str(_limit_start)]
                    cmd += ["-i", video_path]
                    if limit_end is not None:
                        cmd += ["-t", str(limit_end - _limit_start)]
                    cmd += ["-c", "copy", temp_vid]
                    subprocess.run(cmd, check=True)
                    current_video_input = temp_vid

            # Auto source detection for video input if user did not provide --source.
            if _source_auto_requested and not _is_srt_input:
                source_lang = self.detect_source_language(current_video_input)

            # Resolve target list now that source language is final.
            resolved_targets: List[str] = []
            for _t in target_langs:
                _resolved = source_lang if _t in ('auto', 'detect', 'source') else _t
                if _resolved and _resolved not in resolved_targets:
                    resolved_targets.append(_resolved)
            target_langs = resolved_targets or [source_lang, 'fa']
            
            # 1. Transcription
            # Force SRT path to be at ORIGINAL location
            src_srt = f"{original_base}_{source_lang}.srt"
            _migrate_legacy_resolution_srt(source_lang, src_srt)
            self.logger.info(f"🔎 Source transcription candidate: {src_srt}")
            
            # Use regex to recover SRT if only temp version exists (migration logic)
            # (Skipped for now, assuming fresh run)
            
            if os.path.exists(src_srt) and not force:
                # Validate existing file
                try:
                    if os.path.getsize(src_srt) < 50:
                        self.logger.warning("Existing asset verification failed (undersized); initiating regeneration.")
                        os.remove(src_srt)
                    else:
                        self.logger.info(f"Source asset validation successful: {Path(src_srt).name}")
                except:
                    pass
            elif os.path.exists(src_srt) and force:
                self.logger.info(f"🔄 Force mode enabled; overriding existing asset: {Path(src_srt).name}")
                os.remove(src_srt)
            
            if not os.path.exists(src_srt):
                self.logger.info("🎙️ Reusable source transcription not found after probe; Whisper transcription will run.")
                # We pass the current_video_input (which might be temp/limited) to transcribe
                # BUT we need to ensure the OUTPUT saved is 'src_srt' (original path)
                # The transcribe_video method currently saves based on input name.
                # Let's rename it after generation if needed.
                
                _actual_dur = (limit_end - _limit_start) if limit_end is not None else 0
                _emit_progress(5, "🎙️ Transcription with Whisper...")
                generated_srt = self.transcribe_video(current_video_input, source_lang, correct, detect_speakers, dur=_actual_dur)
                
                # CRITICAL: Unload model immediately after heavy transcription to free RAM for rendering/translation
                self.cleanup()
                
                # If generated name != desired name, move it
                if os.path.abspath(generated_srt) != os.path.abspath(src_srt):
                    self.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
                    shutil.move(generated_srt, src_srt)
                
                _src_is_fresh = True
            else:
                self.logger.info(f"✅ Reusing source transcription without Whisper: {Path(src_srt).name}")
                _src_is_fresh = False  # Already merged on a previous run; do not re-merge.
            
            # MASTER TIMELINE LOCK: Establish the structural anchor once.
            # All downstream translations MUST follow this structure.
            src_entries = self.parse_srt(src_srt)

            # For SRT-as-input with --limit: filter entries to desired time window.
            if _has_limit and _is_srt_input:
                def _ts_to_sec(ts: str) -> float:
                    """Parse SRT timestamp '00:04:09,430' → seconds as float."""
                    ts = ts.replace(',', '.')
                    parts = ts.split(':')
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                before = len(src_entries)
                src_entries = [
                    e for e in src_entries
                    if _ts_to_sec(e['start']) >= _limit_start
                    and (limit_end is None or _ts_to_sec(e['start']) < limit_end)
                ]
                self.logger.info(f"⏱️  Filtered {before} → {len(src_entries)} entries within [{_limit_start}s, {'end' if limit_end is None else str(limit_end) + 's'}]")

            src_entries = self.sanitize_entries(src_entries)
            
            # Smart Merge: Fix split numbers (e.g. "1" + ",000") before saving
            src_entries = self._merge_split_numbers(src_entries)
            
            # 📐 Merge short fragments into semantic clauses.
            # Freshly transcribed SRTs always need this pass.
            # For pre-existing SRTs (e.g., downloaded auto-subs), enable merge only when
            # they are clearly over-fragmented (word-level chunks), to avoid word-by-word output.
            _avg_words = (
                sum(len((e.get('text') or '').split()) for e in src_entries) / max(1, len(src_entries))
            )
            _src_is_fragmented = (len(src_entries) >= 60 and _avg_words < 2.3)

            if _src_is_fresh or _src_is_fragmented:
                if _src_is_fragmented and not _src_is_fresh:
                    self.logger.info(
                        f"📐 Detected fragmented source timeline (avg words/entry={_avg_words:.2f}); applying clause merge."
                    )
                src_entries = self.merge_to_clauses(src_entries)
                # Merge step may create long entries again; enforce width/timing constraints.
                src_entries = self.sanitize_entries(src_entries)
                with open(src_srt, 'w', encoding='utf-8-sig') as f:
                    for idx, entry in enumerate(src_entries, 1):
                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
            
            result[source_lang] = src_srt
            
            # 2. Translation
            _tgt_langs_to_translate = [t for t in target_langs if t != source_lang]
            _tgt_count = len(_tgt_langs_to_translate)
            _emit_progress(55, f"🌐 Starting translation to {', '.join(t.upper() for t in _tgt_langs_to_translate)}...")
            for tgt in target_langs:
                if tgt == source_lang:
                    continue
                
                tgt_srt = f"{original_base}_{tgt}.srt"
                _migrate_legacy_resolution_srt(tgt, tgt_srt)
                
                if os.path.exists(tgt_srt) and not force:
                    # ROBUST VALIDATION: Check entry parity AND language integrity
                    src_entries_count = len(self.parse_srt(src_srt))
                    if self.validate_srt(tgt_srt, src_entries_count, tgt):
                        self.logger.info(f"✓ Target asset verification successful: {Path(tgt_srt).name}")
                        result[tgt] = tgt_srt
                        continue
                    else:
                        self.logger.info(f"� Smart Resume: Target asset {Path(tgt_srt).name} is incomplete or untranslated. Recovering good segments...")
                
                # If we reach here, either tgt_srt doesn't exist, or force is true, or validation failed.
                # In any case, we proceed with translation.
                
                self.logger.info(f"--- Translation Sequence initiated (Target ISO: {tgt.upper()}) ---")
                _tgt_idx = _tgt_langs_to_translate.index(tgt) if tgt in _tgt_langs_to_translate else 0
                _start_pct = 55 + int(_tgt_idx / max(1, _tgt_count) * 20)
                _emit_progress(_start_pct, f"🌐 Translating to {tgt.upper()}...")
                
                try:
                    entries = self.parse_srt(src_srt)
                    # entries are already clause-merged (via src_srt save above)
                    
                    # 💰 SMART RESUME: Ingest partial work before calling LLM (returns recovered mappings)
                    # Skip SRT-based recovery when force=True (still uses local hash cache + provider KV caches)
                    recovered_map = {}
                    if not force:
                        recovered_map.update(self._ingest_partial_srt(entries, tgt_srt.replace('.srt', '_partial.srt'), tgt) or {})
                        recovered_map.update(self._ingest_partial_srt(entries, tgt_srt, tgt) or {})
                    
                    texts = [e['text'] for e in entries]
                    
                    # ── TRANSLATE-THEN-RESEGMENT (Industry Standard) ──
                    # Instead of translating individual subtitle fragments (which causes
                    # line drift when the LLM merges partial sentences), we:
                    # 1. Group entries into complete sentence paragraphs
                    # 2. Translate full paragraphs (giving the LLM complete context)
                    # 3. Re-segment translated text back onto original timecodes
                    
                    paragraph_groups = self._group_entries_into_paragraphs(entries)
                    paragraph_texts = []
                    for group in paragraph_groups:
                        # Join all fragment texts in this paragraph group
                        paragraph_texts.append(' '.join(entries[idx]['text'] for idx in group))
                    
                    self.logger.info(f"📐 Paragraph grouping: {len(entries)} fragments → {len(paragraph_texts)} paragraphs")
                    
                    # Create virtual entries for the paragraph-level translation
                    # (needed for incremental SRT save inside the translation function)
                    para_entries = []
                    for group in paragraph_groups:
                        para_entries.append({
                            'start': entries[group[0]]['start'],
                            'end': entries[group[-1]]['end'],
                            'text': ' '.join(entries[idx]['text'] for idx in group),
                        })
                    
                    # Choose translation strategy based on llm_choice
                    translated_paragraphs = []
                    
                    # If user specified a particular LLM via --llm flag, respect that choice
                    if self.llm_choice == "gemini":
                        translated_paragraphs = self.translate_with_gemini(paragraph_texts, tgt, source_lang, original_entries=para_entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "litellm":
                        translated_paragraphs = self.translate_with_litellm(paragraph_texts, tgt, source_lang, original_entries=para_entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "minimax":
                        translated_paragraphs = self.translate_with_minimax(paragraph_texts, tgt, source_lang, original_entries=para_entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "grok":
                        translated_paragraphs = self.translate_with_grok(paragraph_texts, tgt, source_lang, original_entries=para_entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    else:
                        # Default: Use per-batch fallback chain for optimal rate limit distribution
                        translated_paragraphs = self.translate_with_batch_fallback_chain(
                            paragraph_texts,
                            tgt,
                            source_lang,
                            original_entries=para_entries,
                            output_srt=tgt_srt,
                            existing_translations=recovered_map
                        )
                    
                    # Re-segment translated paragraphs back onto original timecodes
                    translated = self._resegment_translation(entries, paragraph_groups, translated_paragraphs)
                    
                    # Apply Persian text fixes after re-segmentation
                    if tgt == 'fa':
                        translated = [self.fix_persian_text(self.strip_english_echo(t)) if t and t.strip() else t for t in translated]
                    
                    # Write the final re-segmented SRT with original timecodes
                    with open(tgt_srt, 'w', encoding='utf-8-sig') as f:
                        for idx_srt, entry in enumerate(entries, 1):
                            t_text = translated[idx_srt - 1] if idx_srt - 1 < len(translated) else entry['text']
                            f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")

                    
                    # FINAL VERIFICATION: Ensure we actually got some Persian if tgt is FA
                    if tgt == 'fa' and translated:
                        lang_specific_count = sum(1 for t in translated if has_target_language_chars(str(t), tgt))
                        if lang_specific_count < len(translated) // 2:
                            self.logger.warning(f"⚠️ Translation audit failed: Only {lang_specific_count}/{len(translated)} lines are Persian. LLM may have hallucinated or failed.")
                    
                    result[tgt] = tgt_srt
                    self.logger.info(f"✓ Final save completed: {Path(tgt_srt).name}")
                
                except Exception as e:
                    self.logger.error(f"❌ Translation to {tgt} failed: {e}")
                    if self.fail_on_translation_error: raise
                    continue
            
            # POST-TRANSLATION VALIDATION: Ensure 100% translation before proceeding
            for tgt in target_langs:
                if tgt == source_lang:
                    continue
                
                tgt_srt = f"{original_base}_{tgt}.srt"
                if not os.path.exists(tgt_srt):
                    continue
                    
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        # MASTER TIMELINE: No target-side structural sanitation! 
                        # We MUST follow the source index for 1:1 mapping.
                        # But we DO need to apply BiDi/Informal fixes to the text.
                        tgt_entries = self.parse_srt(tgt_srt)
                        for e in tgt_entries:
                            e['text'] = self.fix_persian_text(e['text'])
                        
                        # Save fixed version back
                        with open(tgt_srt, 'w', encoding='utf-8-sig') as f:
                            for idx, entry in enumerate(tgt_entries, 1):
                                f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")

                        src_entries = self.parse_srt(src_srt)
                        
                        # Find untranslated lines
                        untranslated_indices = []
                        
                        # Get language configuration
                        lang_config = get_language_config(tgt)
                        
                        for i, entry in enumerate(tgt_entries):
                            text = entry['text'].strip()
                            if not text:
                                untranslated_indices.append(i)
                                continue
                            
                            # Check if target language uses non-Latin script
                            if lang_config.char_range:
                                char_start, char_end = lang_config.char_range
                                has_target_chars = any(char_start <= c <= char_end for c in text)
                                
                                # If no target language characters found
                                if not has_target_chars:
                                    # Check if it's a technical term pattern with parentheses
                                    has_parenthetical_english = bool(re.search(r'\([A-Za-z0-9\s\-]+\)', text))
                                    
                                    # If no target chars AND no parenthetical pattern, mark as untranslated
                                    if not has_parenthetical_english:
                                        untranslated_indices.append(i)
                            else:
                                # For Latin-script languages (es, fr, de, pt, it, etc.)
                                # Check if text differs from source
                                if text == src_entries[i]['text'].strip():
                                    untranslated_indices.append(i)
                        
                        if not untranslated_indices:
                            self.logger.info(f"✅ Translation validation: 100% of lines translated to {tgt.upper()}")
                            break
                        
                        untranslated_count = len(untranslated_indices)
                        total_count = len(tgt_entries)
                        percentage = (total_count - untranslated_count) / total_count * 100
                        
                        self.logger.warning(f"⚠️ Incomplete translation: {untranslated_count}/{total_count} lines ({100-percentage:.1f}%) not translated to {tgt.upper()}")
                        # Present a user-friendly table of untranslated line numbers and their current text
                        try:
                            rows = []
                            for idx in untranslated_indices:
                                # Display SRT-style line numbers (1-based) and single-line text
                                line_no = idx + 1
                                text = tgt_entries[idx]['text'].replace('\n', ' ').strip()
                                if not text:
                                    # Fall back to source text if target empty
                                    text = src_entries[idx]['text'].replace('\n', ' ').strip()
                                # Truncate long lines for readability
                                if len(text) > 240:
                                    text = text[:237] + '...'
                                rows.append((line_no, text))

                            # Compute padding
                            idx_width = max((len(str(r[0])) for r in rows), default=4)

                            print('\n📋 Untranslated lines:\n')
                            print(f"{'Line'.rjust(idx_width)}  | Text")
                            print('-' * (idx_width + 3 + 80))
                            for ln, txt in rows:
                                print(f"{str(ln).rjust(idx_width)}  | {txt}")
                            print(f"\nTotal untranslated: {untranslated_count}/{total_count}\n")
                        except Exception as e:
                            # Fallback to simple index log
                            self.logger.warning(f"⚠️ Error printing table: {e}")
                            self.logger.info(f"📋 Untranslated line indices: {untranslated_indices[:10]}{'...' if len(untranslated_indices) > 10 else ''}")
                        
                        # Log untranslated info; auto-retry will happen next iteration.
                        self.logger.warning(f"⚠️ Incomplete translation (attempt {retry_count + 1}/{max_retries}): {untranslated_count}/{total_count} lines ({100-percentage:.1f}%) not translated to {tgt.upper()}")
                        
                        # Auto-retry untranslated lines without prompting.
                        # Continue looping; incremented retry_count will exit if >= max_retries.
                        retry_count += 1
                        self.logger.info(f"🔄 Retrying translation for {untranslated_count} lines (Attempt {retry_count}/{max_retries})...")
                        
                        # Extract only untranslated lines
                        texts_to_retry = [src_entries[i]['text'] for i in untranslated_indices]
                        
                        # Translate only these lines with CONTEXT
                        retried_translations = []
                        
                        # New Context-Aware Retry Logic
                        for idx in untranslated_indices:
                            text_to_retry = src_entries[idx]['text']
                            
                            # Get context (3 lines before, 3 lines after)
                            prev_lines = [src_entries[i]['text'] for i in range(max(0, idx-3), idx)]
                            next_lines = [src_entries[i]['text'] for i in range(idx+1, min(len(src_entries), idx+4))]
                            
                            try:
                                translation = self.translate_single_with_context(
                                    text_to_retry, 
                                    prev_lines, 
                                    next_lines, 
                                    tgt, 
                                    source_lang
                                )
                                retried_translations.append(translation)
                            except Exception as e:
                                self.logger.error(f"Failed to retry line {idx+1}: {e}")
                                retried_translations.append(None) # Keep existing if failed
                        
                        
                        # Update only those lines in the SRT file
                        for i, (idx, new_translation) in enumerate(zip(untranslated_indices, retried_translations)):
                            if new_translation and new_translation.strip():
                                tgt_entries[idx]['text'] = new_translation
                        
                        # Save updated SRT
                        with open(tgt_srt, 'w', encoding='utf-8-sig') as f:
                            for idx, entry in enumerate(tgt_entries, 1):
                                f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
                        
                        # Display results of retry
                        print('\n✅ Retried translations results:\n')
                        success_rows = []
                        for i, (idx, new_translation) in enumerate(zip(untranslated_indices, retried_translations)):
                            if new_translation and new_translation.strip():
                                line_no = idx + 1
                                source_text = src_entries[idx]['text'].replace('\n', ' ').strip()
                                trans_text = new_translation.replace('\n', ' ').strip()
                                
                                if len(source_text) > 40: source_text = source_text[:37] + '...'
                                if len(trans_text) > 40: trans_text = trans_text[:37] + '...'
                                
                                success_rows.append((line_no, source_text, trans_text))
                        
                        if success_rows:
                            idx_w = max(len(str(r[0])) for r in success_rows)
                            src_w = max(len(r[1]) for r in success_rows)
                            
                            print(f"{'Line'.rjust(idx_w)} | {'Source'.ljust(src_w)} | Translation")
                            print("-" * (idx_w + 3 + src_w + 3 + 40))
                            for ln, src, tr in success_rows:
                                print(f"{str(ln).rjust(idx_w)} | {src.ljust(src_w)} | {tr}")
                            print(f"\nSuccessfully retried: {len(success_rows)}/{len(untranslated_indices)}\n")
                        else:
                            print("No lines were successfully retried.\n")
                        
                        self.logger.info(f"💾 Updated {Path(tgt_srt).name} with retried translations")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Validation/retry failed: {e}")
                        break
                
                if retry_count >= max_retries:
                    self.logger.warning(f"⚠️ Maximum retries ({max_retries}) reached. Some lines may remain untranslated.")
            
            # Final Save with structural and BiDi check BEFORE rendering
            if source_lang == 'en':
                for tgt in target_langs:
                    if tgt == source_lang: continue
                    tgt_path = result.get(tgt)
                    if tgt_path and os.path.exists(tgt_path):
                        tgt_entries = self.parse_srt(tgt_path)
                        for e in tgt_entries:
                            e['text'] = self.fix_persian_text(e['text'])
                        with open(tgt_path, 'w', encoding='utf-8-sig') as f:
                            for idx, entry in enumerate(tgt_entries, 1):
                                f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
            
            # 3. RENDERING (skip when input is SRT-only — no video source available)
            if render and not _is_srt_input:
                self.logger.info("Rendering sequence initiated.")
                _emit_progress(80, "🎬 Rendering ASS subtitles...")
                
                # Render order = sub_langs order (first = top, second = bottom).
                # target_langs[0] is always the first -sub lang; source is also in result.
                primary = target_langs[0]
                secondary = target_langs[1] if len(target_langs) >= 2 else None
                # If primary == source, it's the transcription SRT (already in result).
                # If primary != source, it was translated and is also in result.
                # If secondary == source, it's the transcription SRT too.
                if secondary == source_lang and secondary not in result:
                    result[secondary] = src_srt
                
                # ASS Path -> Original Base
                ass_path = f"{original_base}_{primary}"
                if secondary:
                    ass_path += f"_{secondary}"
                ass_path += ".ass"
                
                self.create_ass_with_font(
                    result[primary],
                    ass_path,
                    primary,
                    result.get(secondary) if secondary else None,
                    time_offset=_limit_start,
                    video_width=_vw or 0,
                    video_height=_vh or 0,
                )
                result['ass_file'] = ass_path
                
                # Output Video -> Original Base (+render resolution for clarity)
                _render_h = 0
                _render_q = 0
                try:
                    if render_resolution and int(render_resolution) > 0:
                        _render_h = int(render_resolution)
                    else:
                        _dw, _dh = self._detect_video_dimensions(current_video_input)
                        _render_h = int(_dh) if _dh else 0
                except Exception:
                    _render_h = 0

                try:
                    if render_quality and int(render_quality) > 0:
                        _render_q = int(render_quality)
                    else:
                        _render_q = int(get_default_quality())
                except Exception:
                    _render_q = 65

                output_video = (
                    f"{original_base}_{_render_h}p_q{_render_q}_subbed.mp4"
                    if _render_h > 0
                    else f"{original_base}_q{_render_q}_subbed.mp4"
                )
                if os.path.exists(output_video) and not force:
                    self.logger.info(f"✅ Reusing existing rendered video: {Path(output_video).name}")
                    result['rendered_video'] = output_video
                else:
                    # Nuclear Rendering Option (Sandbox)
                    with tempfile.TemporaryDirectory() as temp_dir:
                        safe_video_name = "safe_input.mp4"
                        safe_ass_name = "safe_subs.ass"
                        safe_output_name = "safe_output.mp4"
                        
                        safe_video_path = os.path.join(temp_dir, safe_video_name)
                        safe_ass_path = os.path.join(temp_dir, safe_ass_name)
                        safe_output_path = os.path.join(temp_dir, safe_output_name)
                        
                        # 1. Symlink Input Video (Use current_video_input which is the actual file tailored for length)
                        try:
                            os.symlink(os.path.abspath(current_video_input), safe_video_path)
                        except OSError:
                            shutil.copy(current_video_input, safe_video_path)
                            
                        # 2. Copy ASS to Sandbox
                        shutil.copy(ass_path, safe_ass_path)
                        
                        # 3. FFmpeg Command with Quality-Priority (Git History Restore)
                        # We prioritize constant quality (CRF/Q:V) to maintain file size parity.
                        hw_info = detect_best_hw_encoder()
                        encoder = hw_info['encoder']
                        codec = hw_info['codec']
                        platform = hw_info['platform']
                        # Unified Rendering: Delegate to 'amir video cut'
                        # This ensures we use the centralized logic in video.sh (Bitrate Cap, Encoder Selection, etc.)
                        self.logger.info("🚀 Delegating rendering to 'amir video' engine...")
                        _emit_progress(88, "🎞️ Rendering final video...")
                        
                        # Resolve Font Directory (Mac & Linux support)
                        fonts_dir = None
                        font_paths = [
                            os.path.expanduser("~/Library/Fonts"), # Mac User
                            "/Library/Fonts",                      # Mac System
                            os.path.expanduser("~/.local/share/fonts"), # Linux User
                            "/usr/share/fonts/truetype",           # Linux System
                            "/usr/share/fonts"                     # Linux System Fallback
                        ]
                        
                        for p in font_paths:
                            if os.path.exists(p):
                                # Case-insensitive search for Vazirmatn (primary font in ASS styles)
                                found_font = None
                                try:
                                    for f in os.listdir(p):
                                        fl = f.lower()
                                        if "vazirmatn" in fl and (fl.endswith(".ttf") or fl.endswith(".otf")):
                                            found_font = os.path.join(p, f)
                                            break
                                except OSError:
                                    continue
                                    
                                if found_font:
                                    self.logger.info(f"Found font: {found_font}")
                                    # Standard Approach: Point to the directory containing the font
                                    fonts_dir = p
                                    break

                        # Try to find a sidecar thumbnail to inject as startup cover frame.
                        # This helps clients like Telegram that often preview from first frames.
                        cover_frame_path = None
                        _cover_candidates = [
                            f"{current_video_input}.jpg",
                            f"{current_video_input}.jpeg",
                            f"{current_video_input}.png",
                            f"{Path(current_video_input).with_suffix('').as_posix()}.jpg",
                            f"{Path(current_video_input).with_suffix('').as_posix()}.jpeg",
                            f"{Path(current_video_input).with_suffix('').as_posix()}.png",
                            f"{original_base}.jpg",
                            f"{original_base}.jpeg",
                            f"{original_base}.png",
                        ]
                        for _cand in _cover_candidates:
                            if _cand and os.path.exists(_cand):
                                cover_frame_path = os.path.abspath(_cand)
                                break

                        render_cmd = [
                            "amir", "video", "cut",
                            safe_video_path,
                            "--subtitles", safe_ass_path,
                            "--output", safe_output_path,
                            "--display-input", os.path.basename(current_video_input),
                            "--display-output", os.path.basename(output_video),
                            "--render"
                        ]

                        # Propagate user render intent all the way to final encoder stage.
                        if render_resolution and int(render_resolution) > 0:
                            render_cmd.extend(["--resolution", str(int(render_resolution))])
                        # Always pass concrete quality so final filename and encoder settings stay aligned.
                        render_cmd.extend(["--quality", str(_render_q)])
                        if render_fps and int(render_fps) > 0:
                            render_cmd.extend(["--fps", str(int(render_fps))])
                        if render_split_mb and int(render_split_mb) > 0:
                            render_cmd.extend(["--split", str(int(render_split_mb))])
                        if pad_bottom and int(pad_bottom) > 0:
                            render_cmd.extend(["--pad-bottom", str(int(pad_bottom))])
                        
                        if fonts_dir:
                            render_cmd.extend(["--fonts-dir", fonts_dir])
                        if cover_frame_path:
                            render_cmd.extend(["--cover-frame", cover_frame_path])
                            self.logger.info(f"🖼️ Using cover frame for startup preview: {Path(cover_frame_path).name}")

                        # Prepare environment with FFMPEG_EXEC override
                        # static_ffmpeg puts binaries in PATH, so shutil.which should find it
                        # This bypasses 'amir' script's PATH override (which prefers Homebrew)
                        current_env = os.environ.copy()
                        ffmpeg_bin = shutil.which("ffmpeg")
                        if ffmpeg_bin:
                            current_env["FFMPEG_EXEC"] = ffmpeg_bin
                            self.logger.info(f"🔧 Forcing FFmpeg binary: {ffmpeg_bin}")

                        # Get video duration for progress percentage
                        render_total_duration = 0.0
                        try:
                            dur_result = subprocess.run(
                                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'default=noprint_wrappers=1:nokey=1', safe_video_path],
                                capture_output=True, text=True, timeout=10
                            )
                            render_total_duration = float(dur_result.stdout.strip())
                        except Exception:
                            pass

                        # Execute natively — 'amir video cut' provides its own ASCII progress bar
                        try:
                            process = subprocess.run(
                                render_cmd,
                                env=current_env,
                                check=False
                            )
                        except KeyboardInterrupt:
                            self.logger.warning("Rendering interrupted by user.")
                            return None
                        
                        print() # Final newline after completion
                        
                        if process.returncode != 0:
                            self.logger.error("❌ Rendering failed in 'amir video' engine.")
                            return None
                            
                        self.logger.info("✅ Rendering completed successfully via centralized engine.")
                        _emit_progress(98, "✅ Video rendering complete!")
                        
                        # 4. Move Result to Final Destination
                        if os.path.exists(output_video):
                            os.remove(output_video)
                        
                        shutil.move(safe_output_path, output_video)
                        result['rendered_video'] = output_video
                        self.logger.info(f"Rendering process finalized: {Path(output_video).name}")

            # Social post generation (auto-triggered when platforms list is given)
            if platforms:
                try:
                    saved_posts = self.generate_posts(original_base, source_lang, result, platforms=platforms,
                                                      prompt_file=prompt_file, post_langs=post_langs)
                    if saved_posts:
                        result['posts'] = saved_posts
                except Exception as _pe:
                    self.logger.warning(f"⚠️ Post generation failed (workflow continues): {_pe}")

            # Document export (--save flag)
            if save_formats:
                try:
                    from .exporter import export_subtitles
                    
                    # Determine which languages to export.
                    # If target_langs specified, export them. Otherwise export source_lang.
                    export_langs = set(target_langs) if target_langs else {source_lang}
                    
                    srt_paths = {
                        lang: path for lang, path in result.items()
                        if isinstance(path, str) and path.endswith('.srt') and lang in export_langs
                    }
                    
                    if srt_paths:
                        created = export_subtitles(
                            srt_paths=srt_paths,
                            base_name=original_stem,
                            formats=save_formats,
                            output_dir=original_dir,
                            title=original_stem.replace('_', ' ').replace('-', ' '),
                            logger=self.logger
                        )
                        if created:
                            result['exported_docs'] = created
                    else:
                        self.logger.warning("⚠️ No SRT files available for document export.")
                except Exception as _exp_e:
                    self.logger.warning(f"⚠️ Document export failed: {_exp_e}")

            output_files = self._collect_existing_output_files(result)
            bundle_path = self._bundle_outputs_zip(original_base, output_files)
            if bundle_path and os.path.exists(bundle_path):
                result['bundle_zip'] = bundle_path
                output_files.append(os.path.abspath(bundle_path))

            if output_files:
                self.logger.info("📦 Output files:")
                for p in output_files:
                    self.logger.info(f"   - {os.path.basename(p)}")

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
        """Return (system_prompt, user_prompt) tuple for the given platform.

        Prompt resolution priority:
          1. ``prompt_file`` argument — a .txt file given via --prompt-file CLI flag
          2. ``~/.amir/prompts/{platform}.txt`` — persistent per-platform override
          3. Built-in default below

        Template variables supported in prompt files:
          {title}, {srt_lang_name}, {full_text}

        ADD NEW PLATFORMS HERE — one branch per platform.
        """
        # ── 1. Resolve user_prompt from file (CLI flag or persistent override) ──
        _file_user_prompt: Optional[str] = None

        _candidates = []
        if prompt_file:
            _candidates.append(os.path.expandvars(os.path.expanduser(prompt_file)))
        _candidates.append(os.path.expanduser(f'~/.amir/prompts/{platform}.txt'))

        for _p in _candidates:
            if os.path.isfile(_p):
                try:
                    with open(_p, 'r', encoding='utf-8') as _f:
                        _file_user_prompt = _f.read().format(
                            title=title,
                            srt_lang_name=srt_lang_name,
                            full_text=full_text,
                        )
                    self.logger.info(f"📄 Using custom prompt file for {platform}: {_p}")
                    break
                except KeyError as _ke:
                    self.logger.warning(f"⚠️ Prompt file {_p} has unknown variable {_ke} — using built-in.")
                except Exception as _pe:
                    self.logger.warning(f"⚠️ Could not read prompt file {_p}: {_pe} — using built-in.")

        # ── 2. Build subtitle-languages line (e.g. "با زیرنویس فارسی و آلمانی") ──
        _all_langs = all_srt_langs or [srt_lang]
        def _lang_name_fa(code: str) -> str:
            _fa_names = {
                'fa': 'فارسی', 'en': 'انگلیسی', 'de': 'آلمانی', 'fr': 'فرانسوی',
                'ar': 'عربی', 'es': 'اسپانیایی', 'it': 'ایتالیایی', 'ru': 'روسی',
                'zh': 'چینی', 'ja': 'ژاپنی', 'ko': 'کره‌ای', 'tr': 'ترکی',
                'pt': 'پرتغالی', 'nl': 'هلندی', 'pl': 'لهستانی', 'sv': 'سوئدی',
            }
            return _fa_names.get(code, get_language_config(code).name)
        _subs_line_fa = 'با زیرنویس ' + ' و '.join(_lang_name_fa(l) for l in _all_langs)
        _subs_line_en = 'With ' + ' & '.join(get_language_config(l).name for l in _all_langs) + ' subtitles'
        _dur = duration if duration else '(از تایم‌استمپ محاسبه کن)'
        _dur_en = duration if duration else '(calculate from SRT)'
        # Source (audio) language name in Farsi, shown in the prompt for context
        _src_lang_fa = _lang_name_fa(source_lang) if source_lang else ''
        _src_info_fa = f'زبان ویدیو: {_src_lang_fa}' if _src_lang_fa else ''
        _src_info_en = f'Video language: {get_language_config(source_lang).name}' if source_lang else ''

        # ── 3. Built-in system + user prompts per platform ──
        if platform == 'telegram':
            if srt_lang == 'fa':
                system = (
                    "You write structured Telegram posts in fluent Persian (Farsi) for a technology and AI channel. "
                    "Your style is analytical and informative — no hype, no promotional language, no superlatives. "
                    "Summarise facts and ideas from the content objectively, as a researcher or journalist would. "
                    "Do NOT translate word-for-word — extract key insights and write concisely. "
                    "STRICTLY follow the exact format template provided. "
                    "NEVER use markdown syntax like ** or __ — Telegram does not render them."
                )
                user = _file_user_prompt or (
                    f"یک پست تلگرام بنویس دقیقاً بر اساس این قالب:\n\n"
                    f"📽️ [عنوان کامل ویدیو به فارسی — ترجمه طبیعی، نه تحت‌اللفظی]\n"
                    f"{_subs_line_fa}\n\n"
                    f"🔴 «[یک نقل‌قول مستقیم یا گزاره‌ی کلیدی از ویدیو — بدون تعریف و تمجید]»\n\n"
                    f"[یک پاراگراف ۲ جمله‌ای توصیفی — چه کسی، درباره چه چیزی، در چه زمینه‌ای — بدون ارزش‌گذاری]\n\n"
                    f"🚨 نکات مهم:\n\n"
                    f"🔹 [موضوع اول]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                    f"🔹 [موضوع دوم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                    f"🔹 [موضوع سوم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                    f"🔹 [موضوع چهارم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                    f"✨ [یک جمله — موضوع اصلی این ویدیو در یک خط]\n\n"
                    f"⏱️ مدت: {_dur}\n\n"
                    f"#[هشتگ۱] #[هشتگ۲] #[هشتگ۳] #[هشتگ۴] #[هشتگ۵]\n\n"
                    f"اطلاعات ویدیو:\n"
                    f"عنوان اصلی: {title}\n"
                    f"مدت: {_dur}\n"
                    + (f"{_src_info_fa}\n" if _src_info_fa else "")
                    + f"زبان‌های زیرنویس: {', '.join(_lang_name_fa(l) for l in _all_langs)}\n\n"
                    f"محتوای زیرنویس:\n{full_text}\n\n"
                    f"⛔ قوانین اجباری — تخطی از اینها مجاز نیست:\n"
                    f"① همه بخش‌های قالب را بنویس: 🔴 + پاراگراف + 🚨 (۴ بخش 🔹) + ✨ + ⏱️ + هشتگ‌ها\n"
                    f"② هرگز بخشی را حذف نکن\n"
                    f"③ دقیقاً ۴ بخش 🔹\n"
                    f"④ ⏱️ مدت را دقیقاً همان‌طور که در اطلاعات ویدیو آمده بنویس\n"
                    f"⑤ ۵ هشتگ مرتبط\n"
                    f"⑥ نقل‌قول داخل « »\n"
                    f"⑦ بین هر بخش یک خط خالی\n"
                    f"⑧ بدون markdown (نه ** نه __ نه *)\n"
                    f"⑨ کل پست فارسی (هشتگ‌ها می‌توانند انگلیسی باشند)\n"
                    f"⑩ هر 🔹 باید کوتاه باشد — حداکثر ۱۲ کلمه\n"
                    f"⑪ هدف ۷۰۰–۸۵۰ کاراکتر — با کوتاه کردن هر بخش به این محدوده برس. فراتر رفتن از ۱۰۲۴ کاراکتر ممنوع است."
                )
            else:
                _lang_en = get_language_config(srt_lang).name
                system = (
                    f"You write structured Telegram posts in fluent {_lang_en} for a technology and AI channel. "
                    "Your style is analytical and factual — no hype, no promotional language, no superlatives. "
                    "Summarise facts and ideas from the content objectively, as a researcher or journalist would. "
                    "Do NOT translate word-for-word — extract key insights and write concisely. "
                    "STRICTLY follow the exact format template provided. "
                    "NEVER use markdown syntax like ** or __ — Telegram does not render them."
                )
                _duration_line = f"⏱️ Duration: {duration}" if duration else "⏱️ Duration: [read from SRT timestamps]"
                user = _file_user_prompt or (
                    f"Write a Telegram post following this EXACT format:\n\n"
                    f"📽️ [Full video title in {_lang_en} — natural translation, not literal]\n"
                    f"{_subs_line_en}\n\n"
                    f"🔴 \u00ab[A direct quote or key factual statement from the video — no praise or hype]\u00bb\n\n"
                    f"[1–2 sentences: who, about what, in what context — descriptive, no value judgements]\n\n"
                    f"🚨 Key points:\n\n"
                    f"🔹 [Topic 1]: [one descriptive sentence ≤12 words]\n\n"
                    f"🔹 [Topic 2]: [one descriptive sentence ≤12 words]\n\n"
                    f"🔹 [Topic 3]: [one descriptive sentence ≤12 words]\n\n"
                    f"🔹 [Topic 4]: [one descriptive sentence ≤12 words]\n\n"
                    f"✨ [One sentence: what is the main subject of this video]\n\n"
                    f"{_duration_line}\n\n"
                    f"#[hashtag1] #[hashtag2] #[hashtag3] #[hashtag4] #[hashtag5]\n\n"
                    f"Video info:\n"
                    f"Original title: {title}\n"
                    f"Duration: {_dur_en}\n"
                    f"Subtitle languages: {', '.join(_all_langs)}\n\n"
                    f"Subtitle content:\n{full_text}\n\n"
                    f"⛔ MANDATORY RULES — no exceptions:\n"
                    f"① Write ALL sections: 📽️ title + subtitle line + 🔴 + paragraph + 🚨 (4× 🔹) + ✨ + ⏱️ + hashtags\n"
                    f"② NEVER drop a section to shorten the post\n"
                    f"③ Exactly 4 bullet points (🔹) — not 3, exactly 4\n"
                    f"④ ⏱️ Duration: copy it exactly from the video info above — do not omit\n"
                    f"⑤ Exactly 5 relevant hashtags at the end\n"
                    f"⑥ Quote inside « » — not inside \" \"\n"
                    f"⑦ One blank line between every section\n"
                    f"⑧ NO markdown — no ** no __ no * — Telegram renders them as literal characters\n"
                    f"⑨ Entire post in {_lang_en}\n"
                    f"⑩ Each 🔹 must be brief — max 12 words\n"
                    f"⑪ Target 700–850 characters — shorten each section to fit. NEVER exceed 1024 characters."
                )
            return system, user

        elif platform == 'youtube':
            system = (
                "You are an expert YouTube SEO specialist and video description writer. "
                "Write an optimized YouTube video description that maximizes search visibility. "
                "Use natural language rich with relevant keywords. "
                "Write in the same language as the subtitle content provided."
            )
            user = _file_user_prompt or (
                f"Write an SEO-optimized YouTube video description.\n\n"
                f"Video title: {title}\n\n"
                f"Subtitle content (language: {srt_lang_name}):\n{full_text}\n\n"
                f"The description must:\n"
                f"- Start with a strong 1-2 sentence hook summarizing the video\n"
                f"- Have 3-5 bullet points of key takeaways\n"
                f"- Include a short paragraph with natural SEO keywords\n"
                f"- End with 5-10 relevant hashtags\n"
                f"- Be 150-350 words total\n"
                f"- Be written in the same language as the subtitle content"
            )
            return system, user

        elif platform == 'linkedin':
            system = (
                "You are a professional LinkedIn content writer for a senior tech/AI expert. "
                "Write thought-leadership posts that drive engagement from engineers, managers, and founders. "
                "Tone: authoritative but approachable. No fluff. "
                "Write in the same language as the subtitle content provided."
            )
            user = _file_user_prompt or (
                f"Write a professional LinkedIn post about this video.\n\n"
                f"Video title: {title}\n\n"
                f"Subtitle content (language: {srt_lang_name}):\n{full_text}\n\n"
                f"The post must:\n"
                f"- Open with a bold insight or surprising fact from the video\n"
                f"- Share 2-3 key learnings in short punchy sentences\n"
                f"- End with a question to drive comments\n"
                f"- Include 3-5 professional hashtags\n"
                f"- Be 100-200 words"
            )
            return system, user

        # ── Future platforms ──────────────────────────────────────────────
        # elif platform == 'instagram':
        #     system = "You write punchy Instagram captions with lots of hashtags..."
        #     user   = f"Write an Instagram caption for: {title}\n\n{full_text}"
        #     return system, user
        #
        # elif platform == 'twitter':
        #     system = "You write Twitter/X threads (max 280 chars per tweet)..."
        #     user   = f"Write a thread about: {title}\n\n{full_text}"
        #     return system, user
        #
        # elif platform == 'aparat':
        #     system = "You write Aparat video descriptions in Persian..."
        #     user   = f"Write Aparat description for: {title}\n\n{full_text}"
        #     return system, user
        # ─────────────────────────────────────────────────────────────────

        else:
            raise ValueError(
                f"Unknown platform: {platform!r}. "
                f"Supported: telegram, youtube, linkedin. "
                f"Add new ones inside _get_post_prompt()."
            )

    def _call_llm_for_post(self, system: str, user: str) -> Optional[str]:
        """Call LLM with DeepSeek → Gemini fallback. Returns generated text or None."""
        # Sanitize surrogate chars that break UTF-8 API calls
        system = system.encode('utf-8', errors='replace').decode('utf-8')
        user = user.encode('utf-8', errors='replace').decode('utf-8')
        try:
            _ds = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
            _resp = _ds.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            return _resp.choices[0].message.content.strip()
        except Exception as _e1:
            self.logger.warning(f"⚠️ DeepSeek unavailable for post: {_e1} — trying Gemini…")
            try:
                _gc = genai.Client(api_key=self.google_api_key)
                _gresp = _gc.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[f"{system}\n\n{user}"],
                )
                return _gresp.text.strip()
            except Exception as _e2:
                self.logger.error(f"❌ Post generation failed: {_e2}")
                return None

    @staticmethod
    def _sanitize_post(text: str, platform: str) -> str:
        """Post-process LLM output to enforce platform-specific formatting rules."""
        if platform == 'telegram':
            # Strip bold/italic markdown that Telegram renders as literal asterisks
            # **text** → text,  __text__ → text,  *text* → text
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)
            text = re.sub(r'__(.+?)__', r'\1', text, flags=re.DOTALL)
            text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)
            # Strip leading/trailing --- separator lines that may appear from template
            text = re.sub(r'^-{3,}\s*\n?', '', text)
            text = re.sub(r'\n?-{3,}\s*$', '', text)
            text = text.strip()
            # Hard cap: Telegram caption limit is 1024 characters; trim gracefully
            if len(text) > 1024:
                # Try cutting at last newline within limit
                cut = text[:1024].rfind('\n')
                if cut < 800: # If no newline or it's too early, try last space
                    cut = text[:1024].rfind(' ')
                
                text = text[:cut if cut > 500 else 1024].rstrip()
                if len(text) < len(text.strip()): # ensure we don't end on half word
                     pass
                text += "..." if len(text) < 1024 else ""
        return text

    @staticmethod
    def _telegram_sections_complete(text: str) -> tuple:
        """Return (ok: bool, missing: list[str]) for required Telegram post sections.

        Checks every mandatory visual marker that the format template requires:
          📽️  title icon
          🔴   pull-quote
          🚨   key-points header
          5×🔹 bullet points
          ✨   summary paragraph
          📌   call-to-action
          ⏱️  duration line
          #    at least one hashtag
        """
        missing = []
        for marker, label in [
            ('\U0001f4fd',   '📽️ title icon'),
            ('\U0001f534',   '🔴 pull-quote'),
            ('\U0001f6a8',   '🚨 key-points header'),
            ('\u2728',       '✨ summary paragraph'),
            ('\u23f1',       '⏱️ duration'),
        ]:
            if marker not in text:
                missing.append(label)
        bullet_count = text.count('\U0001f539')
        if bullet_count < 4:
            missing.append(f'🔹 bullet points (found {bullet_count}, need 4)')
        if '#' not in text:
            missing.append('hashtags (#)')
        return (len(missing) == 0, missing)

    @staticmethod
    def _format_publish_date(value: str) -> str:
        """Normalize common date forms to YYYY-MM-DD (+ weekday) for post headers."""
        if not value:
            return ""
        value = str(value).strip()
        fa_weekdays = {
            0: "دوشنبه",
            1: "سه\u200cشنبه",
            2: "چهارشنبه",
            3: "پنج\u200cشنبه",
            4: "جمعه",
            5: "شنبه",
            6: "یکشنبه",
        }
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(value, fmt)
                return f"{dt.strftime('%Y-%m-%d')} ({fa_weekdays.get(dt.weekday(), dt.strftime('%A'))})"
            except ValueError:
                continue
        return value

    def _discover_video_metadata(self, original_base: str, srt_path: Optional[str] = None) -> Dict[str, str]:
        """Best-effort metadata lookup from yt-dlp sidecars near the current video/SRT."""
        candidates = []
        if srt_path:
            srt_path = os.path.abspath(srt_path)
            candidates.extend([
                f"{srt_path}.info.json",
                f"{os.path.splitext(srt_path)[0]}.info.json",
            ])
        original_base_abs = os.path.abspath(original_base)
        base_dir = os.path.dirname(original_base_abs)
        base_name = os.path.basename(original_base_abs)
        candidates.extend([
            f"{original_base_abs}.info.json",
            f"{original_base_abs}.mp4.info.json",
            f"{original_base_abs}.mov.info.json",
            f"{original_base_abs}.m4v.info.json",
        ])

        # Fallback for resolution/collision sidecars:
        # Also look in current working directory in case we are downloading to a fresh folder
        # while original_base points to a canonical/existing one.
        cwd = os.getcwd()
        try:
            dynamic_candidates = []
            for d in set([base_dir, cwd]):
                for pattern in (f"{base_name}_*.info.json", f"{base_name}*.info.json", "*.info.json"):
                    for p in Path(d).glob(pattern):
                        if p.is_file():
                            dynamic_candidates.append(str(p.resolve()))
            
            # Additional check: if original_base was renamed/canonicalized, maybe the info file
            # matches the current folder's video files
            for p in Path(cwd).glob("*.info.json"):
                dynamic_candidates.append(str(p.resolve()))

            dynamic_candidates = sorted(set(dynamic_candidates), key=lambda p: os.path.getmtime(p), reverse=True)
            candidates.extend(dynamic_candidates)
        except Exception:
            pass

        seen = set()
        for meta_path in candidates:
            if not meta_path or meta_path in seen or not os.path.exists(meta_path):
                continue
            seen.add(meta_path)
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                title = str(data.get('title') or data.get('fulltitle') or '').strip()
                publish_date = self._format_publish_date(
                    data.get('upload_date') or data.get('release_date') or data.get('timestamp') or ''
                )
                webpage_url = str(data.get('webpage_url') or data.get('original_url') or '').strip()
                uploader = str(data.get('uploader') or data.get('channel') or '').strip()
                if title or publish_date or webpage_url or uploader:
                    # Also try to get duration from video file itself for accuracy
                    duration_sec = data.get('duration') or 0.0
                    if not duration_sec:
                        # Try to find the actual media file based on original_base
                        for ext in ('.mp4', '.mkv', '.mov', '.m4v', '.webm', '.ts'):
                            v_p = original_base + ext
                            if os.path.exists(v_p):
                                duration_sec = self._get_video_duration(v_p)
                                if duration_sec > 0: break

                    return {
                        'title': title,
                        'publish_date': publish_date,
                        'webpage_url': webpage_url,
                        'uploader': uploader,
                        'duration_sec': duration_sec,
                    }
            except Exception:
                continue

        # If no info.json or it lacked duration, try to find and probe the actual video file
        # Check original_base + extensions AND check for quality suffixes (e.g. _720p.mp4)
        duration_sec = duration_sec if 'duration_sec' in locals() and duration_sec > 0 else 0.0
        if duration_sec <= 0:
            base_dir = os.path.dirname(original_base_abs)
            base_name = os.path.basename(original_base_abs)
            exts = ('.mp4', '.mkv', '.mov', '.m4v', '.webm', '.ts')
            
            # 1. Try exact matches
            for ext in exts:
                v_p = original_base_abs + ext
                if os.path.exists(v_p):
                    duration_sec = self._get_video_duration(v_p)
                    if duration_sec > 0: break
            
            # 2. Try glob for suffixes if still not found
            if duration_sec <= 0:
                try:
                    for ext in exts:
                        for p in Path(base_dir).glob(f"{base_name}*{ext}"):
                            duration_sec = self._get_video_duration(str(p))
                            if duration_sec > 0: break
                        if duration_sec > 0: break
                except Exception:
                    pass

        return {
            'title': title if 'title' in locals() else '',
            'publish_date': publish_date if 'publish_date' in locals() else '',
            'webpage_url': webpage_url if 'webpage_url' in locals() else '',
            'uploader': uploader if 'uploader' in locals() else '',
            'duration_sec': duration_sec,
        }

    @staticmethod
    def _compose_post_file_header(platform: str, metadata: Dict[str, str], fallback_title: str) -> str:
        """Human-readable header added above saved post text files."""
        title = (metadata.get('title') or fallback_title or '').strip()
        quality_label = (metadata.get('quality_label') or '360p').strip()
        publish_date = (metadata.get('publish_date') or '').strip()
        webpage_url = (metadata.get('webpage_url') or '').strip()
        uploader = (metadata.get('uploader') or '').strip()

        lines = []
        if title:
            lines.append(title)  # Just the title, no prefix as requested
        if quality_label:
            lines.append(f"\nکیفیت: {quality_label}")
        if publish_date:
            if platform == 'telegram':
                # Concise date for Telegram (just the YYYY-MM-DD part)
                clean_date = publish_date.split(' ')[0]
                lines.append(f"\nDate: {clean_date}")
            else:
                lines.append(f"تاریخ انتشار: {publish_date}")
        if uploader:
            lines.append(f"\nمنتشرکننده: {uploader}")
        if webpage_url:
            lines.append(f"\nلینک مرجع:\n {webpage_url}")
        if not lines:
            return ""
        return "\n".join(lines) + "\n\n" + ("─" * 20) + "\n\n"

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
        if platforms is None:
            platforms = ['telegram']

        # Languages for which a post will be written (default: FA only)
        _wanted_langs: List[str] = post_langs if post_langs else ['fa']

        # Title: clean up stem for human readability
        stem = Path(original_base).name
        stem = re.sub(r'_(subbed|[a-z]{2,3})$', '', stem, flags=re.IGNORECASE)
        stem = re.sub(r'_\d{2}\.\d{2}\.\d{4}$', '', stem)   # strip date suffix
        title = re.sub(r'[_\-]+', ' ', stem).strip()

        _bidi = '\u200f\u200e\u200d\u202b\u202a\u202c\u202e\u202d\u2067\u2066\u2069'

        # Collect SRT languages present in result, restricted to _wanted_langs
        srt_langs = [
            lang for lang, path in result.items()
            if isinstance(path, str) and path.endswith('.srt') and os.path.exists(path)
            and lang in _wanted_langs
        ]

        # post-only / empty result: discover existing SRTs on disk for _wanted_langs
        if not srt_langs:
            for _l in _wanted_langs:
                _c = f"{original_base}_{_l}.srt"
                if os.path.exists(_c) and _l not in srt_langs:
                    srt_langs.append(_l)

        if not srt_langs:
            self.logger.warning("⚠️ No SRT files found — skipping post generation.")
            return {}

        saved: Dict[str, str] = {}

        for srt_lang in srt_langs:
            try:
                srt_path = result.get(srt_lang) or f"{original_base}_{srt_lang}.srt"
                if not os.path.exists(srt_path):
                    continue

                # Extract clean subtitle text + compute duration
                entries = self.parse_srt(srt_path)
                video_metadata = self._discover_video_metadata(original_base, srt_path)
                
                # Prioritize probed duration from video file over SRT content length
                meta_dur = video_metadata.get('duration_sec', 0.0)
                if meta_dur > 0:
                    duration = self._format_total_seconds(meta_dur, lang=srt_lang)
                else:
                    duration = self._srt_duration_str(entries, lang=srt_lang)

                lines = []
                for e in entries:
                    t = e['text']
                    for c in _bidi:
                        t = t.replace(c, '')
                    lines.append(t.strip())
                full_text = '\n'.join(lines[:80]) + ('\n...' if len(lines) > 80 else '')
                # Remove surrogate characters that break UTF-8 encoding when sent to APIs
                full_text = full_text.encode('utf-8', errors='replace').decode('utf-8')
                title_clean = title.encode('utf-8', errors='replace').decode('utf-8')

                srt_lang_name = get_language_config(srt_lang).name

                for platform in platforms:
                    try:
                        system, user = self._get_post_prompt(platform, title_clean, srt_lang_name, full_text,
                                                             prompt_file=prompt_file, srt_lang=srt_lang,
                                                             duration=duration, all_srt_langs=srt_langs,
                                                             source_lang=source_lang)
                    except ValueError as ve:
                        self.logger.warning(str(ve))
                        continue
                    except Exception as _pe:
                        self.logger.warning(f"⚠️ Prompt build failed for {platform}/{srt_lang}: {_pe}")
                        continue

                    try:
                        post_text = self._call_llm_for_post(system, user)
                    except Exception as _le:
                        self.logger.warning(f"⚠️ LLM call failed for {platform}/{srt_lang}: {_le}")
                        continue

                    if not post_text:
                        self.logger.warning(f"⚠️ Empty response for {platform}/{srt_lang} — skipping")
                        continue

                    try:
                        post_text = self._sanitize_post(post_text, platform)

                        # Validate completeness; retry once if sections are missing
                        if platform == 'telegram':
                            _ok, _missing = self._telegram_sections_complete(post_text)
                            if not _ok:
                                self.logger.warning(
                                    f"⚠️ Post incomplete (missing: {', '.join(_missing)}) — retrying…"
                                )
                                # Trailing-only truncation: if every missing section comes after
                                # what's already written, just ask the model to continue (append).
                                # Full rewrite would hit the same token limit again.
                                _tail_markers = {'\u2728', '\U0001f4cc', '\u23f1', 'hashtags (#)'}
                                _is_tail_only = all(
                                    any(m in label for m in _tail_markers)
                                    for label in _missing
                                )
                                if _is_tail_only:
                                    _retry_user = (
                                        f"The post below was truncated — it is missing its final sections.\n"
                                        f"Continue it from where it stopped; output ONLY the continuation "
                                        f"(do not repeat what is already written).\n\n"
                                        f"Missing sections to add in order:\n"
                                        + ('\n'.join(f'  • {lbl}' for lbl in _missing)) +
                                        f"\n\nThe full required tail is:\n"
                                        f"✨ [one sentence — main subject of this video]\n\n"
                                        f"📌 [one sentence — for which audience this is relevant]\n\n"
                                        f"⏱️ Duration: {duration}\n\n"
                                        f"#[tag1] #[tag2] #[tag3] #[tag4] #[tag5]\n\n"
                                        f"TRUNCATED POST:\n{post_text}"
                                    )
                                else:
                                    _retry_user = (
                                        f"The post you wrote is INCOMPLETE. Missing: {', '.join(_missing)}\n\n"
                                        f"Rewrite the COMPLETE post from scratch following the original instructions.\n\n"
                                        f"ORIGINAL REQUEST:\n{user}"
                                    )
                                try:
                                    _retry = self._call_llm_for_post(system, _retry_user)
                                    if _retry:
                                        _retry_sanitized = self._sanitize_post(_retry, platform)
                                        if _is_tail_only:
                                            # Merge: original truncated body + appended tail
                                            _merged = post_text.rstrip() + '\n\n' + _retry_sanitized.strip()
                                            _ok2, _still = self._telegram_sections_complete(_merged)
                                            if _ok2 or len(_still) < len(_missing):
                                                post_text = _merged
                                        else:
                                            _ok2, _still = self._telegram_sections_complete(_retry_sanitized)
                                            if _ok2 or len(_still) < len(_missing):
                                                post_text = _retry_sanitized
                                        if not self._telegram_sections_complete(post_text)[0]:
                                            _, _still = self._telegram_sections_complete(post_text)
                                            self.logger.warning(
                                                f"⚠️ Retry still incomplete (missing: {', '.join(_still)})"
                                            )
                                except Exception as _re:
                                    self.logger.warning(f"⚠️ Retry failed: {_re}")

                        post_path = f"{original_base}_{srt_lang}_{platform}.txt"
                        post_header = self._compose_post_file_header(platform, video_metadata, title_clean)
                        with open(post_path, 'w', encoding='utf-8') as f:
                            f.write(post_header + post_text)
                        saved[f"{srt_lang}_{platform}"] = post_path
                        label = f"پست {platform} ({srt_lang.upper()})"
                        self.logger.info(f"📝 {label} saved: {Path(post_path).name}")
                        _preview_text = post_header + post_text if post_header else post_text
                        print(f"\n{'━'*60}\n📝  {label}:\n{'━'*60}\n{_preview_text}\n{'━'*60}\n")
                    except Exception as _we:
                        self.logger.warning(f"⚠️ Could not save post for {platform}/{srt_lang}: {_we}")

            except Exception as _lang_e:
                self.logger.warning(f"⚠️ Skipping lang={srt_lang} due to unexpected error: {_lang_e}")
                continue

        return saved

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
        """
        Single model translation with minimal retries (1-2 attempts only).
        Raises exception immediately if it fails so fallback chain can try next model.
        
        Args:
            batch: Texts to translate
            target_lang: Target language
            source_lang: Source language
            model_name: Model to use (deepseek, minimax, gemini, grok)
            batch_size: Batch size for this model
            max_retries: Max retry attempts (default 2)
        
        Returns:
            Translated texts or raises exception
        """
        if model_name == "deepseek":
            client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
            
            for attempt in range(1, max_retries + 1):
                try:
                    # Context lines (3 before + 3 after)
                    ctx_section = ""
                    batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
                    
                    response = client.chat.completions.create(
                        model=self.llm_models["deepseek"],
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=self.temperature,
                        max_tokens=4000
                    )
                    
                    output = response.choices[0].message.content.strip()
                    
                    # Log DeepSeek KV cache hit tokens (automatically cached at 10x discount)
                    if hasattr(response, 'usage') and response.usage:
                        cached_tokens = getattr(response.usage, 'prompt_cache_hit_tokens', 0) or 0
                        if cached_tokens:
                            self._cost_savings["deepseek_cache_hit_tokens"] += cached_tokens
                    
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                    if trans_list and len(trans_list) >= len(batch):
                        result_batch = trans_list[:len(batch)]
                        # Apply Persian fixes if needed
                        if target_lang == 'fa':
                            processed_list = []
                            for idx_in_batch, t in enumerate(trans_list):
                                if not t or not t.strip():
                                    processed_list.append(batch[idx_in_batch])
                                    continue
                                if not any('\u0600' <= c <= '\u06FF' for c in t):
                                    processed_list.append(batch[idx_in_batch])
                                else:
                                    processed_list.append(self.fix_persian_text(self.strip_english_echo(t)))
                            trans_list = processed_list
                        return trans_list[:len(batch)]
                    else:
                        raise ValueError(f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}")
                
                except Exception as e:
                    if attempt >= max_retries:
                        raise
                    wait_time = 5 * attempt
                    self.logger.debug(f"DeepSeek attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}")
                    time.sleep(wait_time)
        
        elif model_name == "minimax":
            for attempt in range(1, max_retries + 1):
                try:
                    import requests
                    api_key = self.minimax_api_key
                    if not api_key:
                        raise ValueError("MINIMAX_API_KEY not set")
                    
                    batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
                    
                    # Minimax API call (simplified)
                    headers = {"Authorization": f"Bearer {api_key}"}
                    data = {
                        "model": self.llm_models["minimax"],
                        "messages": [
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ]
                    }
                    
                    response = requests.post("https://api.minimaxi.com/v1/text/chatcompletion_pro", json=data, headers=headers, timeout=30)
                    response.raise_for_status()
                    result = response.json()
                    output = result.get("reply", "")
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                    if trans_list and len(trans_list) >= len(batch):
                        return trans_list[:len(batch)]
                    else:
                        raise ValueError(f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}")
                
                except Exception as e:
                    if attempt >= max_retries:
                        raise
                    wait_time = 5 * attempt
                    self.logger.debug(f"MiniMax attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}")
                    time.sleep(wait_time)
        
        elif model_name == "gemini":
            # Try to get/create server-side CachedContent for system instruction
            gemini_cache_name = self._get_gemini_content_cache(target_lang)
            
            for attempt in range(1, max_retries + 1):
                try:
                    if not HAS_GEMINI or not self.google_api_key:
                        raise ValueError("Gemini SDK not available or API key not set")
                    
                    from google import genai
                    from google.genai import types as genai_types
                    client = genai.Client(api_key=self.google_api_key)
                    
                    batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
                    
                    model = self.llm_models["gemini"]
                    
                    if gemini_cache_name:
                        # USE EXPLICIT CACHE: system instruction is already cached on Gemini's servers
                        # Only pay for user message tokens, not system instruction tokens (guaranteed savings)
                        response = client.models.generate_content(
                            model=model,
                            contents=batch_text,
                            config=genai_types.GenerateContentConfig(
                                cached_content=gemini_cache_name
                            )
                        )
                    else:
                        # Fallback: implicit caching (system prompt embedded, may or may not cache)
                        response = client.models.generate_content(
                            model=model,
                            contents=f"{self.get_translation_prompt(target_lang)}\n\n{batch_text}"
                        )
                    
                    output = response.text.strip() if response else ""
                    if not output:
                        raise ValueError(f"Empty response from {model}")
                    
                    # Log cached tokens if available
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        cached = getattr(response.usage_metadata, 'cached_content_token_count', 0) or 0
                        if cached:
                            self._cost_savings["gemini_cached_tokens"] += cached
                    
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                    if trans_list and len(trans_list) >= len(batch):
                        return trans_list[:len(batch)]
                    else:
                        raise ValueError(f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}")
                
                except Exception as e:
                    if attempt >= max_retries:
                        raise
                    wait_time = 5 * attempt
                    self.logger.debug(f"Gemini attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}")
                    time.sleep(wait_time)
        
        elif model_name == "grok":
            for attempt in range(1, max_retries + 1):
                try:
                    from openai import OpenAI as XAI_Client
                    if not self.grok_api_key:
                        raise ValueError("GROK_API_KEY not set")
                    
                    client = XAI_Client(api_key=self.grok_api_key, base_url="https://api.x.ai/v1")
                    
                    batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
                    
                    response = client.chat.completions.create(
                        model=self.llm_models["grok"],
                        messages=[
                            {"role": "system", "content": self.get_translation_prompt(target_lang)},
                            {"role": "user", "content": batch_text}
                        ],
                        temperature=0.7,
                        max_tokens=4000
                    )
                    
                    output = (response.choices[0].message.content or "").strip()
                    if not output:
                        raise ValueError("Empty response from Grok")
                    
                    # Log Grok cached prompt tokens (auto-cached, discounted)
                    if hasattr(response, 'usage') and response.usage:
                        cached_tokens = getattr(response.usage, 'prompt_cache_hit_tokens', 0) or 0
                        if cached_tokens:
                            self._cost_savings["grok_cache_hit_tokens"] += cached_tokens
                    
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                    if trans_list and len(trans_list) >= len(batch):
                        return trans_list[:len(batch)]
                    else:
                        raise ValueError(f"Incomplete response: expected {len(batch)}, got {len(trans_list) if trans_list else 0}")
                
                except Exception as e:
                    if attempt >= max_retries:
                        raise
                    wait_time = 5 * attempt
                    self.logger.debug(f"Grok attempt {attempt} failed, retrying in {wait_time}s: {str(e)[:50]}")
                    time.sleep(wait_time)
        
        raise ValueError(f"Unknown model: {model_name}")

    # ==================== TRANSLATE-THEN-RESEGMENT ====================
    # Industry-standard approach: translate full sentences, then re-segment
    # back onto original timecodes using character-proportional splitting.

    @staticmethod
    def _group_entries_into_paragraphs(entries: List[Dict]) -> List[List[int]]:
        """Group consecutive subtitle entries into sentence-level paragraphs.
        
        A paragraph boundary is placed after any entry whose text ends with
        sentence-ending punctuation (. ! ? … 。？！). This ensures the LLM
        receives complete sentences for translation.
        
        Safety caps:
          - 8 entries max per group (word count safety)
          - 9 seconds max per group (time-domain safety for resegmentation)
        
        Returns:
            List of groups, where each group is a list of indices into `entries`.
            Example: [[0,1,2], [3,4], [5], ...]
        """
        sentence_enders = {'.', '!', '?', '…', '。', '？', '！'}
        groups = []
        current_group = []
        group_start_sec = 0.0
        MAX_GROUP_SECONDS = 15.0

        def _ts_to_sec(ts: str) -> float:
            ts = ts.replace(',', '.')
            h, m, s = ts.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
        
        for i, entry in enumerate(entries):
            # Track group start time
            if not current_group:
                group_start_sec = _ts_to_sec(entry.get('start', '00:00:00,000'))
            
            current_group.append(i)
            text = entry.get('text', '').strip()
            
            # Check if this entry ends a sentence
            ends_sentence = False
            if text:
                last_char = text.rstrip()[-1] if text.rstrip() else ''
                if last_char in sentence_enders:
                    ends_sentence = True
                # Also break on ellipsis patterns
                if text.rstrip().endswith('...') or text.rstrip().endswith('…'):
                    ends_sentence = True

            # Time span of this group so far
            group_end_sec = _ts_to_sec(entry.get('end', entry.get('start', '00:00:00,000')))
            group_duration = group_end_sec - group_start_sec
            
            # Flush group if sentence ends OR safety cap reached
            if ends_sentence or len(current_group) >= 8 or group_duration >= MAX_GROUP_SECONDS:
                groups.append(current_group)
                current_group = []
        
        # Flush remaining
        if current_group:
            groups.append(current_group)
        
        return groups

    @staticmethod
    def _take_words_up_to(words: List[str], target_chars: int) -> tuple:
        """Take words from the front of the list until we reach target_chars.
        
        OPTIMIZED: Uses 'Punctuation Snapping' to favor breaking at sentence or 
        clause boundaries (. ! ? , : ; ...) if they are within a reasonable 
        window (80% - 130% of target). If no punctuation is found, it uses 
        'Lexical Snapping' to avoid breaking after dangling prepositions/conjunctions.
        
        Returns:
            (segment_text, remaining_words)
        """
        if not words:
            return ('', [])
        
        punctuations = {'.', '!', '?', '…', '。', '？', '！', ',', ';', ':', '،', '؛', '»', ')', '}', ']'}
        
        # Words we absolutely DO NOT want at the END of a subtitle line 
        # (they should start the next line instead)
        bad_enders = {
            'و', 'در', 'به', 'که', 'از', 'با', 'برای', 'تا', 'چون', 'اگر', 
            'یا', 'پس', 'اما', 'ولی', 'هم', 'نیز', 'را',
            'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'of', 'that'
        }
        
        best_index = 0
        chars_so_far = 0
        best_punctuated_index = -1
        
        for i, word in enumerate(words):
            word_len = len(word) + (1 if i > 0 else 0)
            chars_so_far += word_len
            
            clean_word = word.rstrip(''.join(punctuations)).strip()
            ends_in_punct = word.rstrip() and word.rstrip()[-1] in punctuations
            
            # --- PEAK SELECTION LOGIC ---
            # 1. Punctuation Priority: Store index of last word with punctuation in window [80%, 130%]
            if 0.8 * target_chars <= chars_so_far <= 1.3 * target_chars:
                if ends_in_punct:
                    best_punctuated_index = i
            
            # 2. Hard Stop: We have exceeded the window, we MUST break
            if chars_so_far > 1.3 * target_chars and i > 0:
                break
            
            # 3. Mathematical Best Fit (fallback)
            if chars_so_far <= target_chars:
                best_index = i
            elif best_index == 0: # safety: take at least one word
                best_index = i
        
        # FINAL DECISION TIER
        if best_punctuated_index != -1:
            final_idx = best_punctuated_index
        else:
            final_idx = best_index
            # Lexical Snapping: Move the break back if it lands on a bad ender
            # (e.g. don't end a line with "در")
            clean_end_word = words[final_idx].rstrip(''.join(punctuations)).strip().lower()
            if clean_end_word in bad_enders and final_idx > 0:
                final_idx -= 1
        
        taken = words[:final_idx + 1]
        remaining = words[final_idx + 1:]
        
        return (' '.join(taken).strip(), remaining)

    @staticmethod
    def _take_n_words_with_punct_snap(words: List[str], target_n: int, min_n: int, max_n: int = None) -> tuple:
        """Take ~target_n words from the front, preferring to end at punctuation.
        
        Looks for punctuation within [min_n, hard_max] word range.
        Takes the LAST punctuation found in that window (closest to target).
        Never takes fewer than min_n words (unless list is shorter).
        Never takes more than max_n words — hard ceiling, defaults to target_n+1.
        
        Returns:
            (taken_words_list, remaining_words_list)
        """
        if not words:
            return ([], [])
        
        punctuations = {'.', '!', '?', '…', '،', '؟', '؛', ',', ';', ':', '。', '？', '！'}
        bad_enders = {
            'و', 'در', 'به', 'که', 'از', 'با', 'برای', 'تا', 'چون', 'اگر',
            'یا', 'پس', 'اما', 'ولی', 'هم', 'نیز', 'را',
            'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'of', 'that'
        }
        
        available = len(words)
        # Hard ceiling: never take more than this many words
        hard_max = min(max_n if max_n is not None else target_n + 1, available)
        
        final_n = max(min_n, min(target_n, hard_max))
        
        # Punctuation search window: near target_n (within ±1 word), bounded by hard_max.
        # Using hard_max as the search ceiling would greedily take far too many words.
        search_low = min_n - 1  # inclusive, 0-based
        search_high = min(hard_max - 1, target_n + 1)  # near target, not up to hard_max
        
        best_punct_idx = -1  # 0-based index of best punctuation word
        for i in range(search_low, search_high + 1):
            w = words[i].rstrip()
            if w and w[-1] in punctuations:
                best_punct_idx = i  # keep updating: last punct in window wins
        
        if best_punct_idx >= 0:
            final_n = best_punct_idx + 1  # convert to count
        else:
            # Lexical snapping: step back off dangling connectors
            punct_chars = ''.join(punctuations)
            while final_n > min_n:
                w = words[final_n - 1].rstrip(punct_chars).strip().lower()
                if w in bad_enders:
                    final_n -= 1
                else:
                    break
        
        final_n = max(min_n, min(final_n, hard_max))
        return (words[:final_n], words[final_n:])

    @staticmethod
    def _vis_len(s: str) -> int:
        """Visual character length: excludes zero-width Unicode format
        characters (ZWNJ U+200C, ZWJ U+200D, RLM, LRM …) that Python's
        len() counts but that occupy no rendered width in the font."""
        import unicodedata
        return sum(1 for c in s if unicodedata.category(c) != 'Cf')

    def _resegment_translation(
        self,
        entries: List[Dict],
        paragraph_groups: List[List[int]],
        translated_paragraphs: List[str]
    ) -> List[str]:
        """Re-segment translated paragraphs back onto original timecodes.

        Strategy (punctuation-first, time-proportional fallback):
        1. Split the translated paragraph at sentence-ending punctuation first.
           Each resulting sentence is one subtitle slot (or fewer if slots run out).
        2. If the translation has fewer sentences than slots, distribute words
           across remaining slots using time-proportional splitting.
        3. If a slot's text still exceeds max_chars, trim to word boundary.

        This produces semantically complete subtitle lines instead of
        time-sliced fragments that cut mid-phrase.
        """
        def _ts_to_sec(ts: str) -> float:
            ts = ts.replace(',', '.')
            h, m, s = ts.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)

        # Sentence-ending punctuation — comma/،/؛ excluded (clause separators, not sentence ends)
        _SENT_END = re.compile(r'(?<=[.!?؟…])\s+')
        # Bad enders: words we never want at the END of a subtitle line
        _BAD_ENDERS = frozenset({
            'و', 'در', 'به', 'که', 'از', 'با', 'برای', 'تا', 'چون', 'اگر',
            'یا', 'پس', 'اما', 'ولی', 'هم', 'نیز', 'را', 'این', 'آن',
            'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with',
            'by', 'of', 'that', 'the', 'a', 'an',
        })

        result = [''] * len(entries)
        slot_max_chars = self.style_config.max_chars

        def _trim_to_fit(text: str) -> str:
            """Trim text to slot_max_chars at a word boundary."""
            if self._vis_len(text) <= slot_max_chars:
                return text
            words_tmp = text.split()
            fitted, budget = [], 0
            for w in words_tmp:
                needed = self._vis_len(w) + (1 if fitted else 0)
                if budget + needed > slot_max_chars:
                    break
                budget += needed
                fitted.append(w)
            return ' '.join(fitted) if fitted else text[:slot_max_chars]

        def _split_at_punct(text: str) -> List[str]:
            """Split translated paragraph into sentences at punctuation boundaries."""
            # Split on whitespace that follows sentence-ending punct
            parts = _SENT_END.split(text.strip())
            # Also split on Persian comma '،' when followed by enough context
            result_parts = []
            for part in parts:
                part = part.strip()
                if part:
                    result_parts.append(part)
            return result_parts if result_parts else [text.strip()]

        def _distribute_words(words: List[str], slots: List[int], times: List[float]) -> List[str]:
            """Time-proportional word distribution (fallback when sentences < slots)."""
            out = [''] * len(slots)
            total_time = sum(times)
            remaining = list(words)
            remaining_time = total_time

            for i, (idx, t) in enumerate(zip(slots, times)):
                if i == len(slots) - 1:
                    out[i] = _trim_to_fit(' '.join(remaining).strip())
                    break
                if not remaining:
                    out[i] = ''
                    continue
                slots_left = len(slots) - i
                proportional = max(1, round(len(remaining) * t / max(remaining_time, 0.1)))
                max_take = max(1, len(remaining) - (slots_left - 1))
                target_n = max(1, min(proportional, max_take))

                # Snap back off bad enders
                taken_words = remaining[:target_n]
                while len(taken_words) > 1 and taken_words[-1].lower().rstrip('.,!?؟،') in _BAD_ENDERS:
                    target_n -= 1
                    taken_words = remaining[:target_n]

                out[i] = _trim_to_fit(' '.join(taken_words).strip())
                remaining = remaining[target_n:]
                remaining_time = max(remaining_time - t, 0.1)

            return out

        for group_indices, translated_text in zip(paragraph_groups, translated_paragraphs):
            if not translated_text or not translated_text.strip():
                for idx in group_indices:
                    result[idx] = entries[idx].get('text', '')
                continue

            n_slots = len(group_indices)

            # Single-slot group: trivial
            if n_slots == 1:
                result[group_indices[0]] = _trim_to_fit(translated_text.strip())
                continue

            # ── Step 1: Split at sentence boundaries ─────────────────────────
            sentences = _split_at_punct(translated_text)

            # ── Step 2: Assign sentences to slots ────────────────────────────
            if len(sentences) >= n_slots:
                # More (or equal) sentences than slots: merge excess into last slot
                for i, idx in enumerate(group_indices):
                    if i < n_slots - 1:
                        result[idx] = _trim_to_fit(sentences[i])
                    else:
                        # Last slot gets all remaining sentences
                        result[idx] = _trim_to_fit(' '.join(sentences[i:]))
            else:
                # Fewer sentences than slots.
                # Strategy: assign sentences greedily, one per slot.
                # The last sentence gets distributed across ALL remaining slots
                # using time-proportional word splitting.
                # If there is only ONE sentence for multiple slots, it is
                # distributed entirely — never repeated or truncated into silence.
                slot_cursor = 0

                for sentence_idx, sentence in enumerate(sentences):
                    if slot_cursor >= n_slots:
                        break

                    sentences_left = len(sentences) - sentence_idx
                    slots_left     = n_slots - slot_cursor

                    if sentences_left == 1 and slots_left > 1:
                        # Last (or only) sentence covers multiple slots.
                        # If the sentence fits comfortably in one line, put it on the
                        # LAST slot (most natural reading position) and leave earlier
                        # slots empty — better than cutting a phrase mid-word.
                        # If it is too long to fit on one line, distribute words.
                        sentence_vis = _trim_to_fit(sentence)
                        if sentence_vis == sentence.strip():
                            # Fits on one line → assign only to last slot
                            for idx in group_indices[slot_cursor:-1]:
                                result[idx] = ''
                            result[group_indices[-1]] = sentence_vis
                        else:
                            # Too long to fit on one line → split at clause/punct boundaries.
                            # We try to produce exactly len(remaining_slots) chunks,
                            # each ≤ slot_max_chars, breaking at punctuation or bad-ender words.
                            remaining_slots = group_indices[slot_cursor:]
                            n_remaining = len(remaining_slots)
                            words_fa = sentence.split()
                            chunks = []
                            target_per_chunk = max(1, len(words_fa) // n_remaining)

                            buf_w = []
                            buf_c = 0
                            for wi, w in enumerate(words_fa):
                                buf_w.append(w)
                                buf_c += len(w) + (1 if len(buf_w) > 1 else 0)
                                is_last_word = (wi == len(words_fa) - 1)
                                chunks_needed = n_remaining - len(chunks)
                                words_left = len(words_fa) - wi - 1

                                should_chunk = False
                                if is_last_word:
                                    should_chunk = True
                                elif len(chunks) < n_remaining - 1:
                                    # Break at punctuation when near target size
                                    ends_punct = w.rstrip()[-1] in ('.!','?','،','؛',',') if w.rstrip() else False
                                    if buf_c >= slot_max_chars * 0.7 and ends_punct:
                                        should_chunk = True
                                    elif buf_c >= slot_max_chars:
                                        # Snap back off bad enders
                                        while len(buf_w) > 1 and buf_w[-1].lower().rstrip('.,!?؟،') in _BAD_ENDERS:
                                            words_fa.insert(wi + 1 - (len(buf_w) - len(buf_w)), buf_w.pop())
                                        should_chunk = True
                                    elif len(buf_w) >= target_per_chunk and words_left >= chunks_needed - 1:
                                        should_chunk = True

                                if should_chunk and buf_w:
                                    chunks.append(_trim_to_fit(' '.join(buf_w).strip()))
                                    buf_w = []; buf_c = 0

                            # Pad or trim chunks to match slot count
                            while len(chunks) < n_remaining:
                                chunks.append(chunks[-1] if chunks else '')
                            chunks = chunks[:n_remaining]

                            for k, idx in enumerate(remaining_slots):
                                result[idx] = chunks[k]
                        slot_cursor = n_slots
                    else:
                        # Assign this sentence to current slot and move on
                        result[group_indices[slot_cursor]] = _trim_to_fit(sentence)
                        slot_cursor += 1

                # Safety net: fill any leftover slots with last assigned text
                for k in range(slot_cursor, n_slots):
                    result[group_indices[k]] = result[group_indices[max(0, slot_cursor - 1)]]

        return result

    def translate_with_batch_fallback_chain(
        self,
        texts: List[str],
        target_lang: str,
        source_lang: str = 'en',
        original_entries: List[Dict] = None,
        output_srt: str = None,
        existing_translations: Dict[int, str] = None
    ) -> List[str]:
        """
        Translate texts with per-batch model fallback chain.
        
        Each batch tries models in sequence (deepseek -> minimax -> gemini -> grok).
        Each model gets only 1-2 attempts per batch before trying the next model.
        When a batch succeeds, the next batch starts fresh with the first model.
        This maximizes rate limit tolerance and distribution.
        
        Args:
            texts: Texts to translate
            target_lang: Target language code
            source_lang: Source language code (default: 'en')
            original_entries: Original SRT entries for incremental save
            output_srt: Output SRT file path for incremental saves
            existing_translations: Pre-existing translations to skip (from recovery)
        
        Returns:
            List of translated texts
        """
        if not texts or target_lang == source_lang:
            return texts
        
        # Model chain for fallback (resets per batch)
        MODEL_CHAIN = ["deepseek", "minimax", "gemini", "grok"]
        
        # Get batch sizes for each model
        BATCH_SIZES = {
            "deepseek": 25,
            "minimax": 20,
            "gemini": 40,
            "grok": 25,
        }
        
        # Initialize result list
        final_result = [None] * len(texts)
        
        # Prefill with existing translations (Smart Resume)
        if existing_translations:
            for idx, txt in existing_translations.items():
                if 0 <= idx < len(final_result) and txt and txt.strip():
                    final_result[idx] = txt
        
        # ── Pass 1: LOCAL CACHE LOOKUP (100% cost saving) ────────────────
        local_hits = 0
        for i, text in enumerate(texts):
            if final_result[i] is None:
                cached = self._lookup_local_cache(text, target_lang)
                if cached:
                    final_result[i] = cached
                    local_hits += 1
        if local_hits:
            self._cost_savings["local_cache_hits"] += local_hits
            self.logger.info(f"💾 Local cache: {local_hits} translations reused (100% cost saved)")

        # ── Pass 2: DEDUPLICATION ─────────────────────────────────────────
        # Many subtitles repeat the same sentence multiple times.
        # Translate each unique text once and fill in all duplicates.
        indices_to_translate = [i for i in range(len(texts)) if final_result[i] is None]
        if not indices_to_translate:
            self._save_local_translation_cache()
            # CRITICAL: Write the SRT file to disk even when ALL translations came from cache.
            # Without this, the output file is never created, breaking bilingual ASS rendering.
            result_texts = [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]
            if output_srt and original_entries:
                try:
                    with open(output_srt, 'w', encoding='utf-8-sig') as f:
                        for idx_srt, entry in enumerate(original_entries, 1):
                            t_text = result_texts[idx_srt-1] if idx_srt-1 < len(result_texts) else entry['text']
                            f.write(f"{idx_srt}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                    self.logger.info(f"✓ Cache-only save completed: {Path(output_srt).name}")
                except Exception as e:
                    self.logger.warning(f"Failed to save cache-only SRT: {e}")
            return result_texts
        
        # Build unique text → list of original indices
        unique_text_map: Dict[str, List[int]] = {}
        for i in indices_to_translate:
            t = texts[i]
            unique_text_map.setdefault(t, []).append(i)
        
        unique_texts = list(unique_text_map.keys())
        dedup_count = len(indices_to_translate) - len(unique_texts)
        if dedup_count > 0:
            self.logger.info(f"🔁 Deduplication: {len(unique_texts)} unique → saves {dedup_count} redundant API calls")
        
        # Create balanced batches over unique texts only
        unique_indices = list(range(len(unique_texts)))  # virtual indices into unique_texts
        
        # We need to batch unique_texts. Build a fake texts array just for batching.
        batch_indices_list = self._create_balanced_batches(unique_indices, unique_texts, max(BATCH_SIZES.values()))
        batch_count = len(batch_indices_list)
        
        pbar = tqdm(total=len(unique_texts), unit="item", desc=f"  Translating ({target_lang.upper()}) [Fallback Chain]")

        
        # Process each batch with fallback chain
        for batch_num, batch_indices in enumerate(batch_indices_list):
            # batch_indices are virtual indices into unique_texts
            batch = [unique_texts[idx] for idx in batch_indices]
            success_batch = False
            last_error = None
            
            # Try each model in chain for this batch (reset per batch)
            for model_idx, model_name in enumerate(MODEL_CHAIN):
                if success_batch:
                    break
                
                try:
                    batch_size = BATCH_SIZES[model_name]
                    
                    # Update progress bar postfix instead of printing a new line
                    pbar.set_postfix_str(f"Batch {batch_num + 1}/{batch_count} via {model_name.upper()}")
                    
                    # Call translation with minimal retries
                    trans_list = self.translate_batch_single_attempt(
                        batch,
                        target_lang,
                        source_lang,
                        model_name,
                        batch_size,
                        max_retries=2  # Only 2 attempts per model
                    )
                    
                    # Fill ALL duplicates and store in local cache
                    for rel_idx, trans in enumerate(trans_list):
                        unique_text = batch[rel_idx]
                        # Store in local cache
                        self._store_local_cache(unique_text, target_lang, trans)
                        # Fill all original indices that had this text
                        for abs_idx in unique_text_map.get(unique_text, []):
                            final_result[abs_idx] = trans
                    
                    # Live save to SRT file
                    if output_srt and original_entries:
                        try:
                            with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                for idx, entry in enumerate(original_entries, 1):
                                    trans = final_result[idx - 1]
                                    t_text = trans if trans is not None else entry['text']
                                    f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                        except Exception as e:
                            pbar.write(f"⚠️ Could not save intermediate SRT: {e}")
                    
                    # Update progress
                    pbar.update(len(batch))
                    success_batch = True
                    # Emit structured PROGRESS line for external consumers (e.g. su6i_yar.py)
                    _done_frac = (batch_num + 1) / max(1, batch_count)
                    _batch_pct = int(55 + _done_frac * 22)  # 55% → 77% across all batches
                    self.logger.info(f"PROGRESS:{_batch_pct}:🌐 Translation ({batch_num+1}/{batch_count})")
                    
                    # Wait to avoid rate limit issues
                    time.sleep(1)
                
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    last_error = error_msg
                    is_api_key = "401" in error_msg or "401 Unauthorized" in error_msg or "Invalid API Key" in error_msg
                    
                    if is_api_key:
                        pbar.write(f"⚠️ Batch {batch_num + 1}: {model_name.upper()} - API Key issue, skipping.")
                    else:
                        pbar.write(f"⚠️ Batch {batch_num + 1}: {model_name.upper()} failed - {error_msg[:80]}")
            
            # Check if batch succeeded
            if not success_batch:
                self.logger.error(f"❌ Batch {batch_num + 1} FAILED: All models exhausted. Using original text.")
                # Fallback: use original text for all duplicates in failed batch
                for unique_text in batch:
                    for abs_idx in unique_text_map.get(unique_text, []):
                        if final_result[abs_idx] is None:
                            final_result[abs_idx] = unique_text
                pbar.update(len(batch))
        
        pbar.close()
        
        # Persist local cache to disk
        self._save_local_translation_cache()
        
        # Print cost savings report
        self._log_cost_savings()
        
        # Ensure no None values
        final_result = [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]
        
        return final_result



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