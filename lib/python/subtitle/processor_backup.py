# subtitle/processor.py
# Core Subtitle Processing Engine

import os
import re
import subprocess
import time
import json
import configparser
import tempfile
import shutil
from datetime import timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from openai import OpenAI

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

from faster_whisper import WhisperModel
from tqdm import tqdm

# Language configuration with native fonts
LANGUAGE_CONFIG = {
    'en': {'name': 'English', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'fa': {'name': 'Persian', 'font': 'B Nazanin', 'font_size': 0, 'rtl': True},
    'ar': {'name': 'Arabic', 'font': 'Arial', 'font_size': 0, 'rtl': True},
    'es': {'name': 'Spanish', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'fr': {'name': 'French', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'de': {'name': 'German', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'it': {'name': 'Italian', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'pt': {'name': 'Portuguese', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'ru': {'name': 'Russian', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'ja': {'name': 'Japanese', 'font': 'MS Gothic', 'font_size': 0, 'rtl': False},
    'ko': {'name': 'Korean', 'font': 'Malgun Gothic', 'font_size': 0, 'rtl': False},
    'zh': {'name': 'Chinese', 'font': 'SimHei', 'font_size': 0, 'rtl': False},
    'hi': {'name': 'Hindi', 'font': 'Mangal', 'font_size': 0, 'rtl': False},
    'tr': {'name': 'Turkish', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'nl': {'name': 'Dutch', 'font': 'Arial', 'font_size': 0, 'rtl': False},
    'mg': {'name': 'Malagasy', 'font': 'Arial', 'font_size': 0, 'rtl': False},
}

try:
    import platform
    import mlx_whisper
    HAS_MLX = True
except ImportError:
    HAS_MLX = False


class SubtitleProcessor:
    def __init__(self, api_key: str = None, model_size: str = 'large-v3'):
        self.api_key = api_key or self.load_api_key()
        self._model = None
        self.model_size = model_size

    @property
    def model(self):
        """Lazy load Whisper model to save memory if not transcribing"""
        if self._model is None:
            if HAS_MLX and platform.system() == "Darwin" and platform.machine() == "arm64":
                print(f"  🏎️ Using MLX Acceleration (GPU/Neural Engine) for {self.model_size}")
                # MLX loads models on the fly during transcribe, so we just set a flag
                self._model = "MLX"
                return self._model
                
            print(f"  🧠 Loading Whisper model ({self.model_size})...")
            # Determine best device
            device = "cpu"
            try:
                import torch
                if torch.cuda.is_available(): device = "cuda"
                # CTranslate2 does not support 'mps' directly, so we use CPU highly optimized
            except: pass
            
            self._model = WhisperModel(self.model_size, device=device, compute_type="int8")
        return self._model

    @staticmethod
    def load_api_key(config_file: str = '.config') -> str:
        """Load API key from env vars or config file"""
        if os.environ.get('DEEPSEEK_API'):
            return os.environ['DEEPSEEK_API']

        search_paths = [
            config_file,
            os.path.join(os.getcwd(), '.config'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '.config'),
            os.path.expanduser('~/.amir/config'),
            os.path.expanduser('~/.amir-cli/config'),
            os.path.expanduser('~/.config/amir/config'),
        ]

        for path in search_paths:
            if os.path.exists(path):
                config = configparser.ConfigParser()
                try:
                    config.read(path)
                    if 'DEFAULT' in config and 'DEEPSEEK_API' in config['DEFAULT']:
                        api_key = config['DEFAULT']['DEEPSEEK_API'].strip()
                        if api_key and api_key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                            return api_key
                except Exception:
                    continue
        
        raise ValueError("DeepSeek API key not found! Set DEEPSEEK_API env var or create ~/.amir/config")

    @staticmethod
    def format_time(seconds: float) -> str:
        """Convert seconds to SRT time format (00:00:00,000)"""
        td = timedelta(seconds=float(seconds))
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    @staticmethod
    def parse_srt_time(time_str: str) -> float:
        """Convert SRT time format to seconds"""
        hours, minutes, seconds = time_str.replace(',', '.').split(':')
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    @staticmethod
    def fix_persian_text(text: str) -> str:
        """Fix common Persian typography issues (2026 Standard)"""
        if not text: return text
        
        # 2026 Standard: Prefer informal/conversational forms
        informal_fixes = {
            r'\bمی‌باشد\b': 'هست',
            r'\bمی‌باشند\b': 'هستن',
            r'\bباشد\b': 'باشه',
            r'\bگردید\b': 'شد',
        }
        for pattern, replacement in informal_fixes.items():
            text = re.sub(pattern, replacement, text)

        patterns = [
            (r'(\w)(ها)(\s|$)', r'\1‌\2\3'),
            (r'(\w)(های)(\s|$)', r'\1‌\2\3'),
            (r'می(\s)', r'می‌\1'),
            (r'نمی(\s)', r'نمی‌\1'),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        
        fixes = {
            'صحبتهای': 'صحبت‌های', 'صحبتها': 'صحبت‌ها',
            'ویدیوهای': 'ویدیو‌های', 'ویدیوها': 'ویدیو‌ها',
            'فیلمهای': 'فیلم‌های', 'فیلمها': 'فیلم‌ها'
        }
        for k, v in fixes.items():
            text = text.replace(k, v)
        
        verb_stems = r'(کنم|کنی|کند|کنیم|کنید|کنند|شم|شی|شود|شیم|شید|شوند|رم|ری|رود|ریم|رید|روند|گم|گی|گوید|گیم|گید|گویند|دانم|دانی|داند|دانیم|دانید|دانند)'
        text = re.sub(r'(می|نمی)(' + verb_stems + r')', r'\1‌\2', text)
        return text

    def calculate_cps(self, text: str, start: str, end: str) -> float:
        """Calculate Characters Per Second (CPS)"""
        try:
            duration = self.parse_srt_time(end) - self.parse_srt_time(start)
            if duration <= 0: return 0
            # Strip HTML tags and special spaces for count
            clean_text = re.sub(r'<[^>]+>', '', text).replace('\u00A0', ' ').strip()
            return len(clean_text) / duration
        except:
            return 0

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def transcribe_video(self, video_path: str, language: str = 'en', correct: bool = False) -> str:
        """Transcribe video with word-level timestamps and punctuation support"""
        if self.model == "MLX":
            return self.transcribe_video_mlx(video_path, language, correct)
            
        print(f"  Transcribing video ({language.upper()})...")
        
        segments, info = self.model.transcribe(
            video_path,
            language=language,
            word_timestamps=True,
            initial_prompt="I am transcribing a video for social media with clear punctuation and case sensitivity."
        )
        
        all_words = []
        pbar = tqdm(total=int(info.duration), unit="s", desc="  Processing audio", dynamic_ncols=True)
        
        last_end = 0
        for segment in segments:
            # 2026 Fix: Update bar even if no words (silence/music)
            diff = int(segment.end) - last_end
            if diff > 0:
                pbar.update(diff)
                last_end = int(segment.end)
                
            if segment.words:
                all_words.extend(segment.words)
        
        # Ensure bar reaches 100%
        if last_end < int(info.duration):
            pbar.update(int(info.duration) - last_end)
            
        pbar.close()
        
        resegmented_entries = self.resegment_to_sentences(all_words)
        
        if correct and self.api_key:
            print(f"  Correcting transcription with DeepSeek context...")
            texts = [e['text'] for e in resegmented_entries]
            corrected_texts = self.correct_with_deepseek_block(texts, language)
            for i, text in enumerate(corrected_texts):
                if i < len(resegmented_entries):
                    resegmented_entries[i]['text'] = text

        srt_path = os.path.splitext(video_path)[0] + f"_{language}.srt"
        # 2026 Standard: UTF-8 with BOM for cross-platform support
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, entry in enumerate(resegmented_entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        
        return srt_path
        
    def transcribe_video_mlx(self, video_path: str, language: str = 'en', correct: bool = False) -> str:
        """Mac-specific transcription using MLX for extreme performance"""
        print(f"  🏎️ Transcribing with MLX Acceleration ({language.upper()})...")
        
        # MLX-Whisper does not have a native progress bar easily for long clips,
        # but the speed gain is usually massive.
        result = mlx_whisper.transcribe(
            video_path,
            language=language,
            path_or_hf_repo=f"mlx-community/whisper-{self.model_size}-mlx",
            word_timestamps=True,
            initial_prompt="I am transcribing a video for social media with clear punctuation and case sensitivity."
        )
        
        all_words = []
        for segment in result.get('segments', []):
            if 'words' in segment:
                for w in segment['words']:
                    # Mock the faster-whisper word object for compatibility
                    class WordObj:
                        def __init__(self, start, end, word):
                            self.start = start
                            self.end = end
                            self.word = word
                    all_words.append(WordObj(w['start'], w['end'], w['word']))
        
        resegmented_entries = self.resegment_to_sentences(all_words)
        
        if correct and self.api_key:
            print(f"  Correcting transcription with DeepSeek context...")
            texts = [e['text'] for e in resegmented_entries]
            corrected_texts = self.correct_with_deepseek_block(texts, language)
            for i, text in enumerate(corrected_texts):
                if i < len(resegmented_entries):
                    resegmented_entries[i]['text'] = text

        srt_path = os.path.splitext(video_path)[0] + f"_{language}.srt"
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, entry in enumerate(resegmented_entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        
        return srt_path

    def resegment_to_sentences(self, words: List) -> List[Dict]:
        """Group words into semantic sentences (max 40 chars) following 2026 standards"""
        entries = []
        current_words = []
        current_len = 0
        
        sentence_enders = ('.', '?', '!', '...')
        phrase_enders = (',', '،', ':', ';')
        
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
            is_end_of_sentence = text.endswith(sentence_enders)
            is_end_of_phrase = text.endswith(phrase_enders)
            
            # 2026 Standard: Max 40 chars
            limit = 40
            
            # 1. Break at sentence ender
            if is_end_of_sentence:
                # Merge tiny sentences if they fit under limit
                if current_len < 15 and i + 1 < total:
                    next_w = words[i+1].word.strip()
                    if current_len + len(next_w) < limit:
                        should_break = False
                    else:
                        should_break = True
                else:
                    should_break = True
            
            # 2. Break at phrases or length limits
            elif current_len > 30:
                if is_end_of_phrase:
                    should_break = True
                elif current_len > limit:
                    should_break = True
            
            if i == total - 1:
                should_break = True
                
            if should_break and current_words:
                t = " ".join([w.word.strip() for w in current_words])
                t = re.sub(r'\s+', ' ', t).strip()
                
                # 2026 Standard: Fix orphans with NBSP and ensure min 3 words
                words_in_t = t.split()
                if len(words_in_t) >= 3:
                    # Connect last two words with NBSP (\u00A0)
                    t = " ".join(words_in_t[:-2]) + " " + words_in_t[-2] + "\u00A0" + words_in_t[-1]
                
                entries.append({
                    'start': self.format_time(current_words[0].start),
                    'end': self.format_time(current_words[-1].end),
                    'text': t
                })
                current_words = []
                current_len = 0
            
            i += 1
            
        # EXTRA PROTECTION: Backward merge for orphans (less than 3 words)
        if len(entries) >= 2:
            last = entries[-1]
            if len(last['text'].split()) < 3:
                prev = entries[-2]
                prev['end'] = last['end']
                prev['text'] = f"{prev['text']} {last['text']}".replace('\u00A0', ' ')
                # Re-apply NBSP to the new combined text
                ws = prev['text'].split()
                if len(ws) >= 2:
                    prev['text'] = " ".join(ws[:-2]) + " " + ws[-2] + "\u00A0" + ws[-1]
                entries.pop()

        return entries

    def correct_with_deepseek_block(self, lines: List[str], lang: str) -> List[str]:
        """Correct a whole block of transcript while maintaining line count"""
        if not lines: return []
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        
        # We send as numbered lines to help model maintain mapping
        prompt = f"""You are a professional editor. Correct this transcription in {lang}.
1. Fix grammar, punctuation, and capitalization.
2. Keep the EXACT same number of lines.
3. Keep the content faithful to the spoken word.
4. DO NOT merge or split lines. Each line must correspond 1:1 to the input.
5. Return ONLY the corrected lines, one per line, without numbers.

Input:
""" + "\n".join(lines)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                stream=False
            )
            corrected_text = response.choices[0].message.content.strip()
            # Split and clean
            corrected_lines = [l.strip() for l in corrected_text.split('\n') if l.strip()]
            
            # If model failed to keep count, fallback to original or try to adjust
            if len(corrected_lines) != len(lines):
                print(f"  ⚠️ Warning: DeepSeek changed line count ({len(corrected_lines)} vs {len(lines)}). Using fallback.")
                return lines
            return corrected_lines
        except Exception as e:
            print(f"  ⚠️ Correction failed: {e}")
            return lines

    def get_translation_prompt(self, target_lang: str) -> str:
        lang_name = LANGUAGE_CONFIG.get(target_lang, {}).get('name', target_lang)
        if target_lang == 'fa':
            return f"""You are a professional Persian translator for YouTube/TikTok. 
Translate EXACTLY what is said, but keep it CONCEPTUAL and CONCISE.
1. Use informal/conversational tone ('hast' not 'mibashad').
2. SUMMARIZE if the original text is too long (keep it under 40 characters if possible).
3. Use ZWNJ for prefixes (mi-, nemi-).
4. Only output: number. Translation"""
        return f"Translate to {lang_name} with EXACT same tone and slang. Keep it CONCISE for subtitle constraints. Only output: number. Translation"

    def translate_with_deepseek(self, texts: List[str], target_lang: str, source_lang: str = 'en') -> List[str]:
        if not texts: return []
        if target_lang == source_lang: return texts
        
        # 2026 Professional Batching (15 lines at a time for maximum DeepSeek attention)
        batch_size = 15
        all_translations = []
        
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        system_prompt = self.get_translation_prompt(target_lang)
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_text = "\n".join([f"{j+1}. {t}" for j, t in enumerate(batch)])
            
            translated_batch = None
            for attempt in range(3):
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Translate these to {target_lang} (MANDATORY):\n\n{batch_text}"}
                        ],
                        temperature=0.2, # Lower temperature for less echoing
                        max_tokens=4000
                    )
                    output = response.choices[0].message.content.strip()
                    translations = []
                    for line in output.split('\n'):
                        line = line.strip()
                        if not line: continue
                        trans = re.sub(r'^\d+[\.\)]\s*', '', line)
                        
                        # ANTI-ECHO PROTECTION: If the AI returned English instead of Persian, fail the batch
                        if target_lang == 'fa' and not any('\u0600' <= c <= '\u06FF' for c in trans):
                            # Skip check if it's numbers or short tags
                            if len(trans) > 5:
                                continue 
                                
                        if target_lang == 'fa':
                            trans = self.fix_persian_text(trans)
                        translations.append(trans)
                    
                    if len(translations) >= len(batch):
                        translated_batch = translations[:len(batch)]
                        break
                except Exception as e:
                    print(f"    Translation error: {e}")
                    time.sleep(2)
            
            if translated_batch:
                all_translations.extend(translated_batch)
            else:
                print(f"  ❌ FAILED to translate batch {i//batch_size + 1}")
                # Use a clear marker that isn't the original English
                all_translations.extend([f"((ترجمه ناموفق: {t}))" for t in batch])
        
        return all_translations
    @staticmethod
    def clean_subtitle_line(text: str) -> str:
        """Remove trailing punctuation and internal newlines"""
        text = text.strip()
        if not text: return text
        while text and text[-1] in ".،,؟!?…":
            text = text[:-1].strip()
        text = text.replace('\n', ' ').replace('\r', ' ')
        return re.sub(r'\s+', ' ', text)

    def write_srt_file_with_split(self, srt_path: str, entries: List[Dict]) -> None:
        """Write SRT with smart splitting logic (CRITICAL for sync)"""
        new_entries = []
        for entry in entries:
            text = self.clean_subtitle_line(entry['text'])
            # Enforce 42 chars for 2026 standards
            parts = self.split_text_smart(text, max_chars=42)
            
            if len(parts) == 1:
                new_entries.append({'start': entry['start'], 'end': entry['end'], 'text': parts[0]})
            else:
                s_sec = self.parse_srt_time(entry['start'])
                e_sec = self.parse_srt_time(entry['end'])
                dur = e_sec - s_sec
                total_chars = sum(len(p) for p in parts)
                curr = s_sec
                for p in parts:
                    # Precise interpolation
                    p_dur = dur * (len(p) / total_chars)
                    nxt = min(curr + p_dur, e_sec)
                    if nxt > curr:
                        new_entries.append({'start': self.format_time(curr), 'end': self.format_time(nxt), 'text': p})
                        curr = nxt
        with open(srt_path, 'w', encoding='utf-8-sig') as f:
            for i, e in enumerate(new_entries, 1):
                cps = self.calculate_cps(e['text'], e['start'], e['end'])
                if cps > 20:
                    print(f"  ⚠️ Warning: High CPS ({cps:.1f}) at {e['start']}. Text may be too long for reading.")
                f.write(f"{i}\n{e['start']} --> {e['end']}\n{e['text']}\n\n")

    @staticmethod
    def split_text_smart(text: str, max_chars: int = 40) -> List[str]:
        """2026 Standard: Split text while respecting 50-50 balance and no orphans"""
        if len(text) <= max_chars: return [text]
        
        words = text.split(' ')
        if len(words) < 6: return [text] # Too short to split balanced
        
        # 2026 Standard: Balanced 50-50 split
        mid = len(words) // 2
        # Ensure at least 3 words on each side
        if mid < 3: mid = 3
        if len(words) - mid < 3: mid = len(words) - 3
        
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        
        # Apply NBSP to second line to prevent final orphan
        w2 = line2.split()
        if len(w2) >= 2:
            line2 = " ".join(w2[:-2]) + " " + w2[-2] + "\u00A0" + w2[-1]
            
        return [line1, line2]

    def extract_subtitles_from_srt(self, srt_path: str) -> List[Dict]:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)'
        return [{'index': int(m[0]), 'start': m[1], 'end': m[2], 'text': m[3].strip()} for m in re.findall(pattern, content, re.DOTALL)]

    def find_existing_subtitle(self, base_path: str, lang_code: str) -> Optional[str]:
        lang_name = LANGUAGE_CONFIG.get(lang_code, {}).get('name', '').lower()
        possible = [f"{base_path}_{lang_code}.srt", f"{base_path}_{lang_name}.srt"]
        if lang_code == 'en': possible.insert(0, f"{base_path}.srt")
        elif lang_code == 'fa': possible.extend([f"{base_path}_farsi.srt", f"{base_path}_persian.srt"])
        return next((f for f in possible if os.path.exists(f)), None)

    def create_ass_with_font(self, srt_path: str, ass_path: str, lang_code: str = 'en', secondary_srt: str = None) -> None:
        lang_config = LANGUAGE_CONFIG.get(lang_code, LANGUAGE_CONFIG['en'])
        font_name = lang_config['font']
        
        # تبدیل اولیه به ASS
        subprocess.run(['ffmpeg', '-y', '-i', srt_path, '-f', 'ass', ass_path], capture_output=True, text=True)
        with open(ass_path, 'r', encoding='utf-8') as f: content = f.read()
        
        # استایل حرفهای ۲۰۲۶: 
        # BorderStyle=3 (باکس نیمهشفاف) | Outline=1 (ضخامت حاشیه باکس) | Shadow=0
        # BackColour=&H80000000 (شفافیت ۵۰٪ مشکی) | Encoding=178 (فارسی)
        style = f"Style: Default,{font_name},28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,3,1,0,2,10,10,22,178"
        content = re.sub(r'^Style:\s*Default,.*$', style, content, flags=re.MULTILINE)
        
        if secondary_srt and os.path.exists(secondary_srt):
            # 2026 Robust Mapping Strategy: Time-Based Alignment
            # This prevents desync if line counts differ between source and target
            secondary_entries = self.extract_subtitles_from_srt(secondary_srt)
            # Map by start time (rounded/cleaned to match ASS format)
            sec_texts_by_time = {e['start'].replace(',', '.'): e['text'] for e in secondary_entries}
            
            def add_secondary(m):
                start_time = m.group(1)
                full_line = m.group(0)
                parts = full_line.split(',', 9)
                text = m.group(3).strip()
                
                # Find matching secondary text by time
                sec_text = sec_texts_by_time.get(start_time, "").strip()
                
                # If no EXACT match, look for a "fuzzy" match (within 0.1s)
                if not sec_text:
                    for time_key, val in sec_texts_by_time.items():
                        if time_key[:7] == start_time[:7]: # Match up to 0.1s
                            sec_text = val
                            break

                if sec_text:
                    RLE, PDF = '\u202B', '\u202C'
                    if any('\u0600' <= c <= '\u06FF' for c in sec_text):
                        try:
                            import arabic_reshaper
                            sec_text = arabic_reshaper.reshape(sec_text)
                        except: pass
                    
                    styled_en = f"{{\\bord0}}{{\\fs15}}{{\\c&H00FFFF&}}{text}"
                    styled_fa = f"{{\\fnB Nazanin}}{{\\b1}}{{\\fs25}}{{\\c&HFFFFFF&}}{RLE}{sec_text}{PDF}"
                    return f"{parts[0]},{m.group(1)},{m.group(2)},Default,,0,0,0,,{{\\q2}}{styled_en}\\N{styled_fa}"
                return full_line

            # Robust Regex for Dialogue lines
            content = re.sub(r'Dialogue: [^,]*,(\d{1,2}:\d{2}:\d{2}\.\d{2}),(\d{1,2}:\d{2}:\d{2}\.\d{2}),[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[\s]?(.*)', add_secondary, content)

        with open(ass_path, 'w', encoding='utf-8') as f: f.write(content)

    def apply_farsi_reshaping(self, ass_content: str) -> str:
        try:
            import arabic_reshaper; from bidi.algorithm import get_display
            def reshape(m):
                prefix, text = m.group(1), m.group(2).replace('\u200f', '').strip()
                if any('\u0600' <= c <= '\u06FF' for c in text):
                    # RLE/PDF for single-language FA as well
                    RLE, PDF = '\u202B', '\u202C'
                    import arabic_reshaper
                    # Shaping only, let the engine handle BiDi via Unicode Embedding
                    reshaped = arabic_reshaper.reshape(text)
                    # Apply fs25, B Nazanin, and wrap in RLE/PDF
                    return f"{prefix}{{\\fnB Nazanin}}{{\\b1}}{{\\fs25}}{RLE}{reshaped}{PDF}"
                return f"{prefix}{text}"
            # Use [^,]* for empty fields
            return re.sub(r'(Dialogue: [^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,)(.*)', reshape, ass_content)
        except ImportError:
            return ass_content

    def render_video(self, video_path: str, ass_path: str, output_path: str) -> bool:
        """Render video using temporary symlinks to bypass FFmpeg escaping hell"""
        duration = self.get_video_duration(video_path)
        
        # 1. Clean old output
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass
            
        print(f"  Rendering video with subtitles...")
        
        # 2. Safe Symlink Strategy
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_video = Path(tmpdir) / "video.mp4"
            tmp_ass = Path(tmpdir) / "sub.ass"
            tmp_out = Path(tmpdir) / "out.mp4"
            
            try:
                os.symlink(os.path.abspath(video_path), tmp_video)
                os.symlink(os.path.abspath(ass_path), tmp_ass)
            except Exception as e:
                print(f"❌ Symlink creation failed: {e}")
                # Fallback to copy if symlink fails (rare)
                shutil.copy(video_path, tmp_video)
                shutil.copy(ass_path, tmp_ass)

            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-i', str(tmp_video),
                '-vf', f"ass=filename='{tmp_ass}'",
                '-c:a', 'copy', '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-progress', 'pipe:1',
                str(tmp_out)
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            pbar = tqdm(total=100, unit="%", desc="  Encoding video")
            
            stderr_output = []
            import threading
            def capture_stderr():
                for line in process.stderr:
                    stderr_output.append(line)
            
            stderr_thread = threading.Thread(target=capture_stderr)
            stderr_thread.start()

            try:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if 'out_time_ms=' in line:
                        try:
                            time_ms = int(line.split('=')[1])
                            pct = min(100.0, (time_ms / 1000000) / duration * 100) if duration > 0 else 0
                            pbar.n = int(pct)
                            pbar.refresh()
                        except: pass
            finally:
                stderr_thread.join()
                pbar.close()
            
            if process.returncode != 0:
                print(f"\n❌ FFmpeg error (Code {process.returncode}):")
                print("".join(stderr_output))
                return False
                
            if os.path.exists(tmp_out):
                shutil.move(tmp_out, output_path)
                return True
                
        return False

    def get_srt_path(self, base_path: str, lang: str, limit: Optional[float] = None) -> str:
        """Single source of truth for SRT file naming"""
        suffix = "_limit" if limit else ""
        return f"{base_path}_{lang}{suffix}.srt"

    def run_workflow(self, video_path: str, source_lang: str, target_langs: List[str], render: bool = False, force: bool = False, correct: bool = False, limit: Optional[float] = None):
        print(f"🚀 Processing video: {video_path}")
        original_video = video_path
        original_base = os.path.splitext(original_video)[0]
        temp_video = None
        
        # 0. Prep work: Limit & Base Path
        if limit:
            print(f"  ⏳ Global Limit active: Trimming first {limit}s...")
            temp_video = os.path.join(tempfile.gettempdir(), f"amir_limit_{int(time.time())}.mp4")
            trim_cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-i', original_video,
                '-t', str(limit),
                '-c', 'copy', temp_video
            ]
            subprocess.run(trim_cmd)
            # video_path now refers to the trimmed version for transcription
            video_path = temp_video

        # 1. Source logic (Modular Transcription)
        # We always want the source SRT to match the limit mode
        source_srt_path = self.get_srt_path(original_base, source_lang, limit)
        
        if not os.path.exists(source_srt_path) or force:
            # transcribe_video returns the path of the created file
            actual_source_srt = self.transcribe_video(video_path, language=source_lang, correct=correct)
            # Move to the correct final path if it was created in a temp location
            if actual_source_srt != source_srt_path:
                shutil.move(actual_source_srt, source_srt_path)
        
        # 2. Standardization (Source of Truth for Timecodes)
        print("  Standardizing synchronization (Sentence-Aware)...")
        source_entries = self.extract_subtitles_from_srt(source_srt_path)
        self.write_srt_file_with_split(source_srt_path, source_entries)
        
        # Reload after split to ensures 100% sync
        source_entries = self.extract_subtitles_from_srt(source_srt_path)
        source_texts = [e['text'] for e in source_entries]
        
        # 3. Translation logic (Explicit Mapping)
        result_files = {source_lang: source_srt_path}
        for target_lang in target_langs:
            if target_lang == source_lang: continue
            
            target_srt_path = self.get_srt_path(original_base, target_lang, limit)
            
            if not os.path.exists(target_srt_path) or force:
                print(f"  Translating to {target_lang.upper()} (DeepSeek Batched)...")
                translations = self.translate_with_deepseek(source_texts, target_lang)
                
                # Write translation using PRECISE source entries (time-locked)
                with open(target_srt_path, 'w', encoding='utf-8-sig') as f:
                    for i, (orig_entry, trans_text) in enumerate(zip(source_entries, translations), 1):
                        f.write(f"{i}\n{orig_entry['start']} --> {orig_entry['end']}\n{trans_text}\n\n")
            else:
                print(f"  Using existing translation: {Path(target_srt_path).name}")
                
            result_files[target_lang] = target_srt_path
            
        # 4. Rendering logic (Data-Driven)
        if render:
            success = False
            suffix = "_limit" if limit else ""
            if len(target_langs) >= 2:
                # Use the ACTUAL files produced in previous steps
                l1, l2 = target_langs[0], target_langs[1]
                print(f"  Creating bilingual rendering: {l1.upper()} + {l2.upper()}...")
                combined_ass = f"{original_base}_{l1}_{l2}{suffix}.ass"
                self.create_ass_with_font(result_files[l1], combined_ass, l1, secondary_srt=result_files[l2])
                output = f"{original_base}_{l1}_{l2}_subtitled{suffix}.mp4"
                success = self.render_video(video_path, combined_ass, output)
            else:
                target_lang = target_langs[0]
                srt = result_files[target_lang]
                ass = f"{original_base}_{target_lang}{suffix}.ass"
                self.create_ass_with_font(srt, ass, target_lang)
                output = f"{original_base}_{target_lang}_subtitled{suffix}.mp4"
                success = self.render_video(video_path, ass, output)
            
            if success:
                print(f"✅ Rendered: {Path(output).name}")
            else:
                print(f"❌ Rendering failed.")

        # 5. Cleanup
        if temp_video and os.path.exists(temp_video):
            try: os.remove(temp_video)
            except: pass
        
        return result_files
