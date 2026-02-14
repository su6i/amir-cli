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


class SubtitleProcessor:
    def __init__(self, api_key: str = None, model_size: str = 'medium'):
        self.api_key = api_key or self.load_api_key()
        self._model = None
        self.model_size = model_size

    @property
    def model(self):
        """Lazy load Whisper model to save memory if not transcribing"""
        if self._model is None:
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
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
        """Fix common Persian typography issues"""
        if not text: return text
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
        print(f"  Transcribing video ({language.upper()})...")
        
        segments, info = self.model.transcribe(
            video_path,
            language=language,
            word_timestamps=True,
            initial_prompt="I am transcribing a video for social media with clear punctuation and case sensitivity."
        )
        
        all_words = []
        pbar = tqdm(total=int(info.duration), unit="s", desc="  Processing audio")
        
        last_end = 0
        for segment in segments:
            if segment.words:
                all_words.extend(segment.words)
                diff = int(segment.end) - last_end
                if diff > 0:
                    pbar.update(diff)
                    last_end = int(segment.end)
        
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
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(resegmented_entries, 1):
                f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        
        return srt_path

    def resegment_to_sentences(self, words: List) -> List[Dict]:
        """Group words into single-line segments (max 42-55 chars) preventing dangling words"""
        entries = []
        current_words = []
        current_len = 0
        
        sentence_enders = ('.', '?', '!', '...', ':', ';')
        phrase_enders = (',', '،')
        
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
            last_word_ends_sentence = text.endswith(sentence_enders)
            
            # Start considering break at 30 chars
            if current_len > 30:
                # 1. Natural sentence end is best
                if last_word_ends_sentence:
                    # Look ahead: if next word is very short or also ends sentence, keep it!
                    if i + 1 < total:
                        next_w = words[i+1].word.strip()
                        if (len(next_w) < 10 or next_w.endswith(sentence_enders)) and current_len + len(next_w) < 55:
                            should_break = False # Merge for better flow
                        else:
                            should_break = True
                    else:
                        should_break = True
                
                # 2. Phrase end is second best
                elif text.endswith(phrase_enders) and current_len > 38:
                    should_break = True
                
                # 3. Hard limit with "Dangling Word" protection
                elif current_len > 45:
                    # If we break now, check what's left. If only 1-2 words are left in the whole sequence, just take them!
                    words_left = total - (i + 1)
                    if words_left <= 2 and words_left > 0:
                        # Don't break! Pull them in
                        pass 
                    else:
                        should_break = True
            
            if i == total - 1:
                should_break = True
                
            if should_break and current_words:
                t = " ".join([w.word.strip() for w in current_words])
                t = re.sub(r'\s+', ' ', t).strip()
                
                # Final check: if 't' is just one word, try to merge backwards if possible
                # (Logic handled by look-ahead above mostly)
                
                entries.append({
                    'start': self.format_time(current_words[0].start),
                    'end': self.format_time(current_words[-1].end),
                    'text': t
                })
                current_words = []
                current_len = 0
            
            i += 1
            
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
Translate EXACTLY what is said. Keep the tone (casual/funny/serious).
Use ZWNJ for prefixes like 'mi-' and 'nemi-'. 
DO NOT FORMALIZE (use 'hast' not 'mibashad').
Only output: number. Translation"""
        return f"Translate to {lang_name} with EXACT same tone and slang. Only output: number. Translation"

    def translate_with_deepseek(self, texts: List[str], target_lang: str, source_lang: str = 'en') -> List[str]:
        if not texts: return []
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        batch_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
        system_prompt = self.get_translation_prompt(target_lang)
        
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Translate these to {target_lang} with tone match:\n\n{batch_text}"}
                    ],
                    temperature=0.3,
                    max_tokens=4000
                )
                output = response.choices[0].message.content.strip()
                translations = []
                for line in output.split('\n'):
                    line = line.strip()
                    if not line: continue
                    trans = re.sub(r'^\d+[\.\)]\s*', '', line)
                    if target_lang == 'fa':
                        trans = self.fix_persian_text(trans)
                    translations.append(trans)
                
                if len(translations) >= len(texts):
                    return translations[:len(texts)]
            except Exception as e:
                print(f"    Translation error: {e}")
                time.sleep(2)
        return texts
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
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, e in enumerate(new_entries, 1):
                f.write(f"{i}\n{e['start']} --> {e['end']}\n{e['text']}\n\n")

    @staticmethod
    def split_text_smart(text: str, max_chars: int = 42) -> List[str]:
        """Split text while respecting word boundaries and punctuation"""
        if len(text) <= max_chars: return [text]
        
        parts = []
        words = text.split(' ')
        curr = ""
        
        sentence_enders = ('.', '?', '!', '...')
        phrase_enders = (',', '،', ';', ':')
        
        for word in words:
            # If adding this word exceeds limit
            if len(curr) + len(word) + 1 > max_chars:
                if curr:
                    parts.append(curr.strip())
                    curr = word
                else:
                    # Single word longer than limit (rare)
                    parts.append(word[:max_chars])
                    curr = word[max_chars:]
            else:
                curr = (curr + " " + word) if curr else word
                
                # If we have a punctuation and we are deep enough (e.g. > 70% of limit)
                # cut early to prevent sentence splitting across lines
                if word.endswith(sentence_enders) and len(curr) > (max_chars * 0.7):
                    parts.append(curr.strip())
                    curr = ""
                elif word.endswith(phrase_enders) and len(curr) > (max_chars * 0.85):
                    parts.append(curr.strip())
                    curr = ""
                    
        if curr:
            parts.append(curr.strip())
        return parts

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
        
        # Initial conversion
        subprocess.run(['ffmpeg', '-y', '-i', srt_path, '-f', 'ass', ass_path], capture_output=True, text=True)
        with open(ass_path, 'r', encoding='utf-8') as f: content = f.read()
        
        # Style logic
        style = f"Style: Default,{font_name},24,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,2,0,1,2,10,10,10,1"
        content = re.sub(r'^Style:\s*Default,.*$', style, content, flags=re.MULTILINE)
        
        if lang_code == 'fa':
            content = self.apply_farsi_reshaping(content)
            
        if secondary_srt and os.path.exists(secondary_srt):
            secondary_entries = self.extract_subtitles_from_srt(secondary_srt)
            
            # Ultra-Robust Time Normalization
            def norm(t):
                # Handle 00:00:01,500 -> 0:00:01.50
                t = t.replace(',', '.').strip()
                parts = t.split(':')
                if len(parts) == 3:
                    h, m, s = parts
                    # Remove leading 0 from hours if present (ASS style)
                    h = str(int(h))
                    # Truncate ms to 2 digits
                    if '.' in s:
                        base, ms = s.split('.')
                        s = f"{base}.{ms[:2]}"
                    return f"{h}:{m}:{s}"
                return t

            sec_texts = {f"{norm(e['start'])}-->{norm(e['end'])}": e['text'] for e in secondary_entries}
            
            def add_secondary(m):
                # ASS groups (1,2) are 0:00:00.00
                t1, t2, text = norm(m.group(1)), norm(m.group(2)), m.group(3)
                time_key = f"{t1}-->{t2}"
                sec_text = sec_texts.get(time_key, "")
                
                if sec_text:
                    if any('\u0600' <= c <= '\u06FF' for c in sec_text):
                        try:
                            import arabic_reshaper; from bidi.algorithm import get_display
                            sec_text = get_display(arabic_reshaper.reshape(sec_text), base_dir='R')
                        except: pass
                    return f"Dialogue: {m.group(0).split('Dialogue: ')[1].split(',', 9)[0]},{m.group(1)},{m.group(2)},Default,,0,0,0,,{text}\\N{sec_text}"
                return m.group(0)

            content = re.sub(r'Dialogue: [^,]+,(\d{1,2}:\d{2}:\d{2}\.\d{2}),(\d{1,2}:\d{2}:\d{2}\.\d{2}),[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,(.*)', add_secondary, content)

        with open(ass_path, 'w', encoding='utf-8') as f: f.write(content)

    def apply_farsi_reshaping(self, ass_content: str) -> str:
        try:
            import arabic_reshaper; from bidi.algorithm import get_display
            def reshape(m):
                prefix, text = m.group(1), m.group(2).replace('\u200f', '')
                if any('\u0600' <= c <= '\u06FF' for c in text):
                    return f"{prefix}{get_display(arabic_reshaper.reshape(text), base_dir='R')}"
                return f"{prefix}{text}"
            return re.sub(r'(Dialogue: [^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,)(.*)', reshape, ass_content)
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

    def run_workflow(self, video_path: str, source_lang: str, target_langs: List[str], render: bool = False, force: bool = False, correct: bool = False, limit: Optional[float] = None):
        print(f"🚀 Processing video: {video_path}")
        original_video = video_path
        original_base = os.path.splitext(original_video)[0]
        temp_video = None
        
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
            video_path = temp_video

        # Use original_base for SRT/ASS file naming to keep them near the original video
        base_path = original_base
        
        # 1. Source logic
        source_srt = self.find_existing_subtitle(base_path, source_lang)
        if not source_srt or force:
            # We transcribe the (possibly trimmed) video_path
            source_srt = self.transcribe_video(video_path, language=source_lang, correct=correct)
        
        # CRITICAL SYNC FIX: Early split (always run to ensure limits)
        print("  Standardizing synchronization (Sentence-Aware)...")
        entries = self.extract_subtitles_from_srt(source_srt)
        self.write_srt_file_with_split(source_srt, entries)
        
        # Reload split entries
        source_entries = self.extract_subtitles_from_srt(source_srt)
        source_texts = [e['text'] for e in source_entries]
        
        # 2. Translation logic
        result_files = {source_lang: source_srt}
        for target_lang in target_langs:
            if target_lang == source_lang: continue
            target_srt = f"{base_path}_{target_lang}.srt"
            
            if not os.path.exists(target_srt) or force:
                print(f"  Translating to {target_lang.upper()}...")
                translations = self.translate_with_deepseek(source_texts, target_lang)
                translated_entries = [{**e, 'text': t} for e, t in zip(source_entries, translations)]
                self.write_srt_file_with_split(target_srt, translated_entries)
            else:
                print(f"  Using existing translation: {Path(target_srt).name}")
                
            result_files[target_lang] = target_srt
            
        # 3. Rendering logic
        if render:
            success = False
            suffix = "_limit" if limit else ""
            if len(target_langs) >= 2:
                l1, l2 = target_langs[0], target_langs[1]
                print(f"  Creating bilingual rendering: {l1.upper()} + {l2.upper()}...")
                combined_ass = f"{base_path}_{l1}_{l2}{suffix}.ass"
                self.create_ass_with_font(result_files[l1], combined_ass, l1, secondary_srt=result_files[l2])
                output = f"{base_path}_{l1}_{l2}_subtitled{suffix}.mp4"
                success = self.render_video(video_path, combined_ass, output)
            else:
                target_lang = target_langs[0]
                srt = result_files[target_lang]
                ass = f"{base_path}_{target_lang}{suffix}.ass"
                self.create_ass_with_font(srt, ass, target_lang)
                output = f"{base_path}_{target_lang}_subtitled{suffix}.mp4"
                success = self.render_video(video_path, ass, output)
            
            if success:
                print(f"✅ Rendered: {Path(output).name}")
            else:
                print(f"❌ Rendering failed.")

        # Cleanup temp video
        if temp_video and os.path.exists(temp_video):
            try: os.remove(temp_video)
            except: pass
        
        return result_files
