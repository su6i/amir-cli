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
import os
import gc
import hashlib

# Environment control for library verbosity
# (Set to 0 if full debug needed, 1 hides progress bars)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0" 

import configparser
import tempfile
import shutil
import logging
import threading
from datetime import timedelta
from collections import deque
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

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

# ==================== ENUMS & DATA CLASSES ====================

class SubtitleStyle(Enum):
    PODCAST = "podcast"
    LECTURE = "lecture"
    VLOG = "vlog"
    MOVIE = "movie"
    NEWS = "news"
    CUSTOM = "custom"

class ProcessingStage(Enum):
    INIT = "init"
    TRANSCRIPTION = "transcription"
    STANDARDIZATION = "standardization"
    TRANSLATION = "translation"
    RENDERING = "rendering"
    COMPLETED = "completed"

@dataclass
class StyleConfig:
    name: str
    font_name: str
    font_size: int
    position: str
    alignment: int
    outline: int
    shadow: int
    border_style: int
    back_color: str
    primary_color: str
    max_chars: int
    max_lines: int
    use_banner: bool = False
    animation: Optional[str] = None

@dataclass
class WordObj:
    start: float
    end: float
    word: str

@dataclass
class ProcessingCheckpoint:
    video_path: str
    stage: ProcessingStage
    source_lang: str
    target_langs: List[str]
    timestamp: float
    data: Dict[str, Any]

# ==================== STYLE PRESETS ====================

STYLE_PRESETS = {
    SubtitleStyle.LECTURE: StyleConfig(
        name="Lecture",
        font_name="Arial",
        font_size=28,
        position="bottom",
        alignment=2,
        outline=2,
        shadow=0,
        border_style=3,
        back_color="&H80000000",
        primary_color="&H00FFFF00",
        max_chars=42,
        max_lines=1,
        use_banner=False
    ),
    SubtitleStyle.VLOG: StyleConfig(
        name="Vlog",
        font_name="Arial",
        font_size=22,
        position="top",
        alignment=8,
        outline=3,
        shadow=0,
        border_style=1,
        back_color="&H00000000",
        primary_color="&H00FFFFFF",
        max_chars=35,
        max_lines=2,
        use_banner=False,
        animation="fade"
    ),
}

# ==================== LANGUAGE CONFIGURATION ====================

@dataclass
class LanguageConfig:
    """Configuration for a specific language"""
    code: str
    name: str
    char_range: Optional[tuple] = None  # Unicode range for validation (start, end)
    rtl: bool = False  # Right-to-left script
    
# Central language registry - single source of truth
# Ordered by YouTube priority (top 25 languages + extras)
LANGUAGE_REGISTRY = {
    # Top 25 by internet/YouTube reach (2026)
    'zh': LanguageConfig('zh', 'Chinese', ('\u4e00', '\u9fff')),              # 1. Mandarin/Simplified
    'en': LanguageConfig('en', 'English'),                                    # 2. English
    'es': LanguageConfig('es', 'Spanish'),                                    # 3. Spanish
    'hi': LanguageConfig('hi', 'Hindi', ('\u0900', '\u097F')),               # 4. Hindi (Devanagari)
    'ar': LanguageConfig('ar', 'Arabic', ('\u0600', '\u06FF'), rtl=True),    # 5. Arabic (Standard)
    'bn': LanguageConfig('bn', 'Bengali', ('\u0980', '\u09FF')),             # 6. Bengali
    'pt': LanguageConfig('pt', 'Portuguese'),                                 # 7. Portuguese
    'ru': LanguageConfig('ru', 'Russian', ('\u0400', '\u04FF')),             # 8. Russian (Cyrillic)
    'ja': LanguageConfig('ja', 'Japanese', ('\u3040', '\u30ff')),            # 9. Japanese (Hiragana/Katakana)
    'fr': LanguageConfig('fr', 'French'),                                     # 10. French
    'ur': LanguageConfig('ur', 'Urdu', ('\u0600', '\u06FF'), rtl=True),      # 11. Urdu (Arabic script)
    'pa': LanguageConfig('pa', 'Punjabi', ('\u0a00', '\u0a7f')),             # 12. Punjabi (Gurmukhi)
    'vi': LanguageConfig('vi', 'Vietnamese'),                                 # 13. Vietnamese
    'tr': LanguageConfig('tr', 'Turkish'),                                    # 14. Turkish
    'ko': LanguageConfig('ko', 'Korean', ('\uac00', '\ud7af')),              # 15. Korean (Hangul)
    'id': LanguageConfig('id', 'Indonesian'),                                 # 16. Indonesian
    'de': LanguageConfig('de', 'German'),                                     # 17. German
    'fa': LanguageConfig('fa', 'Persian', ('\u0600', '\u06FF'), rtl=True),   # 18. Persian/Dari/Tajik
    'gu': LanguageConfig('gu', 'Gujarati', ('\u0a80', '\u0aff')),            # 19. Gujarati
    'it': LanguageConfig('it', 'Italian'),                                    # 20. Italian
    'mr': LanguageConfig('mr', 'Marathi', ('\u0900', '\u097f')),             # 21. Marathi (Devanagari)
    'te': LanguageConfig('te', 'Telugu', ('\u0c00', '\u0c7f')),              # 22. Telugu
    'ta': LanguageConfig('ta', 'Tamil', ('\u0b80', '\u0bff')),               # 23. Tamil
    'th': LanguageConfig('th', 'Thai', ('\u0e00', '\u0e7f')),                # 24. Thai
    'ha': LanguageConfig('ha', 'Hausa'),                                      # 25. Hausa (Latin script)
    
    # Additional supported languages
    'el': LanguageConfig('el', 'Greek', ('\u0370', '\u03FF')),
    'mg': LanguageConfig('mg', 'Malagasy'),                                   # Madagascar
    'nl': LanguageConfig('nl', 'Dutch'),
    'pl': LanguageConfig('pl', 'Polish'),
    'uk': LanguageConfig('uk', 'Ukrainian', ('\u0400', '\u04FF')),
}

def get_language_config(lang_code: str) -> LanguageConfig:
    """Get language configuration with fallback to generic config"""
    return LANGUAGE_REGISTRY.get(lang_code, LanguageConfig(lang_code, lang_code.upper()))

def has_target_language_chars(text: str, lang_code: str) -> bool:
    """Check if text contains characters from the target language's script"""
    if not text:
        return False
    
    lang_config = get_language_config(lang_code)
    
    # If language doesn't have a specific character range (Latin scripts), 
    # we can't validate by character presence alone
    if not lang_config.char_range:
        return True  # Assume valid for Latin scripts
    
    char_start, char_end = lang_config.char_range
    return any(char_start <= c <= char_end for c in text)

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
        bert_model: Optional[str] = None
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
        
        self.sec_font_size = sec_font_size or 25  # Default for Persian if not provided
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
    def load_api_key(config_file: str = '.config') -> str:
        """Load API key from env, .env file, or config"""
        # Check environment variables (both formats)
        if os.environ.get('DEEPSEEK_API'):
            return os.environ['DEEPSEEK_API']
        if os.environ.get('DEEPSEEK_API_KEY'):
            return os.environ['DEEPSEEK_API_KEY']

        # Search in multiple locations
        search_paths = [
            config_file,
            os.path.join(os.getcwd(), '.env'),
            os.path.join(os.getcwd(), '.config'),
            os.path.expanduser('~/.amir/config'),
            os.path.expanduser('~/.env'),
        ]

        for path in search_paths:
            if not os.path.exists(path):
                continue
            
            # Try .env format first (KEY=value)
            try:
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('DEEPSEEK_API_KEY='):
                            key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                                return key
                        elif line.startswith('DEEPSEEK_API='):
                            key = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                                return key
            except:
                pass
            
            # Try ConfigParser format
            try:
                config = configparser.ConfigParser()
                config.read(path)
                if 'DEFAULT' in config:
                    for key_name in ['DEEPSEEK_API_KEY', 'DEEPSEEK_API']:
                        if key_name in config['DEFAULT']:
                            key = config['DEFAULT'][key_name].strip()
                            if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                                return key
            except:
                continue
        
        return ""

    # ==================== MODEL MANAGEMENT ====================

    @property
    def model(self):
        """Lazy load Whisper model"""
        if self._model is None:
            if HAS_MLX and HAS_PLATFORM and platform_module.system() == "Darwin" and platform_module.machine() == "arm64":
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

    def cleanup(self):
        if HAS_MLX:
             # Try to clear Metal cache if mlx is loaded in main process
             try:
                 import mlx.core as mx
                 mx.clear_cache()
             except:
                 pass
        
        # Explicitly clear torch cache too
        if HAS_TORCH:
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except:
                pass
        
        # Force Python GC
        gc.collect()

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
        """Dynamically split indices into batches based on text length and count to respect context limits"""
        batches = []
        current_batch = []
        current_chars = 0
        
        for idx in indices:
            text_len = len(texts[idx])
            # Start new batch if adding this exceeds COUNT or CHAR limit
            # 5000 chars is ~1250-1500 tokens, safe for all modern models and response windows
            if len(current_batch) >= max_batch_size or (current_batch and current_chars + text_len > max_chars):
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
            
            current_batch.append(idx)
            current_chars += text_len
            
        if current_batch:
            batches.append(current_batch)
            
        self.logger.debug(f"⚖️ Batch Balancer: Created {len(batches)} optimal batches for {len(indices)} entries.")
        return batches

    # Cache system removed - users manage their own SRT files

    # ==================== COST SAVING HELPERS ====================

    def _local_cache_key(self, text: str, target_lang: str) -> str:
        """Stable hash key for local translation cache"""
        return hashlib.md5(f"{text}|||{target_lang}".encode("utf-8")).hexdigest()

    def _load_local_translation_cache(self):
        """Load persisted local translation cache from disk"""
        try:
            if self._local_cache_path.exists():
                with open(self._local_cache_path, 'r', encoding='utf-8') as f:
                    self._local_cache = json.load(f)
                self.logger.debug(f"💾 Local translation cache loaded: {len(self._local_cache)} entries")
        except Exception as e:
            self.logger.warning(f"Could not load local translation cache: {e}")
            self._local_cache = {}

    def _save_local_translation_cache(self):
        """Persist local translation cache to disk"""
        if not self._local_cache_dirty:
            return
        try:
            self._local_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._local_cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._local_cache, f, ensure_ascii=False, indent=None)
            self._local_cache_dirty = False
        except Exception as e:
            self.logger.warning(f"Could not save local translation cache: {e}")

    def _lookup_local_cache(self, text: str, target_lang: str) -> Optional[str]:
        """Return cached translation or None"""
        return self._local_cache.get(self._local_cache_key(text, target_lang))

    def _store_local_cache(self, text: str, target_lang: str, translation: str):
        """Store a single translation in local cache"""
        if translation and translation.strip():
            key = self._local_cache_key(text, target_lang)
            self._local_cache[key] = translation
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
        """Print accumulated cost savings summary"""
        s = self._cost_savings
        total_local = s["local_cache_hits"]
        ds_cached = s["deepseek_cache_hit_tokens"]
        grok_cached = s["grok_cache_hit_tokens"]
        gem_cached = s["gemini_cached_tokens"]
        
        if total_local + ds_cached + grok_cached + gem_cached == 0:
            return
        
        self.logger.info("──────────────────────────────────────────")
        self.logger.info("💰 Cost Savings Report:")
        if total_local:
            self.logger.info(f"   • Local cache hits: {total_local} lines (100% saved)")
        if ds_cached:
            self.logger.info(f"   • DeepSeek cached tokens: {ds_cached:,} (90% cheaper)")
        if grok_cached:
            self.logger.info(f"   • Grok cached tokens: {grok_cached:,} (discounted)")
        if gem_cached:
            self.logger.info(f"   • Gemini cached tokens: {gem_cached:,} (guaranteed discount)")
        self.logger.info("──────────────────────────────────────────")



    def transcribe_video(
        self,
        video_path: str,
        language: str = 'en',
        correct: bool = False,
        detect_speakers: bool = False,
        dur: float = 0
    ) -> str:
        """Main transcription gate"""
        if HAS_MLX and HAS_PLATFORM and platform_module.system() == "Darwin" and platform_module.machine() == "arm64":
            return self.transcribe_video_mlx(video_path, language, correct, detect_speakers, dur_override=dur)
        return self.transcribe_video_whisper(video_path, language, correct, detect_speakers)

    def transcribe_video_whisper(
        self,
        video_path: str,
        language: str = 'en',
        correct: bool = False,
        detect_speakers: bool = False
    ) -> str:
        """Transcribe video with Whisper (Standard Torch)"""
        from faster_whisper import WhisperModel
        
        self.logger.info(f"Transcription process initiated (ISO: {language.upper()})")
        
        segments, info = self.model.transcribe(
            video_path,
            language=language,
            word_timestamps=True,
            initial_prompt=self.initial_prompt or "Clear punctuation and case sensitivity.",
            temperature=self.temperature
        )
        
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
        
        srt_path = os.path.splitext(video_path)[0] + f"_{language}.srt"
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, entry in enumerate(entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        
        self.logger.info(f"Asset preservation complete: {Path(srt_path).name}")
        return srt_path

    def transcribe_video_mlx(self, video_path: str, language: str, correct: bool, detect_speakers: bool, dur_override: float = 0) -> str:
        """MLX-accelerated transcription (Isolated in Subprocess for Memory safety)"""
        self.logger.info(f"☢️ Initiating Isolated MLX Transcription (ISO: {language.upper()})")
        
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
        result = mlx_whisper.transcribe(
            "{video_path}",
            language="{language}",
            path_or_hf_repo="{repo_path}",
            word_timestamps=True,
            verbose=True, # Stream progress
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            temperature=(0.0, 0.2, 0.4, 0.6, 0.8),
        )
        
        simplified = []
        for segment in result.get('segments', []):
            if 'words' in segment:
                for w in segment['words']:
                    simplified.append({{'start': w['start'], 'end': w['end'], 'word': w['word']}})
        
        with open("{result_json_path}", "w", encoding="utf-8") as f:
            json.dump(simplified, f)
            
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
            
            pbar = tqdm(total=100, unit="%", desc=f"  Transcribing ({language.upper()})")
            
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

            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                
                if line:
                    # Log errors from worker if any
                    if "WORKER_ERROR" in line:
                        self.logger.error(f"  {line.strip()}")
                        
                    curr_time = parse_time(line)
                    if curr_time and dur > 0:
                        pct = min(100, (curr_time / dur) * 100)
                        pbar.n = int(pct)
                        pbar.refresh()
            
            proc.wait()
            pbar.n = 100
            pbar.refresh()
            pbar.close()
            
            if proc.returncode != 0:
                stderr = proc.stderr.read()
                self.logger.error(f"❌ Isolated worker failed: {stderr}")
                raise RuntimeError(f"Transcription worker failed: {stderr}")
            
            # 4. Load results
            if not os.path.exists(result_json_path):
                raise RuntimeError("Isolated worker exited without producing results.")
                
            with open(result_json_path, 'r', encoding='utf-8') as f:
                word_dicts = json.load(f)
            
            all_words = [WordObj(w['start'], w['end'], w['word']) for w in word_dicts]
            
            self.logger.info(f"✅ Isolated transcription successful. {len(all_words)} words retrieved.")
            
        finally:
            # Cleanup worker files
            for p in [worker_path, result_json_path]:
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass

        entries = self.resegment_to_sentences(all_words, None)
        
        # Final cleanup for the main process just in case
        self.cleanup()
        
        # Use original video name for SRT output
        final_video_name = Path(video_path).stem
        if "safe_input" in video_path or "temp_" in video_path:
            final_video_name = re.sub(r'^(temp_\d+_|safe_)', '', final_video_name)
            
        srt_path = os.path.splitext(video_path)[0] + f"_{language}.srt"
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
        """Smart sentence segmentation - semantic-first"""
        entries = []
        current_words = []
        current_len = 0
        
        sentence_enders = ('.', '?', '!', '...')
        soft_break_chars = (',', ';', ':')
        limit = getattr(self.style_config, 'max_chars', 42)
        hard_limit = limit * 2  # Absolute ceiling to prevent overly long lines
        
        i = 0
        total = len(words)
        
        while i < total:
            word_obj = words[i]
            text = word_obj.word.strip()
            
            if not text:
                i += 1
                continue
            
            current_words.append(word_obj)
            current_len += len(text) + 1
            
            should_break = False
            is_sentence_end = text.endswith(sentence_enders)
            is_soft_break = text.endswith(soft_break_chars)
            is_last = (i == total - 1)
            
            if is_last:
                should_break = True
            
            elif is_sentence_end:
                # Priority 1: Sentence end -> Always break
                should_break = True
            
            elif current_len > hard_limit:
                # Absolute ceiling: Must break, but try to break at comma if possible
                should_break = True
            
            elif is_soft_break and current_len > limit:
                # Comma + exceeded limit -> Look ahead
                # If the remaining part of the sentence is short and ends with a period, wait
                remaining_text = ""
                j = i + 1
                temp_len = 0
                hits_sentence_end = False
                
                while j < total and temp_len < 30:  # Look ahead max 30 chars
                    next_word = words[j].word.strip()
                    temp_len += len(next_word) + 1
                    remaining_text += next_word + " "
                    if next_word.endswith(sentence_enders):
                        hits_sentence_end = True
                        break
                    if next_word.endswith(soft_break_chars):
                        break  # Another comma found, break here
                    j += 1
                
                if hits_sentence_end and temp_len <= 25:
                    # Remaining part is short and hits sentence end -> Wait for full sentence
                    should_break = False
                else:
                    should_break = True
            
            if should_break and current_words:
                t = " ".join([w.word.strip() for w in current_words])
                t = re.sub(r'\s+', ' ', t).strip()
                
                # Orphan prevention
                words_in_t = t.split()
                if len(words_in_t) >= 3:
                    t = " ".join(words_in_t[:-2]) + " " + words_in_t[-2] + "\u00A0" + words_in_t[-1]
                
                entries.append({
                    'start': self.format_time(current_words[0].start),
                    'end': self.format_time(current_words[-1].end),
                    'text': t
                })
                
                current_words = []
                current_len = 0
            
            i += 1
        
        # Hallucination Suppression (Pre-Sanitization)
        entries = self.suppress_hallucinations(entries)

        # Sanitize entries (fix overlaps and short durations)
        entries = self.sanitize_entries(entries)
        
        return entries

    def merge_to_clauses(self, entries: List[Dict]) -> List[Dict]:
        """
        Merge consecutive SRT fragments primarily based on TIME (configurable via config).
        Raw fragments inherently represent semantic pauses. We accumulate them until 
        reaching a target duration (e.g., 5.0 seconds) so that subtitles stay on screen 
        long enough to be comfortably read, and don't stretch into massive lines.
        """
        if not entries:
            return []
            
        # Load configurable target duration and break characters
        try:
            from media_config import MediaConfig
            config = MediaConfig()
            target_duration_sec = float(config.get('video.subtitle.merge_sec', 5.0))
            min_words = int(config.get('video.subtitle.min_words', 5))
            max_words = int(config.get('video.subtitle.max_words', 15))
            break_chars_list = config.get('video.subtitle.break_chars', ['.', '?', '!', '...', '。', '？', '！', ',', ';', ':', '،', '؛'])
            all_break_chars = tuple(break_chars_list)
            split_words_list = config.get('video.subtitle.split_words', ['and', 'but', 'because', 'so', 'if', 'when', 'what', 'why', 'where', 'how', 'who'])
            split_words = tuple(w.lower() for w in split_words_list)
        except Exception:
            target_duration_sec = 5.0
            min_words = 5
            max_words = 15
            all_break_chars = ('.', '?', '!', '...', '。', '？', '！', ',', ';', ':', '،', '؛')
            split_words = ('and', 'but', 'because', 'so', 'if', 'when', 'what', 'why', 'where', 'how', 'who')
        
        def _ts_to_sec(ts: str) -> float:
            """Parse SRT timestamp '00:04:09,430' → seconds."""
            ts = ts.replace(',', '.')
            parts = ts.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        
        merged = []
        buffer_texts = []
        buffer_start = None
        buffer_start_sec = 0.0
        buffer_end = None
        buffer_end_sec = 0.0
        
        def _flush():
            nonlocal buffer_texts, buffer_start, buffer_start_sec, buffer_end, buffer_end_sec
            if buffer_texts:
                merged_text = ' '.join(buffer_texts)
                merged_text = re.sub(r'\s+', ' ', merged_text).strip()
                merged.append({
                    'start': buffer_start,
                    'end': buffer_end,
                    'text': merged_text,
                })
            buffer_texts = []
            buffer_start = None
            
        for entry in entries:
            text = entry['text'].strip()
            if not text:
                continue
                
            text_lower = text.lower()
            incoming_word_count = len(text.split())
            
            # --- 1. Pre-addition check (Semantic Chunking based on Conjunctions & Limits) ---
            if buffer_texts:
                current_word_count = sum(len(t.split()) for t in buffer_texts)
                
                # Check if any of our split words exist as whole words in the string
                # We use regex word boundaries to prevent matching 'or' inside 'world'
                is_conjunction = False
                for w in split_words:
                    if re.search(r'\b' + re.escape(w) + r'\b', text_lower):
                        is_conjunction = True
                        break
                
                should_flush_early = False
                
                # Rule 1: Break before conjunctions if we already have a decent clause
                if is_conjunction and current_word_count >= min_words:
                    should_flush_early = True
                
                # Rule 2: Break BEFORE adding this chunk if it would exceed our hard max
                elif (current_word_count + incoming_word_count) > max_words:
                    should_flush_early = True
                    
                if should_flush_early:
                    _flush()
            
            # Now add current fragment to the buffer
            if buffer_start is None:
                buffer_start = entry['start']
                buffer_start_sec = _ts_to_sec(entry['start'])
            
            buffer_texts.append(text)
            buffer_end = entry['end']
            buffer_end_sec = _ts_to_sec(entry['end'])
            
            buf_duration = buffer_end_sec - buffer_start_sec
            current_word_count = sum(len(t.split()) for t in buffer_texts)
            ends_with_break = text.endswith(all_break_chars)
            
            # --- 2. Post-addition check (Time & Punctuation) ---
            should_flush = False
            
            # Rule A: User logic -> Above `min_words` AND `break_chars` exists
            if ends_with_break and current_word_count >= min_words:
                should_flush = True
                
            # Rule B: Time logic -> Above `merge_sec` AND `break_chars` exists    
            elif ends_with_break and buf_duration >= target_duration_sec:
                should_flush = True
                
            # Rule C: Time ceiling to prevent infinite lines if no punctuation exists
            elif buf_duration >= 8.0:
                should_flush = True
                
            if should_flush:
                _flush()
        
        # Flush remaining buffer
        _flush()
        
        self.logger.info(f"📐 Clause merge (Target: {target_duration_sec}s): {len(entries)} fragments → {len(merged)} clauses")
        return merged

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
        """Convert SRT time format to seconds"""
        try:
            h, m, s_ms = t_str.replace(',', '.').split(':')
            s, ms = s_ms.split('.')
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000
        except Exception:
            return 0.0

    @staticmethod
    def format_time(seconds: float) -> str:
        """SRT time format"""
        td = timedelta(seconds=float(seconds))
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    @staticmethod
    def _normalize_digits(text: str) -> str:
        """Normalize Persian/Arabic-Indic digits to ASCII for robust parsing."""
        if not text:
            return text
        return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

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

    def _parse_translated_batch_output(self, output: str, expected_count: int) -> List[str]:
        """Robustly parse model output into an ordered list of translated lines."""
        if not output:
            return []
        
        # CRITICAL: Detect LLM contamination (thinking/JSON injection)
        if '</think>' in output or 'I\'m capturing' in output or 'I am capturing' in output:
            self.logger.error(f"❌ LLM thinking detected in output! Model returned internal reasoning.")
            # Try salvage: extract only the JSON/Persian part
            match = re.search(r'\{\"1\".*?\}', output, re.DOTALL)
            if match:
                try:
                    parsed_json = json.loads(match.group())
                    items = [str(parsed_json.get(str(i+1), '')).strip() for i in range(expected_count)]
                    if any(items):
                        self.logger.warning(f"⚠️ Salvaged translation from corrupted output")
                        return items
                except:
                    pass
            # If can't salvage, reject entire batch
            return []

        cleaned = output.strip()
        cleaned = re.sub(r'^```(?:json|text)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = self._normalize_digits(cleaned)

        # 1) JSON first (many providers now return strict JSON when constrained)
        if cleaned.startswith('[') or cleaned.startswith('{'):
            try:
                parsed_json = json.loads(cleaned)
                if isinstance(parsed_json, list):
                    items = [str(item).strip() for item in parsed_json if str(item).strip()]
                    if items:
                        return items[:expected_count]
                elif isinstance(parsed_json, dict):
                    mapped = {}
                    for k, v in parsed_json.items():
                        key_str = self._normalize_digits(str(k).strip())
                        if key_str.isdigit():
                            # Keep even empty strings if explicitly returned
                            mapped[int(key_str)] = str(v).strip()
                    if mapped:
                        # Build full list with same length as expected
                        ordered = [mapped.get(i) for i in range(1, expected_count + 1)]
                        # Apply 80% threshold for JSON dicts too
                        valid_count = sum(1 for v in ordered if v is not None)
                        if valid_count >= int(expected_count * 0.8):
                            return ordered
            except Exception:
                pass

        # 2) Numbered lines with multiline continuation support
        parsed_lines = {}
        current_num = None
        for raw_line in cleaned.split('\n'):
            line = self._normalize_digits(raw_line.strip())
            if not line:
                continue

            match = re.match(r'^[\-\*•\u2022]?\s*[\(\[]?(\d+)[\)\]\.\-:\s]+(.*)', line)
            if match:
                num = int(match.group(1))
                content = match.group(2).strip().strip('"').strip("'")
                parsed_lines[num] = content if content else parsed_lines.get(num, "")
                current_num = num
                continue

            if current_num is not None:
                prev = parsed_lines.get(current_num, "")
                parsed_lines[current_num] = f"{prev} {line}".strip()

        # Build ordered list - ALWAYS return expected_count items
        ordered = []
        for i in range(1, expected_count + 1):
            value = parsed_lines.get(i)
            # Accept any value, even empty - caller will handle with original text fallback
            ordered.append(value if value else None)
        
        # If we got at least 80% valid lines, return the full batch (with None for missing)
        valid_count = sum(1 for v in ordered if v and v.strip())
        if valid_count >= int(expected_count * 0.8):
            return ordered
        
        # If less than 80% valid, reject entire batch to trigger retry
        return []

        # 3) Plain line fallback (for providers that ignore numbering)
        plain_lines = []
        for raw_line in cleaned.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r'^(translation|translations|ترجمه)\s*[:：]\s*$', line, flags=re.IGNORECASE):
                continue
            plain_lines.append(line.lstrip('-• ').strip())

        return plain_lines[:expected_count] if len(plain_lines) >= expected_count else []

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

            # Use indexed list for DeepSeek to ensure perfect alignment
            batch_text = ctx_section + "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
            
            # NUCLEAR PERSISTENCE: Retry until successful (Max 10 attempts)
            attempt = 0
            max_retries = 10
            success_batch = False
            ds_failed = False
            last_error_msg = ""
            while attempt < max_retries:
                try:
                    attempt += 1
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
                    trans_list = self._parse_translated_batch_output(output, len(batch))
                    
                        # Replace None values with original text as fallback
                    if None in trans_list:
                        trans_list = [trans_list[j] if trans_list[j] is not None else batch[j] for j in range(len(trans_list))]
                    
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
                    
                    if len(trans_list) >= len(batch):
                        result_batch = trans_list[:len(batch)]
                        for rel_idx, trans in enumerate(result_batch):
                            abs_idx = batch_indices[rel_idx]
                            final_result[abs_idx] = trans
                            
                        # LIVE SAVING: Write progress to SRT file immediately
                        if output_srt and original_entries:
                            try:
                                with open(output_srt, 'w', encoding='utf-8-sig') as f:
                                    for idx, entry in enumerate(original_entries, 1):
                                        trans = final_result[idx-1]
                                        t_text = trans if trans is not None else entry['text']
                                        f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{t_text}\n\n")
                            except: pass

                        pbar.update(len(batch))
                        success_batch = True
                        time.sleep(1)
                        break
                    else:
                        delay = min(20 + attempt * 5, 120)
                        self.logger.warning(f"⚠️ Batch {i + 1} incomplete: expected {len(batch)}, got {len(trans_list)}. Retrying in {delay}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(delay)
                        if attempt >= max_retries:
                            last_error_msg = f"incomplete response after {max_retries} attempts"
                            ds_failed = True
                            break

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    last_error_msg = error_msg
                    if "401" in error_msg or "Invalid API Key" in error_msg:
                        raise
                    if attempt >= max_retries:
                        ds_failed = True
                        break
                    wait_time = min(60, (2 ** (attempt % 6)) * 5)
                    self.logger.warning(f"Batch {i//batch_size + 1} attempt {attempt}/{max_retries} failed: {error_msg}")
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
                "SYSTEM:Tehrani informal tone, max 45 chars/line.\n"
                "FORMAT: Return ONLY a valid JSON object where keys are the input line numbers and values are the translations.\n"
                "EXAMPLE: {\"1\": \"سلام\", \"2\": \"چطوری؟\"}\n"
                f"RULE: For technical terms (API, AGI, etc.), write the {lang_name} translation first, then the English in parentheses (e.g. 'هزینه‌ها (CapEx)').\n"
                "CRITICAL: NEVER echo or repeat the original English source text in your output. Each value must contain ONLY the Persian translation.\n"
                "NO commentary, NO extra text."
            )
        
        # Generic prompt for other languages
        return (
            f"You are a professional {lang_name} subtitle translator.\n"
            "FORMAT: Return ONLY a valid JSON object where keys are the input line numbers and values are the translations.\n"
            "EXAMPLE: {\"1\": \"Hello\", \"2\": \"How are you?\"}\n"
            "NO commentary, NO extra text."
        )

    @staticmethod
    def fix_persian_text(text: str) -> str:
        if not text:
            return text
        
        # 0. Cleanup spaces before punctuation (LLM artifact)
        text = re.sub(r'\s+([\.!؟،؛])', r'\1', text)
        
        # 1. Informal verb normalization + ZWNJ insertion for correct letterform shaping.
        # Vazirmatn renders ZWNJ (\u200C) as an invisible zero-width glyph, so we CAN use it.
        informal = {
            r'\bمی‌باشند\b': 'هستن',
            r'\bمی‌باشد\b': 'هست',
        }
        for p, r in informal.items():
            text = re.sub(p, r, text)

        # Add ZWNJ where needed for correct Persian word shapes:
        #   می‌کنیم  — prevents ی+ک joining across morpheme boundary
        #   کتاب‌ها  — prevents ب+ه joining in plural suffix
        zwnj_patterns = [
            (r'(\w)(ها)(\s|$)', '\\1\u200c\\2\\3'),
            (r'می(\s)', 'می\u200c\\1'),
        ]
        for pat, repl in zwnj_patterns:
            text = re.sub(pat, repl, text)

        # 2. Strip directional control characters — both old embeddings AND any previously
        # applied isolates (so this function is always idempotent: safe to call repeatedly).
        # Kept: ZWNJ (\u200c) — Vazirmatn renders it as invisible zero-width glyph; needed
        # for correct Persian word-boundary shaping.
        # Stripped embeddings : RLM \u200f, LRM \u200e, ZWJ \u200d, RLE \u202b, LRE \u202a,
        #                        PDF \u202c, RLO \u202e, LRO \u202d
        # Stripped isolates   : RLI \u2067, LRI \u2066, PDI \u2069  (re-applied fresh below)
        for _cp in ('\u200f', '\u200e', '\u200d',
                    '\u202b', '\u202a', '\u202c', '\u202e', '\u202d',
                    '\u2067', '\u2066', '\u2069'):
            text = text.replace(_cp, '')

        # 3. Migration: undo the old "move-to-front" punct transform.
        # Previous versions of fix_persian_text moved trailing punctuation to logical-START
        # to compensate for LTR paragraph rendering. With RLI (step 5), the paragraph is
        # now RTL: logical-START = visual-RIGHT = beginning of sentence = WRONG position
        # for punctuation. Detect the old pattern (string starts with punct cluster) and
        # move it back to logical-END where it belongs in an RTL paragraph.
        text = text.strip()
        text = re.sub(r'^([.!:،؛؟]+)(.+)$', r'\2\1', text)

        # 4. Isolate English parenthetical terms as LTR runs within the RTL paragraph.
        # Unicode TR9 §6.3: "use directional isolates instead of embeddings in
        # programmatically generated text."
        # LRI (\u2066) ... PDI (\u2069) → equivalent to dir="ltr" unicode-bidi:isolate
        _LRI = '\u2066'  # LEFT-TO-RIGHT ISOLATE
        _PDI = '\u2069'  # POP DIRECTIONAL ISOLATE
        _RLI = '\u2067'  # RIGHT-TO-LEFT ISOLATE
        text = re.sub(r'(\([A-Za-z][^)]*\))', _LRI + r'\1' + _PDI, text)

        # 5. Wrap the entire string as an RTL isolate paragraph.
        # This forces libass BiDi P2/P3 "first strong character" resolution to RTL,
        # isolated from any surrounding LTR context (e.g. the English top line).
        # RLI (\u2067) ... PDI (\u2069) → equivalent to dir="rtl" unicode-bidi:isolate
        text = _RLI + text + _PDI

        return text

    @staticmethod
    def strip_english_echo(text: str) -> str:
        """Strip echoed English prefix from a Persian translation.

        When an LLM returns 'original sentence. ترجمه فارسی' instead of just
        the Persian part, this strips everything before the first Persian char.
        It is safe: if the text already starts with Persian (the normal case)
        the string is returned unchanged.
        """
        if not text:
            return text
        # Find the position of the first Persian/Arabic character
        persian_start = -1
        for i, c in enumerate(text):
            if '\u0600' <= c <= '\u06FF':
                persian_start = i
                break
        # Text has no Persian at all – nothing to strip (caller handles fallback)
        if persian_start < 0:
            return text
        # Text already starts with Persian (most common case) – leave untouched
        if persian_start == 0:
            return text
        # There are non-Persian characters before the first Persian character.
        # Only strip them when the prefix looks like real English words (2+ consecutive
        # ASCII letters), to avoid trimming legitimate leading punctuation.
        prefix = text[:persian_start]
        if re.search(r'[a-zA-Z]{2,}', prefix):
            return text[persian_start:].strip()
        return text

    @staticmethod
    def _clean_bidi(t: str) -> str:
        """Strip BiDi directional control chars. Preserves ZWNJ (\u200C) — Vazirmatn renders it invisibly."""
        if not t: return ""
        for cp in ('\u200f', '\u200e', '\u200d',
                   '\u202b', '\u202a', '\u202c', '\u202e', '\u202d'):
            t = t.replace(cp, '')
        return t.strip()

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

    def create_ass_with_font(self, srt_path: str, ass_path: str, lang: str, secondary_srt: Optional[str] = None, time_offset: float = 0.0):
        """Generate ASS file"""
        title = f"{get_language_config(lang).name} + {get_language_config('fa').name}" if secondary_srt else get_language_config(lang).name
        self.logger.info(f"Generating ASS asset ({title})...")
        
        style = self.style_config
        
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
                f"{style.alignment},10,10,10,1"
            )
        
        # Standard V4+ Styles Format (23 entries)
        format_line = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"

        # Update primary_style to match full format
        primary_style_full = (
            f"Style: Default,{style.font_name},{style.font_size},{style.primary_color},&H000000FF,&H00000000,{style.back_color},"
            f"0,0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
            f"{style.alignment},10,10,10,1"
        )

        # Build styles block: always include primary, conditionally add FA
        styles_block = f"{format_line}\n{primary_style_full}"
        if lang == 'fa' or secondary_srt:
            styles_block += f"\n{fa_style}"

        header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2

[V4+ Styles]
{styles_block}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        secondary_map = {}
        if secondary_srt and os.path.exists(secondary_srt):
            sec = self.parse_srt(secondary_srt)
            # Sync protection: Do NOT re-sanitize here, assume already sanitized in workflow
            # Use INDEX-based mapping instead of time-based for better alignment
            for idx, e in enumerate(sec):
                secondary_map[idx] = e['text'] # fix_persian_text will be handled during rendering
        
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
            
            final_text = text
            
            # --- PERSIAN SHAPING LOGIC REMOVED ---
            # FFmpeg is compiled with --enable-libharfbuzz, so it handles Arabic/Persian natively.
            # Manual reshaping interferes with HarfBuzz and causes "backwards" text.
            # We simply pass the raw UTF-8 text.
            
            # If we need to force RTL base direction, we use standard Unicode markers if needed,
            # but usually raw text is best for HarfBuzz.

            if secondary_map:
                # Use INDEX-based matching for perfect alignment
                sec_text = secondary_map.get(idx)
                
                if sec_text:
                    # Clean and re-fix to ensure no double-wrapping
                    sec_text = SubtitleProcessor._clean_bidi(sec_text)
                    sec_text_fixed = self.fix_persian_text(sec_text)
                    # Wrap English terms in parentheses with smaller font
                    sec_text_formatted = wrap_parentheses_with_smaller_font(sec_text_fixed)
                    # Top row (primary/source): smaller gray — fixed at 75%, never dynamic.
                    # Bottom row (secondary/FA): full size white bold — never changes.
                    # Font size MUST be constant per video; dynamic sizing causes jarring jumps.
                    top_fs = max(16, int(style.font_size * 0.75))
                    bot_fs = style.font_size
                    # RTL direction handled by FaDefault style (Vazirmatn is inherently RTL).
                    # Do NOT insert RLM here — libass renders it as a visible rectangle.
                    final_text = f"{{\\fs{top_fs}}}{{\\c&H808080}}{text}\\N{{\\rFaDefault}}{{\\fs{bot_fs}}}{{\\b1}}{sec_text_formatted}"
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

            # Use FaDefault style when primary lang is FA (RTL) and no secondary row.
            # In bilingual mode, Default is used for the top row and FaDefault is applied
            # inline (via {\rFaDefault}) for the bottom row.
            event_style = "FaDefault" if (lang == 'fa' and not secondary_map) else "Default"
            events.append(f"Dialogue: 0,{ass_start},{ass_end},{event_style},,0,0,0,,{final_text}")
        
        with open(ass_path, 'w', encoding='utf-8') as f:
            # Add BOM for good measure
            f.write('\ufeff' + header + "\n".join(events))
        
        self.logger.info(f"ASS asset generation complete: {Path(ass_path).name}")

    @staticmethod
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
            hours = total_sec // 3600
            mins  = (total_sec % 3600) // 60
            secs  = total_sec % 60

            def _fa(n: int) -> str:
                return str(n).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

            if lang == 'fa':
                if hours > 0:
                    return f'{_fa(hours)} ساعت و {_fa(mins)} دقیقه'
                elif secs >= 30:
                    return f'{_fa(mins)} دقیقه و {_fa(secs)} ثانیه'
                else:
                    return f'{_fa(mins)} دقیقه'
            else:
                if hours > 0:
                    return f'{hours} hr {mins} min'
                elif secs >= 30:
                    return f'{mins} min {secs} sec'
                else:
                    return f'{mins} min'
        except Exception:
            return ''

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
        # تغییر self._model به self.model
        if hasattr(self, 'model') and self.model is not None:
            self.logger.info("♻️ Force-unloading model to reclaim memory...")
            self.model = None
            
            # Python garbage collection
            gc.collect()
            
            # Metal / CUDA memory reclaim
            try:
                if HAS_TORCH and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            
            self.logger.info("✅ Memory reclamation sequence complete.")
            
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
    ) -> Dict[str, Any]:
        """Complete workflow with fixed path handling and memory management"""
        
        # Resolve absolute path to properly handle inputs
        video_path = os.path.abspath(video_path)
        self.logger.info(f"Processing sequence initiated: {Path(video_path).name}")
        
        result = {}
        temp_vid = None
        
        # ORIGINAL BASE: This is where ALL output files (SRT, ASS, Video) MUST go.
        # It should be based on the user's input file, not any temp/safe copies.
        original_dir = os.path.dirname(video_path)
        original_stem = Path(video_path).stem
        
        # If input is already a temp/safe file (e.g. from a previous step), try to clean it
        if "safe_input" in original_stem or "temp_" in original_stem:
            original_stem = re.sub(r'^(temp_\d+_|safe_)', '', original_stem)

        # Detect SRT-as-input: user passed a pre-existing transcript file directly.
        # Convention: file is named <base>_<lang>.srt — strip the `_<lang>` suffix so
        # that original_base points at the real base name (same as if the video was given).
        _is_srt_input = video_path.lower().endswith('.srt')
        if _is_srt_input:
            _srt_lang_suffix = f'_{source_lang}'
            if original_stem.endswith(_srt_lang_suffix):
                original_stem = original_stem[:-len(_srt_lang_suffix)]

        original_base = os.path.join(original_dir, original_stem)
        
        try:
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
            
            # 1. Transcription
            # Force SRT path to be at ORIGINAL location
            src_srt = f"{original_base}_{source_lang}.srt"
            
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
                # We pass the current_video_input (which might be temp/limited) to transcribe
                # BUT we need to ensure the OUTPUT saved is 'src_srt' (original path)
                # The transcribe_video method currently saves based on input name.
                # Let's rename it after generation if needed.
                
                _actual_dur = (limit_end - _limit_start) if limit_end is not None else 0
                generated_srt = self.transcribe_video(current_video_input, source_lang, correct, detect_speakers, dur=_actual_dur)
                
                # CRITICAL: Unload model immediately after heavy transcription to free RAM for rendering/translation
                self.cleanup()
                
                # If generated name != desired name, move it
                if os.path.abspath(generated_srt) != os.path.abspath(src_srt):
                    self.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
                    shutil.move(generated_srt, src_srt)
            
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
            
            # 📐 Merge short fragments into semantic clauses (shared with translation path)
            # Ensures bilingual ASS file has matching English/Persian line counts
            src_entries = self.merge_to_clauses(src_entries)
            
            with open(src_srt, 'w', encoding='utf-8-sig') as f:
                for idx, entry in enumerate(src_entries, 1):
                    f.write(f"{idx}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
            
            result[source_lang] = src_srt
            
            # 2. Translation
            for tgt in target_langs:
                if tgt == source_lang:
                    continue
                
                tgt_srt = f"{original_base}_{tgt}.srt"
                
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
                    
                    # Choose translation strategy based on llm_choice
                    translated = []
                    
                    # If user specified a particular LLM via --llm flag, respect that choice
                    if self.llm_choice == "gemini":
                        translated = self.translate_with_gemini(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "litellm":
                        translated = self.translate_with_litellm(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "minimax":
                        translated = self.translate_with_minimax(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "grok":
                        translated = self.translate_with_grok(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    else:
                        # Default: Use per-batch fallback chain for optimal rate limit distribution
                        # Each batch tries models in sequence: deepseek -> minimax -> gemini -> grok
                        translated = self.translate_with_batch_fallback_chain(
                            texts,
                            tgt,
                            source_lang,
                            original_entries=entries,
                            output_srt=tgt_srt,
                            existing_translations=recovered_map
                        )

                    
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
                        
                        # Ask user if they want to retry
                        print(f"\n⚠️  Translation incomplete for {tgt.upper()}: {untranslated_count} lines remain untranslated.")
                        print(f"   Translated: {total_count - untranslated_count}/{total_count} ({percentage:.1f}%)")
                        print(f"\n   Do you want to retry translating ONLY the {untranslated_count} untranslated lines? (y/n): ", end="")
                        
                        try:
                            response = input().strip().lower()
                        except (EOFError, KeyboardInterrupt):
                            response = 'n'
                            print()  # newline after interrupt
                        
                        if response not in ['y', 'yes']:
                            # Ask user if they want to proceed with incomplete translation
                            try:
                                print(f"\n⚠️ Translation is incomplete. Do you want to PROCEED with {percentage:.1f}% translated file? (y/n): ", end="")
                                proceed = input().strip().lower()
                            except (EOFError, KeyboardInterrupt):
                                proceed = 'n'
                                print()

                            if proceed in ['y', 'yes']:
                                self.logger.warning(f"❌ User declined retry but chose to proceed. Continuing with {percentage:.1f}% translated file.")
                                break
                            else:
                                self.logger.warning("❌ User declined retry and chose to abort. Halting workflow before rendering.")
                                return result
                        
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
            
            # 3. RENDERING
            if render:
                self.logger.info("Rendering sequence initiated.")
                
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
                    time_offset=_limit_start
                )
                
                # Output Video -> Original Base
                output_video = f"{original_base}_subbed.mp4"
                
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

                    render_cmd = [
                        "amir", "video", "cut",
                        safe_video_path,
                        "--subtitles", safe_ass_path,
                        "--output", safe_output_path,
                        "--display-input", os.path.basename(current_video_input),
                        "--display-output", os.path.basename(output_video),
                        "--render"
                    ]
                    
                    if fonts_dir:
                        render_cmd.extend(["--fonts-dir", fonts_dir])

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

                    # Execute and stream output
                    render_start_wall = time.time()
                    process = subprocess.Popen(
                        render_cmd,
                        env=current_env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    def _ffmpeg_time_to_seconds(t: str) -> float:
                        """Parse ffmpeg time string HH:MM:SS.xx to seconds"""
                        try:
                            parts = t.strip().split(':')
                            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                        except Exception:
                            return 0.0

                    for line in process.stdout:
                        # Forward the progress from video.sh
                        line_stripped = line.strip()
                        if not line_stripped:
                            continue
                        
                        # Filter out noisy logs (SVT, FFmpeg config, etc.)
                        if re.match(r'^Svt\[', line_stripped):
                            continue
                        if re.match(r'^ffmpeg version|^input #|^output #|^stream mapping', line_stripped, re.IGNORECASE):
                            continue
                        if 'bitrate=' not in line_stripped and line_stripped.startswith(('frame=', 'size=')):
                            continue

                        # Output progress in one line (\r for progress stats)
                        if line_stripped.startswith("frame=") or \
                           ("time=" in line_stripped and "bitrate=" in line_stripped):
                            # Parse time= field for progress display
                            time_match = re.search(r'time=(\S+)', line_stripped)
                            elapsed_wall = time.time() - render_start_wall
                            progress_str = ""
                            if time_match and render_total_duration > 0:
                                encoded_secs = _ffmpeg_time_to_seconds(time_match.group(1))
                                pct = min(encoded_secs / render_total_duration * 100, 100)
                                remaining = (render_total_duration - encoded_secs) / max(encoded_secs / elapsed_wall, 0.001) if encoded_secs > 0 else 0
                                elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed_wall))
                                remain_str  = time.strftime('%M:%S', time.gmtime(remaining))
                                progress_str = f" | {pct:5.1f}% | elapsed: {elapsed_str} | remaining: {remain_str}"
                            elif time_match:
                                elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed_wall))
                                progress_str = f" | elapsed: {elapsed_str}"
                            
                            # Use VT100 clear line to prevent word-wrapping spam on narrow terminals
                            out_str = f"{line_stripped}{progress_str}"[:110] # Cap length to avoid wrap
                            sys.stdout.write(f"\r\033[K{out_str}")
                            sys.stdout.flush()
                        else:
                            # Allow errors, warnings, completion events OR the Dashboard Table to print
                            if any(keyword in line_stripped.lower() for keyword in ['error', 'warning', 'failed', 'complete', 'finished', 'rendered']):
                                print(f"\n{line_stripped}", flush=True)
                            elif any(c in line_stripped for c in ['╭', '│', '╰', '─', '┌', '├', '└', '┬', '┼', '┴', '┐', '┤', '┘', '📥', '📤', '📊', '📈', '✅', '═']):
                                print(line_stripped, flush=True)
                        
                    process.wait()
                    print() # Final newline after loop finishes
                    
                    if process.returncode != 0:
                        self.logger.error("❌ Rendering failed in 'amir video' engine.")
                        return None
                        
                    self.logger.info("✅ Rendering completed successfully via centralized engine.")
                    
                    # 4. Move Result to Final Destination
                    if os.path.exists(output_video):
                        os.remove(output_video)
                    
                    shutil.move(safe_output_path, output_video)
                    result['rendered_video'] = output_video
                    self.logger.info(f"Rendering process finalized: {Path(output_video).name}")

            # Social post generation (auto-triggered when platforms list is given)
            if platforms:
                try:
                    self.generate_posts(original_base, source_lang, result, platforms=platforms,
                                        prompt_file=prompt_file, post_langs=post_langs)
                except Exception as _pe:
                    self.logger.warning(f"⚠️ Post generation failed (workflow continues): {_pe}")

            self.logger.info("Execution sequence finalized.")
            return result
        
        except Exception as e:
            self.logger.error(f"❌ Failed: {e}")
            raise
        
        finally:
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
                    f"🔹 [موضوع پنجم]: [یک جمله توصیفی ≤۱۲ کلمه]\n\n"
                    f"✨ [یک جمله — موضوع اصلی این ویدیو در یک خط]\n\n"
                    f"📌 [یک جمله — برای چه مخاطبی این ویدیو مفید است]\n\n"
                    f"⏱️ مدت: {_dur}\n\n"
                    f"#[هشتگ۱] #[هشتگ۲] #[هشتگ۳] #[هشتگ۴] #[هشتگ۵]\n\n"
                    f"اطلاعات ویدیو:\n"
                    f"عنوان اصلی: {title}\n"
                    f"مدت: {_dur}\n"
                    + (f"{_src_info_fa}\n" if _src_info_fa else "")
                    + f"زبان‌های زیرنویس: {', '.join(_lang_name_fa(l) for l in _all_langs)}\n\n"
                    f"محتوای زیرنویس:\n{full_text}\n\n"
                    f"⛔ قوانین اجباری — تخطی از اینها مجاز نیست:\n"
                    f"① همه بخش‌های قالب را بنویس: 🔴 + پاراگراف + 🚨 (۵ بخش 🔹) + ✨ + 📌 + ⏱️ + هشتگ‌ها\n"
                    f"② هرگز بخشی را حذف نکن\n"
                    f"③ دقیقاً ۵ بخش 🔹\n"
                    f"④ ⏱️ مدت را دقیقاً همان‌طور که در اطلاعات ویدیو آمده بنویس\n"
                    f"⑤ ۵ هشتگ مرتبط\n"
                    f"⑥ نقل‌قول داخل « »\n"
                    f"⑦ بین هر بخش یک خط خالی\n"
                    f"⑧ بدون markdown (نه ** نه __ نه *)\n"
                    f"⑨ کل پست فارسی (هشتگ‌ها می‌توانند انگلیسی باشند)\n"
                    f"⑩ هر 🔹 باید کوتاه باشد — حداکثر ۱۲ کلمه\n"
                    f"⑪ هدف ۸۵۰–۹۵۰ کاراکتر — با کوتاه کردن هر بخش به این محدوده برس"
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
                    f"🔹 [Topic 5]: [one descriptive sentence ≤12 words]\n\n"
                    f"\u2728 [One sentence: what is the main subject of this video]\n\n"
                    f"\U0001f4cc [One sentence: for which audience this video is relevant]\n\n"
                    f"{_duration_line}\n\n"
                    f"#[hashtag1] #[hashtag2] #[hashtag3] #[hashtag4] #[hashtag5]\n\n"
                    f"Video info:\n"
                    f"Original title: {title}\n"
                    f"Duration: {_dur_en}\n"
                    f"Subtitle languages: {', '.join(_all_langs)}\n\n"
                    f"Subtitle content:\n{full_text}\n\n"
                    f"⛔ MANDATORY RULES — no exceptions:\n"
                    f"① Write ALL sections: 📽️ title + subtitle line + 🔴 + paragraph + 🚨 (5× 🔹) + ✨ + 📌 + ⏱️ + hashtags\n"
                    f"② NEVER drop a section to shorten the post\n"
                    f"③ Exactly 5 bullet points (🔹) — not 3, not 4, exactly 5\n"
                    f"④ ⏱️ Duration: copy it exactly from the video info above — do not omit\n"
                    f"⑤ Exactly 5 relevant hashtags at the end\n"
                    f"⑥ Quote inside « » — not inside \" \"\n"
                    f"⑦ One blank line between every section\n"
                    f"⑧ NO markdown — no ** no __ no * — Telegram renders them as literal characters\n"
                    f"⑨ Entire post in {_lang_en}\n"
                    f"⑩ Each 🔹 must be brief — max 12 words\n"
                    f"⑪ Target 850–950 characters — shorten each section to fit, never drop sections"
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
            # Hard cap: Telegram caption limit is 1024 characters; trim at last newline
            if len(text) > 1024:
                cut = text[:1024].rfind('\n')
                text = text[:cut if cut > 900 else 1024].rstrip()
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
            ('\U0001f4cc',   '📌 call-to-action'),
            ('\u23f1',       '⏱️ duration'),
        ]:
            if marker not in text:
                missing.append(label)
        bullet_count = text.count('\U0001f539')
        if bullet_count < 5:
            missing.append(f'🔹 bullet points (found {bullet_count}, need 5)')
        if '#' not in text:
            missing.append('hashtags (#)')
        return (len(missing) == 0, missing)

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
                        with open(post_path, 'w', encoding='utf-8') as f:
                            f.write(post_text)
                        saved[f"{srt_lang}_{platform}"] = post_path
                        label = f"پست {platform} ({srt_lang.upper()})"
                        self.logger.info(f"📝 {label} saved: {Path(post_path).name}")
                        print(f"\n{'━'*60}\n📝  {label}:\n{'━'*60}\n{post_text}\n{'━'*60}\n")
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
            return [final_result[i] if final_result[i] is not None else texts[i] for i in range(len(texts))]
        
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
                    # Success is implied by progress bar advancing, no need to spam the console.
                    
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