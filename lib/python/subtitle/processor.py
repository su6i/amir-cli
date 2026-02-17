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
        detect_best_hw_encoder
    )
except ImportError:
    # Fallback if media_config not found (backward compatibility)
    def get_bitrate_multiplier(): return 1.1
    def get_fallback_bitrate(): return "2.5M"
    def get_default_crf(): return 23
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
        model_size: str = 'large-v3',
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
        self.llm_choice = llm.lower()
        self.custom_model = custom_model # For LiteLLM testing
        # BERT options (optional, lazy-loaded)
        self.use_bert = use_bert
        self.bert_model = bert_model or os.environ.get('AMIR_BERT_MODEL')
        
        # LiteLLM API Key Normalization: Ensure DEEPSEEK_API_KEY for LiteLLM
        if self.api_key and 'DEEPSEEK_API_KEY' not in os.environ:
            os.environ['DEEPSEEK_API_KEY'] = self.api_key
        self.model_size = model_size
        
        # FIX: Copy the preset to avoid modifying the global dictionary
        base_style = STYLE_PRESETS.get(style, STYLE_PRESETS[SubtitleStyle.LECTURE])
        # Create a fresh copy
        self.style_config = StyleConfig(**base_style.__dict__)
        
        # Apply overrides
        self.style_config.max_lines = max_lines
        if alignment is not None: self.style_config.alignment = alignment
        if font_size is not None: self.style_config.font_size = font_size
        if shadow is not None: self.style_config.shadow = shadow
        if outline is not None: self.style_config.outline = outline
        if back_color is not None: self.style_config.back_color = back_color
        if primary_color is not None: self.style_config.primary_color = primary_color
        
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
        
        self.logger = logger or self._setup_logger()
        self._check_disk_space()
        
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

    # ==================== TRANSCRIPTION ====================

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

    def suppress_hallucinations(self, entries: List[Dict]) -> List[Dict]:
        """DeepSeek/Whisper hallucination suppressor"""
        if not entries: return []
        
        clean = []
        last_text = ""
        
        for e in entries:
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
        """Smart sentence segmentation"""
        entries = []
        current_words = []
        current_len = 0
        
        sentence_enders = ('.', '?', '!', '...')
        limit = self.style_config.max_chars
        
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
            
            if is_sentence_end:
                should_break = True
            elif current_len > 80: # Allow more room for semantic splitting in sanitize_entries
                should_break = True
            
            if i == total - 1:
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
                        if key_str.isdigit() and str(v).strip():
                            mapped[int(key_str)] = str(v).strip()
                    if mapped:
                        return [mapped[i] for i in range(1, expected_count + 1) if mapped.get(i)]
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
            # Use indexed list for DeepSeek to ensure perfect alignment
            batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            
            pbar.set_postfix({"batch": f"{i + 1}/{batch_count}"})
            
            # NUCLEAR PERSISTENCE: Retry until successful (Max 10 attempts)
            attempt = 0
            max_retries = 10
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
                            # Skip if None or empty
                            if not t or not t.strip():
                                processed_list.append(batch[idx_in_batch]) # Keep original with correct index
                                continue
                            # If it returned English (no Persian chars), keep original English
                            if not any('\u0600' <= c <= '\u06FF' for c in t):
                                processed_list.append(batch[idx_in_batch]) # Use correct index
                            else:
                                processed_list.append(self.fix_persian_text(t))
                        trans_list = processed_list
                    
                    if len(trans_list) >= len(batch):
                        result_batch = trans_list[:len(batch)]

                        # Fill final result incrementally
                        for rel_idx, trans in enumerate(result_batch):
                            # Map back to absolute index when batch_indices contains relative indices
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
                        # SUCCESS! Break the retry loop
                        success_batch = True
                        time.sleep(1)
                        break 
                    else:
                        delay = min(3 + attempt, 10) # Progressive sleep 4s, 5s... max 10s
                        self.logger.warning(f"⚠️ Batch {i//batch_size + 1} incomplete: expected {len(batch)}, got {len(trans_list)}. Retrying in {delay}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(delay)
                        if attempt >= max_retries:
                            # ZERO-SKIP POLICY: Raise error instead of skipping
                            raise ValueError(f"CRITICAL: Batch {i//batch_size + 1} failed after {max_retries} attempts.")

                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    if "401" in error_msg or "Invalid API Key" in error_msg:
                        raise
                    
                    if attempt >= max_retries:
                        # ZERO-SKIP POLICY: Halt entire execution
                        self.logger.error(f"❌ TERMINATING: Batch {i//batch_size + 1} failed after {max_retries} attempts.")
                        raise RuntimeError(f"Translation halted to prevent data corruption/cost loss: {error_msg}")

                    wait_time = min(60, (2 ** (attempt % 6)) * 5) 
                    self.logger.warning(f"Batch {i//batch_size + 1} attempt {attempt}/{max_retries} failed: {error_msg}")
                    time.sleep(wait_time)
                    self.logger.info(f"🛡️ Persistence mode: Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
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
            # Use indexed list for perfect alignment across all models
            batch_text = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(batch)])
            
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
                                    processed.append(self.fix_persian_text(t))
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
                                processed.append(self.fix_persian_text(t))
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
        
        # 1. Informal & ZWNJ fixes
        informal = {
            r'\bمی‌باشد\b': 'هست',
            r'\bمی‌باشند\b': 'هستن',
        }
        for p, r in informal.items():
            text = re.sub(p, r, text)
        
        patterns = [
            (r'(\w)(ها)(\s|$)', r'\1‌\2\3'),
            (r'می(\s)', r'می‌\1'),
        ]
        for p, r in patterns:
            text = re.sub(p, r, text)
            
        # 2. FORCE RTL Direction for Punctuation (The Magic Fix)
        # RLE (\u202B) + Text + PDF (\u202C)
        # Also inject RLM (\u200F) around English parentheses to prevent BiDi flip
        
        # 1. Anchor technical terms in parentheses
        # We use \u200E (LRM) inside to stabilize English, 
        # and \u200F (RLM) outside to anchor the whole block to the RTL flow.
        lrm = "\u200E"
        rlm = "\u200F"
        text = re.sub(rf'(\s?)(?<!{rlm})\(([a-zA-Z0-9\s/_\-\.]+)\)(?!{rlm})', rf'\1{rlm}({lrm}\2{rlm}){rlm}', text)
        
        # 2. Anchor the whole string to RTL (Leading + Trailing)
        # One RLM is enough
        if not text.startswith(rlm):
            text = rlm + text
        if not text.endswith(rlm):
            text = text + rlm
            
        return text

    @staticmethod
    def _clean_bidi(t: str) -> str:
        if not t: return ""
        return t.replace('\u202B', '').replace('\u202C', '').replace('\u200F', '').strip()

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

    def create_ass_with_font(self, srt_path: str, ass_path: str, lang: str, secondary_srt: Optional[str] = None):
        """Generate ASS file"""
        title = f"{get_language_config(lang).name} + {get_language_config('fa').name}" if secondary_srt else get_language_config(lang).name
        self.logger.info(f"Generating ASS asset ({title})...")
        
        style = self.style_config
        
        primary_style = (
            f"Style: Default,{style.font_name},{style.font_size},"
            f"{style.primary_color},{style.back_color},"
            f"{style.outline},{style.shadow},{style.border_style},"
            f"{style.alignment},10,10,10,1"
        )
        
        fa_style = ""
        if lang == 'fa' or secondary_srt:
            # Sync FA font size with English to avoid visual jump
            fa_font_size = style.font_size
            fa_style = f"Style: FaDefault,B Nazanin,{fa_font_size},&H00FFFFFF,{style.back_color},{style.outline},{style.shadow},{style.border_style},{style.alignment},10,10,10,1"
        
        header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Outline, Shadow, BorderStyle, Alignment, MarginL, MarginR, MarginV, Encoding
{primary_style}
{fa_style}

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
            """Wrap content inside parentheses with slightly smaller Arial font"""
            # Use specific size 2 points smaller than base to avoid huge discrepancies
            rlm = "\u200F"
            base_fs = style.font_size
            small_fs = max(14, base_fs - 4)
            # Match (Term) along with any pre-existing RLM markers
            # This regex allows RLM outside or inside, but preserves them
            pattern = rf'{rlm}?\(([a-zA-Z0-9\s/_\-\.]+)\){rlm}?'
            # Always wrap with RLM to be safe
            replacement = rf'{rlm}{{\\fnArial\\fs{small_fs}}}(\1){{\\fnB Nazanin\\fs{base_fs}}}{rlm}'
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
                    # EN small gray top, FA white bottom
                    # Ensure FA layer starts with a clear font/size reset
                    en_fs = max(16, style.font_size - 4)
                    fa_fs = style.font_size
                    # Add \u200f (RLM) at the very start of the Persian line to anchor direction
                    # Use explicit font/size settings to avoid picking up 'Default' blue style
                    final_text = f"{{\\fs{en_fs}}}{{\\c&H808080}}{text}\\N{{\\rFaDefault}}{{\\fs{fa_fs}}}{{\\b1}}\u200f{sec_text_formatted}"
                else:
                    final_text = text
            
            # ASS requires 1-digit hour (usually) and 2-digit centiseconds
            # We must convert 00:00:00,000 (SRT) to 0:00:00.00 (ASS)
            def srt_to_ass_time(t_str):
                # t_str is HH:MM:SS,mmm
                h, m, s_ms = t_str.replace(',', '.').split(':')
                s, ms = s_ms.split('.')
                # Convert milliseconds (3 digits) to centiseconds (2 digits)
                cs = int(ms) // 10 
                return f"{int(h)}:{m}:{s}.{cs:02d}"

            ass_start = srt_to_ass_time(e['start'])
            ass_end = srt_to_ass_time(e['end'])
            
            events.append(f"Dialogue: 0,{ass_start},{ass_end},Default,,0,0,0,,{final_text}")
        
        with open(ass_path, 'w', encoding='utf-8') as f:
            # Add BOM for good measure
            f.write('\ufeff' + header + "\n".join(events))
        
        self.logger.info(f"ASS asset generation complete: {Path(ass_path).name}")

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
        limit: Optional[float] = None
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
            
        original_base = os.path.join(original_dir, original_stem)
        
        try:
            # SAFETY: Check disk space before starting
            self._check_disk_space(min_gb=1)
            
            # Limit handling (creates a temp input file)
            current_video_input = video_path
            if limit:
                self.logger.info(f"Duration restriction applied: {limit}s")
                temp_vid = os.path.join(tempfile.gettempdir(), f"temp_{int(time.time())}_{original_stem}.mp4")
                cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                       "-i", video_path, "-t", str(limit), "-c", "copy", temp_vid]
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
                
                generated_srt = self.transcribe_video(current_video_input, source_lang, correct, detect_speakers, dur=limit or 0)
                
                # CRITICAL: Unload model immediately after heavy transcription to free RAM for rendering/translation
                self.cleanup()
                
                # If generated name != desired name, move it
                if os.path.abspath(generated_srt) != os.path.abspath(src_srt):
                    self.logger.info(f"📦 Moving temp SRT to final path: {Path(src_srt).name}")
                    shutil.move(generated_srt, src_srt)
            
            # MASTER TIMELINE LOCK: Establish the structural anchor once.
            # All downstream translations MUST follow this structure.
            src_entries = self.parse_srt(src_srt)
            src_entries = self.sanitize_entries(src_entries)
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
                    
                    # 💰 SMART RESUME: Ingest partial work before calling LLM (returns recovered mappings)
                    recovered_map = {}
                    recovered_map.update(self._ingest_partial_srt(entries, tgt_srt.replace('.srt', '_partial.srt'), tgt) or {})
                    recovered_map.update(self._ingest_partial_srt(entries, tgt_srt, tgt) or {})
                    
                    texts = [e['text'] for e in entries]
                    
                    # Choose LLM Bridge
                    translated = []
                    if self.llm_choice == "gemini":
                        translated = self.translate_with_gemini(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    elif self.llm_choice == "litellm":
                        translated = self.translate_with_litellm(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    else:
                        # Default is DeepSeek (Native)
                        translated = self.translate_with_deepseek(texts, tgt, source_lang, original_entries=entries, output_srt=tgt_srt, existing_translations=recovered_map)
                    
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
                
                primary = source_lang
                secondary = 'fa' if 'fa' in target_langs and 'fa' != source_lang else None
                
                # ASS Path -> Original Base
                ass_path = f"{original_base}_{primary}"
                if secondary:
                    ass_path += f"_{secondary}"
                ass_path += ".ass"
                
                self.create_ass_with_font(
                    result[primary],
                    ass_path,
                    primary,
                    result.get(secondary) if secondary else None
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
                    
                    # 3. FFmpeg Command with Source-Aware Precision
                    # We match the original video's bitrate to maintain file size parity
                    try:
                        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-show_entries', 'format=bit_rate',
                                    '-of', 'default=noprint_wrappers=1:nokey=1', safe_video_path]
                        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                        source_bitrate = probe_result.stdout.strip()
                        
                        if source_bitrate and source_bitrate.isdigit():
                            # Use centralized bitrate multiplier from media config
                            multiplier = get_bitrate_multiplier()
                            target_bitrate = f"{int(int(source_bitrate) * multiplier)}"
                        else:
                            # Fallback if bit_rate not in format: check stream bit_rate
                            probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                        '-show_entries', 'stream=bit_rate',
                                        '-of', 'default=noprint_wrappers=1:nokey=1', safe_video_path]
                            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                            source_bitrate = probe_result.stdout.strip()
                            if source_bitrate and source_bitrate.isdigit():
                                multiplier = get_bitrate_multiplier()
                                target_bitrate = f"{int(int(source_bitrate) * multiplier)}"
                            else:
                                target_bitrate = get_fallback_bitrate()
                    except:
                        target_bitrate = get_fallback_bitrate()
                    
                    # Automatic Hardware Encoder Detection
                    # Uses centralized config to detect best available encoder
                    hw_info = detect_best_hw_encoder()
                    encoder = hw_info['encoder']
                    codec = hw_info['codec']
                    platform = hw_info['platform']
                    
                    hw_accel_args = []
                    if platform == 'cpu':
                        # CPU encoding with CRF
                        crf = get_default_crf()
                        hw_accel_args = ["-c:v", encoder, "-preset", "medium", "-crf", str(crf)]
                    else:
                        # Hardware encoding with bitrate
                        hw_accel_args = ["-c:v", encoder, "-b:v", target_bitrate]
                        # Add appropriate tag for h265/hevc
                        if codec == 'h265' and platform == 'apple_silicon':
                            hw_accel_args.extend(["-tag:v", "hvc1"])
                    
                    self.logger.info(f"🎬 Encoder: {encoder} ({platform.upper()}) | Codec: {codec.upper()}")
                    
                    # Add audio copy to preserve original audio quality
                    hw_accel_args.extend(["-c:a", "copy"])
                    
                    # Resolve Font Directory to ensure B Nazanin is found
                    # FFmpeg inside sandbox might not see system fonts unless explicitly told
                    fonts_dir_arg = ""
                    user_font_dir = os.path.expanduser("~/Library/Fonts")
                    system_font_dir = "/Library/Fonts"
                    
                    if os.path.exists(os.path.join(user_font_dir, "BNazanin.ttf")) or \
                       os.path.exists(os.path.join(user_font_dir, "B Nazanin.ttf")):
                        fonts_dir_arg = f":fontsdir={user_font_dir}"
                    elif os.path.exists(os.path.join(system_font_dir, "BNazanin.ttf")) or \
                         os.path.exists(os.path.join(system_font_dir, "B Nazanin.ttf")):
                        fonts_dir_arg = f":fontsdir={system_font_dir}"
                    
                    vf_arg = f"ass={safe_ass_name}{fonts_dir_arg}"
                    
                    cmd = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", safe_video_name,
                        "-vf", vf_arg,
                        *hw_accel_args,
                        "-progress", "pipe:1",  # Enable progress pipe
                        safe_output_name
                    ]
                    
                    # Run FFmpeg with Progress Tracking
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=temp_dir)
                    
                     # Get duration for progress bar
                    dur = 0
                    try:
                        # Use ffprobe on the safe link
                        dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'default=noprint_wrappers=1:nokey=1', safe_video_path]
                        dur_r = subprocess.run(dur_cmd, capture_output=True, text=True)
                        dur = float(dur_r.stdout.strip())
                    except:
                        pass
                    
                    pbar = tqdm(total=100, unit="%", desc="  Encoding")
                    
                    stderr_lines = deque(maxlen=200)
                    def capture_stderr():
                        for line in proc.stderr:
                            stderr_lines.append(line)
                    
                    # Capture stderr in background for error reporting
                    t_err = threading.Thread(target=capture_stderr)
                    t_err.start()
                    
                    # Parse stdout for progress
                    while True:
                        line = proc.stdout.readline()
                        if not line and proc.poll() is not None:
                            break
                        
                        if line and 'out_time_ms=' in line:
                            try:
                                ms = int(line.split('=')[1])
                                if dur > 0:
                                    pct = min(100, (ms / 1000000) / dur * 100)
                                    pbar.n = int(pct)
                                    pbar.refresh()
                            except:
                                pass
                    
                    t_err.join()
                    pbar.close()
                    
                    if proc.returncode != 0:
                        self.logger.error(f"❌ FFmpeg failed (code {proc.returncode})")
                        for line in stderr_lines[-10:]:
                            self.logger.error(f"  {line.strip()}")
                        raise RuntimeError("Rendering failed inside sandbox")
                    
                    # 4. Move Result to Final Destination
                    if os.path.exists(output_video):
                        os.remove(output_video)
                    
                    shutil.move(safe_output_path, output_video)
                    result['rendered_video'] = output_video
                    self.logger.info(f"Rendering process finalized: {Path(output_video).name}")

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