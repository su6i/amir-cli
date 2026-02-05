# video_multilang_translate.py
# Multi-language subtitle generator with DeepSeek API + automatic font configuration

from faster_whisper import WhisperModel
from openai import OpenAI
import argparse
import os
import re
import subprocess
from datetime import timedelta
import configparser
import shutil
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import time

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass


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
}


def format_time(seconds: float) -> str:
    """Convert seconds to SRT time format (00:00:00,000)"""
    td = timedelta(seconds=float(seconds))
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def parse_srt_time(time_str: str) -> float:
    """Convert SRT time format to seconds"""
    hours, minutes, seconds = time_str.replace(',', '.').split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def load_api_key(config_file: str = '.config') -> str:
    """Load API key from env vars or config file"""
    # 1. Check environment variable first
    if os.environ.get('DEEPSEEK_API'):
        return os.environ['DEEPSEEK_API']

    # 2. Define search paths
    search_paths = [
        config_file,                                      # CWD/.config
        os.path.join(os.getcwd(), '.config'),            # Explicit CWD
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.config'), # Script dir
        os.path.expanduser('~/.amir/config'),            # ~/.amir/config
        os.path.expanduser('~/.amir-cli/config'),        # ~/.amir-cli/config
        os.path.expanduser('~/.config/amir/config'),     # XDG style
    ]

    # 3. Search for config file and valid key
    found_config = None
    for path in search_paths:
        if os.path.exists(path):
            config = configparser.ConfigParser()
            try:
                config.read(path)
                if 'DEFAULT' in config and 'DEEPSEEK_API' in config['DEFAULT']:
                    api_key = config['DEFAULT']['DEEPSEEK_API'].strip()
                    if api_key and api_key != "REPLACE_WITH_YOUR_KEY" and api_key != "sk-your-key":
                        return api_key
            except Exception:
                continue
            # Store the first existing config even if invalid, for error reporting
            if not found_config:
                found_config = path
            
    if not found_config:
        # If no config found and no env var, raise error with helpful message
        raise FileNotFoundError(
            "DeepSeek API key not found!\n"
            "Please set 'DEEPSEEK_API' environment variable OR\n"
            "Create a config file at '~/.amir/config' with content:\n"
            "[DEFAULT]\n"
            "DEEPSEEK_API = your_key_here"
        )
    
    raise ValueError(f"DEEPSEEK_API not found or invalid in {found_config} (and other searched paths)!")


def fix_persian_text(text: str) -> str:
    """Fix common Persian typography issues"""
    if not text:
        return text
    
    # Fix ZWNJ (Zero Width Non-Joiner) - نیم‌فاصله
    # Add ZWNJ between repeated letters that should be separate
    patterns = [
        (r'(\w)(ها)(\s|$)', r'\1‌\2\3'),  # کتابها → کتاب‌ها
        (r'(\w)(های)(\s|$)', r'\1‌\2\3'), # کتابهای → کتاب‌های
        (r'می(\s)', r'می‌\1'),             # می کنم → می‌کنم
        (r'نمی(\s)', r'نمی‌\1'),           # نمی کنم → نمی‌کنم
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    
    # Fix common word breaks
    text = text.replace('صحبتهای', 'صحبت‌های')
    text = text.replace('صحبتها', 'صحبت‌ها')
    text = text.replace('ویدیوهای', 'ویدیو‌های')
    text = text.replace('ویدیوها', 'ویدیو‌ها')
    text = text.replace('فیلمهای', 'فیلم‌های')
    text = text.replace('فیلمها', 'فیلم‌ها')
    
    # Fix common attached prefixes (Experimental but useful for common verbs)
    verb_stems = r'(کنم|کنی|کند|کنیم|کنید|کنند|شم|شی|شود|شیم|شید|شوند|رم|ری|رود|ریم|رید|روند|گم|گی|گوید|گیم|گید|گویند|دانم|دانی|داند|دانیم|دانید|دانند)'
    text = re.sub(r'(می|نمی)(' + verb_stems + r')', r'\1‌\2', text)

    return text


def get_translation_prompt(target_lang: str, source_lang_name: str, target_lang_name: str) -> str:
    if target_lang == 'fa':
        return f"""تو یک مترجم حرفه‌ای و بسیار دقیق فارسی هستی که در ترجمه زیرنویس ویدیوهای یوتیوب، تیک‌تاک، اینستاگرام و سخنرانی‌های روزمره تخصص داری.

وظیفه تو اینه که دقیقاً همون چیزی که گوینده گفته رو به فارسی ترجمه کنی — نه بیشتر، نه کمتر، نه رسمی‌تر، نه ادبی‌تر.

قوانین طلایی (حتماً رعایت کن، وگرنه شکست خوردی):

۱. لحن دقیقاً مثل گوینده باشه:
   - اگه عامیانه و خودمونی حرف زده → تو هم خودمونی و عامیانه بنویس (مثل: "داداش"، "وای"، "جدی؟"، "نه بابا"، "آخه چی؟")
   - اگه شوخی کرده → شوخی رو زنده نگه دار
   - اگه عصبانی، هیجان‌زده، شوکه، خنده‌داره → همون حس رو منتقل کن
   - اگه با لهجه یا تپق حرف زده → تا حد ممکن همون حس رو بده (مثلاً "اِ... خب..." یا "من... یعنی...")

۲. نگارش استاندارد فارسی (خیلی مهم):
   - حتماً از "نیم‌فاصله" (ZWNJ) برای پیشوند "می" و "نمی" استفاده کن.
   - غلط: نمیکنم، نمیرم، میگم
   - صحیح: نمی‌کنم، نمی‌رم، می‌گم
   - غلط: کتابها، اینها
   - صحیح: کتاب‌ها، این‌ها

۳. اصلاً رسمی نکن! (مگر اینکه گوینده رسمی باشه):
   - "می‌باشد" → "هست" یا "ئه"
   - "شما" → "تو" (اگه صمیمیه)

۴. عبارات روزمره و اسلنگ رو درست ترجمه کن:
   - "bro" → "داداش" یا "برادر" (بسته به لحن)
   - "no way" → "نه بابا"، "مگه میشه؟"

۵. فقط ترجمه کن. هیچ توضیحی نده. فقط شماره + ترجمه.

مثال:
1. I'm not doing this.
→ ۱. من این کار رو نمی‌کنم.

2. Wait what? No way bro that can't be real
→ ۲. چی؟ نه بابا مگه میشه این واقعیه داداش؟

حالا دقیقاً با همین سبک و دقت تمام جملات زیر رو ترجمه کن:"""

    else:
        return f"""You are an expert subtitle translator for YouTube, TikTok, and casual videos.

Your job is to translate with EXACT same tone, energy, slang, and speaking style as the speaker.

RULES:
- If it's casual, keep it casual
- If it's funny, keep it funny
- If they say "bro", "dude", "like", "you know" → keep the same vibe
- Never make it formal or literary
- Keep filler words like "um", "like", "you know" if they add to the natural feel
- Only output only: number + translation

Now translate these lines with perfect tone match:"""
    


def translate_with_deepseek(texts: List[str], target_lang: str, api_key: str, source_lang: str = 'en') -> List[str]:
    if not texts:
        return []
    
    lang_name = LANGUAGE_CONFIG.get(target_lang, {}).get('name', target_lang)
    source_lang_name = LANGUAGE_CONFIG.get(source_lang, {}).get('name', source_lang)
    
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    batch_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
    
    # استفاده از پرامپت جدید و قوی
    system_prompt = get_translation_prompt(target_lang, source_lang_name, lang_name)
    
    user_message = f"Translate these to {lang_name} with EXACT same tone and style:\n\n{batch_text}"
    
    import time
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"    Retry attempt {attempt+1}/{max_retries}...")
                time.sleep(2)  # Wait a bit before retry

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,      # کمی بالاتر برای طبیعی‌تر شدن (0.3 بهتر از 0.2)
                max_tokens=4000
            )
            
            output = response.choices[0].message.content.strip()
            
            translations = []
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # استخراج بعد از شماره
                if re.match(r'^\d+[\.\)]\s', line):
                    trans = re.sub(r'^\d+[\.\)]\s*', '', line)
                else:
                    trans = line
                # فقط برای فارسی این کار رو بکن
                if target_lang == 'fa':
                    trans = fix_persian_text(trans)
                translations.append(trans)
            
            # اگه تعداد کم بود، تلاش مجدد کن
            if len(translations) < len(texts):
                print(f"    Warning: Received {len(translations)}/{len(texts)} translations. Retrying...")
                # If this was the last attempt, use what we have and fill with original
                if attempt == max_retries - 1:
                    print("    Failed to get full translation. Using partial result + fallback.")
                    translations.extend(texts[len(translations):])
                    return translations[:len(texts)]
                continue
            
            return translations[:len(texts)]
            
        except Exception as e:
            print(f"    Translation error (attempt {attempt+1}): {e}")
            if attempt == max_retries - 1:
                print("    Failed after retries. Using original text.")
                return texts
    
    # Fallback if loop finishes unexpectedly
    return texts

def correct_transcription_with_deepseek(texts: List[str], api_key: str, language: str = 'en') -> List[str]:
    """Correct speech-to-text errors using DeepSeek API"""
    if not texts:
        return []
    
    lang_name = LANGUAGE_CONFIG.get(language, {}).get('name', language)
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    # Create numbered batch
    batch_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
    
    system_prompt = f"""You are a professional {lang_name} transcript editor. 
Your task is to correct speech-to-text errors in transcripts.
Rules:
- Fix misheard words (e.g., "thank" → "think", "their" → "there")
- Fix grammar and punctuation errors
- Keep the original meaning and style
- Do NOT translate or paraphrase
- Do NOT add or remove content
- Only correct errors
- Return each line with its number"""
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Correct any speech-to-text errors in these {lang_name} transcript lines:\n\n{batch_text}"}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        output = response.choices[0].message.content.strip()
        corrected = []
        
        # Parse numbered responses
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            if '. ' in line and line.split('.')[0].isdigit():
                text = line.split('. ', 1)[1]
                corrected.append(text)
            else:
                corrected.append(line)
        
        if len(corrected) != len(texts):
            print(f"Warning: Expected {len(texts)} corrections, got {len(corrected)}. Using original texts for missing.")
            corrected.extend(texts[len(corrected):])
        
        return corrected[:len(texts)]
    
    except Exception as e:
        print(f"Correction error: {e}. Using original texts.")
        return texts


def transcribe_with_deepseek(video_path: str, api_key: str, language: str = 'en') -> str:
    """Transcribe video using DeepSeek API"""
    print(f"Transcribing video with DeepSeek API...")
    
    # Extract audio from video
    base_name = os.path.splitext(video_path)[0]
    audio_path = f"{base_name}_temp_audio.mp3"
    
    print("  Extracting audio from video...")
    result = subprocess.run([
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'libmp3lame', '-q:a', '2',
        audio_path
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")
    
    try:
        # Get audio duration for progress tracking
        probe_result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ], capture_output=True, text=True)
        
        duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0
        
        print(f"  Uploading audio to DeepSeek API...")
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        # Read audio file
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        # Call DeepSeek transcription API (assuming it supports audio transcription)
        # Note: This is a placeholder - adjust based on actual DeepSeek API capabilities
        print(f"  Transcribing audio (0%)...", end='', flush=True)
        
        response = client.audio.transcriptions.create(
            model="whisper-1",  # Adjust model name based on DeepSeek's offering
            file=audio_data,
            language=language,
            response_format="verbose_json"
        )
        
        print(f"\r  Transcribing audio (100%) ✓")
        
        # Convert response to SRT format
        srt_path = f"{base_name}_{language}.srt" if language != 'en' else f"{base_name}.srt"
        
        with open(srt_path, 'w', encoding='utf-8') as f:
            if hasattr(response, 'segments'):
                for i, seg in enumerate(response.segments, 1):
                    start = format_time(seg.start)
                    end = format_time(seg.end)
                    text = seg.text.strip()
                    if text:
                        f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            else:
                # Fallback if segments not available
                f.write(f"1\n00:00:00,000 --> 00:00:10,000\n{response.text}\n\n")
        
        print(f"  Saved transcription: {srt_path}")
        return srt_path
        
    finally:
        # Cleanup temporary audio file
        try:
            os.remove(audio_path)
        except:
            pass


def clean_subtitle_line(text: str) -> str:
    """Remove trailing punctuation from subtitle line"""
    text = text.strip()
    if not text:
        return text
    
    # Remove trailing punctuation
    while text and text[-1] in ".،,؟!?…":
        text = text[:-1].strip()
    
    # Normalize internal newlines to spaces to prevent vertical jumping
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text

def split_text_at_comma(text: str, max_chars: int = 60) -> List[str]:
    """
    Splits text at comma, period, or space if it exceeds max_chars.
    Returns list of strings.
    """
    if len(text) <= max_chars:
        return [text]

    parts = []
    
    # Regex to find split points: comma, period, or end of sentence punctuation
    # We want to split AFTER the punctuation.
    # Also consider splitting at spaces if no punctuation found near middle?
    
    # Simple strategy: 
    # 1. Break by comma/period if present and chunk > max_chars
    # 2. Else break by space
    
    current_part = ""
    words = text.split(' ')
    
    for word in words:
        if len(current_part) + len(word) + 1 > max_chars:
            # If current part is full, push it
            if current_part:
                parts.append(current_part.strip())
            current_part = word
        else:
            if current_part:
                current_part += " " + word
            else:
                current_part = word
            
            # Check if word ends with punctuation, maybe force split?
            if word.endswith(',') or word.endswith('.') or word.endswith('،'):
                parts.append(current_part.strip())
                current_part = ""
                
    if current_part:
        parts.append(current_part.strip())
        
    return parts

def get_ass_style(name: str, font_name: str, font_size: int, primary_color: str = "&H00FFFFFF", margin_v: int = 10) -> str:
    """
    Generate ASS Style line with Opaque Box (BorderStyle=3)
    """
    # Style Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # BorderStyle=3 (Opaque Box)
    # OutlineColour=&H80000000 (Box Color: 50% Black)
    # BackColour=&H80000000 (Shadow/Background: 50% Black)
    return f"Style: {name},{font_name},{font_size},{primary_color},&H000000FF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,3,0,1,2,10,10,{margin_v},1"


def create_ass_with_font(srt_path: str, ass_path: str, lang_code: str = 'en') -> None:
    """Convert SRT to ASS with language-specific font"""
    lang_config = LANGUAGE_CONFIG.get(lang_code, LANGUAGE_CONFIG['en'])
    font_name = lang_config['font']
    font_size = lang_config['font_size']
    
    # Create temporary ASS with subtitles filter to force font size
    result = subprocess.run([
        'ffmpeg', '-y', '-i', srt_path,
        '-f', 'ass',
        ass_path
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")
    
    # Read ASS file
    with open(ass_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Generate unified style string
    # For single file, we use 'Default' as name and default margin 10
    style_line = get_ass_style("Default", font_name, font_size, margin_v=10)
    
    # Replace the main Style line
    # We match the whole line: Style: Default,...
    content = re.sub(
        r'^Style:\s*Default,.*$',
        style_line,
        content,
        flags=re.MULTILINE
    )
    
    # Also replace any inline font size overrides
    content = re.sub(
        r'\\fs\d+',
        f'\\\\fs{font_size}',
        content
    )

    # Ensure Script Info has necessary scaling settings
    if 'ScaledBorderAndShadow: yes' not in content:
        content = content.replace('[Script Info]', 
                                '[Script Info]\nScaledBorderAndShadow: yes')
    
    # Make sure PlayResY is set for proper scaling
    if 'PlayResX' not in content:
        content = content.replace('[Script Info]', 
                                '[Script Info]\nPlayResX: 1920\nPlayResY: 1080')
    
    # FOR PERSIAN: Apply Visual Reshaping (Arabic Reshaper + Python Bidi)
    if lang_code == 'fa':
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            
            def reshape_text(match):
                prefix = match.group(1)
                text = match.group(2)
                
                # Cleanup: Strip all BiDi control characters that might be in the source
                text = text.replace('\u200f', '').replace('\u200e', '') \
                           .replace('\u202a', '').replace('\u202b', '') \
                           .replace('\u202c', '').replace('\u202d', '') \
                           .replace('\u202e', '')

                # Check if it has Persian/Arabic chars
                if any('\u0600' <= c <= '\u06FF' for c in text):
                    reshaped_text = arabic_reshaper.reshape(text)
                    # Force base_dir='R' so the algorithm treats the whole line as RTL context.
                    bidi_text = get_display(reshaped_text, base_dir='R')
                    return f"{prefix}{bidi_text}"
                return f"{prefix}{text}"

            content = re.sub(r'(Dialogue: [^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,)(.*)', 
                             reshape_text, content)
            print("  ✓ Applied visual BiDi reshaping for Persian text")
        except ImportError:
            print("  ⚠️ Warning: arabic-reshaper or python-bidi not installed. Skipping visual fix.")

    # Save modified content
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(content)


def create_combined_ass(subtitle_files: List[Tuple[str, str]], output_ass: str, video_path: str = None) -> None:
    """
    Create ASS file with one or multiple subtitle tracks.
    Always creates a new ASS structure to ensure consistent styling and positioning.
    """
    if not subtitle_files:
        raise ValueError("No subtitle files provided")
    
    print(f"Creating combined ASS with {len(subtitle_files)} languages")
    
    # First, ensure individual ASS files exist
    ass_files = []
    for srt_path, lang_code in subtitle_files:
        ass_path = srt_path.replace('.srt', '.ass')
        # Always regenerate individual ASS to ensure latest settings/fixes
        create_ass_with_font(srt_path, ass_path, lang_code)
        ass_files.append((ass_path, lang_code))
    
    # Write combined ASS
    with open(output_ass, 'w', encoding='utf-8') as f:
        # Header
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("PlayResX: 1920\n")
        f.write("PlayResY: 1080\n")
        f.write("WrapStyle: 0\n")
        f.write("ScaledBorderAndShadow: yes\n\n")
        
        # Styles
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # Fixed Vertical Positions Logic
        current_margin = 30
        
        for i, (_, lang_code) in enumerate(ass_files):
            lang_config = LANGUAGE_CONFIG.get(lang_code, LANGUAGE_CONFIG['en'])
            font_name = lang_config['font']
            base_height = 1080
            
            # Font size logic
            scale_factor = 2 if len(subtitle_files) > 1 else 3.5
            calc_font_size = int((scale_factor / 100) * base_height)
            if lang_code == 'fa':
                calc_font_size = int(calc_font_size * 1.3)
            
            font_size = lang_config['font_size'] if lang_config['font_size'] > 0 else calc_font_size
            
            # Colors
            primary_color = "&H00FFFFFF" if i == 0 else "&H0000FFFF"

            # Define Style with FIXED margin using helper
            style_name = lang_code.upper()
            style_line = get_ass_style(style_name, font_name, font_size, primary_color, current_margin)
            
            f.write(style_line + "\n")
            print(f"  ✓ {style_name}: {font_name} size {font_size} at Fixed Margin {current_margin} (Boxed)")
            
            # Prepare next margin
            # 1.5 factor ensures tight stacking (Font height + minimal gap)
            current_margin += int(font_size * 1.5)

        # Events Processing
        f.write("\n[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for ass_path, lang_code in ass_files:
            with open(ass_path, 'r', encoding='utf-8') as af:
                content = af.read()
            
            # Extract dialogues
            for line in re.findall(r"Dialogue: .*", content, re.MULTILINE):
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    # Enforce the specific style for this language
                    parts[3] = lang_code.upper()
                    f.write(",".join(parts) + "\n")
    
    print(f"  Combined ASS created: {output_ass}")


def render_video_with_subtitles(video_path: str, ass_path: str, output_path: str) -> None:
    """Render video with embedded subtitles"""
    print(f"Rendering video with subtitles → {os.path.basename(output_path)}")
    
    # First, get video resolution and duration
    probe_result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'default=noprint_wrappers=1',
        video_path
    ], capture_output=True, text=True)
    
    width, height, duration = 1920, 1080, 0
    if probe_result.returncode == 0:
        try:
            for line in probe_result.stdout.strip().split('\n'):
                if 'width=' in line:
                    width = line.split('=')[1]
                elif 'height=' in line:
                    height = line.split('=')[1]
                elif 'duration=' in line:
                    duration = float(line.split('=')[1])
            print(f"  Video: {width}x{height}, Duration: {duration:.1f}s")
        except:
            pass
    
    # Fix ASS file to match video resolution
    with open(ass_path, 'r', encoding='utf-8') as f:
        ass_content = f.read()
    
    ass_content = re.sub(r'PlayResX: \d+', f'PlayResX: {width}', ass_content)
    ass_content = re.sub(r'PlayResY: \d+', f'PlayResY: {height}', ass_content)
    
    # Use a safe temporary filename to avoid FFmpeg filter escaping issues
    import time
    fixed_ass = f"temp_subs_{int(time.time())}.ass"
    with open(fixed_ass, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    print(f"  Encoding: 0%", end='', flush=True)
    
    try:
        # Start FFmpeg
        process = subprocess.Popen([
            'ffmpeg', '-y', '-i', video_path,
            '-vf', f"ass=filename='{fixed_ass}'",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-progress', 'pipe:2',
            '-nostats',
            output_path
        ], stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, bufsize=1)
        
        # Track progress and capture error logs
        last_percent = 0
        error_logs = []
        for line in process.stderr:
            error_logs.append(line)
            if len(error_logs) > 20:
                error_logs.pop(0)
                
            if 'out_time_ms=' in line:
                try:
                    time_ms = int(line.split('=')[1].strip())
                    time_sec = time_ms / 1000000.0
                    
                    if duration > 0:
                        percent = min(int((time_sec / duration) * 100), 100)
                        if percent > last_percent:
                            print(f"\r  Encoding: {percent}%", end='', flush=True)
                            last_percent = percent
                except:
                    pass
        
        process.wait()
        
        if process.returncode != 0:
            print(f"\r  Encoding: Failed (Error code {process.returncode})")
            print("FFmpeg Error Output:")
            print("".join(error_logs))
            raise RuntimeError(f"FFmpeg rendering failed. See output above.")
            
        print(f"\r  Encoding: 100% ✓")
            
    finally:
        # Cleanup temporary fixed ASS file
        try:
            if os.path.exists(fixed_ass):
                os.remove(fixed_ass)
        except:
            pass


def find_existing_subtitle(base_path: str, lang_code: str) -> Optional[str]:
    """Find existing subtitle file for a language"""
    lang_name = LANGUAGE_CONFIG.get(lang_code, {}).get('name', '').lower()
    
    possible_names = [
        f"{base_path}_{lang_code}.srt",
        f"{base_path}_{lang_name}.srt",
    ]
    
    # Special cases for common naming patterns
    if lang_code == 'en':
        possible_names.insert(0, f"{base_path}.srt")  # Plain .srt usually means English
        possible_names.append(f"{base_path}_english.srt")
    elif lang_code == 'fa':
        possible_names.extend([
            f"{base_path}_farsi.srt",
            f"{base_path}_persian.srt",
            f"{base_path}_fa.srt"
        ])
    elif lang_code == 'ar':
        possible_names.append(f"{base_path}_arabic.srt")
    elif lang_code == 'es':
        possible_names.append(f"{base_path}_spanish.srt")
    elif lang_code == 'fr':
        possible_names.append(f"{base_path}_french.srt")
    elif lang_code == 'de':
        possible_names.append(f"{base_path}_german.srt")
    elif lang_code == 'ja':
        possible_names.append(f"{base_path}_japanese.srt")
    elif lang_code == 'zh':
        possible_names.extend([
            f"{base_path}_chinese.srt",
            f"{base_path}_cn.srt"
        ])
    
    return next((f for f in possible_names if os.path.exists(f)), None)


def extract_subtitles_from_srt(srt_path: str) -> List[Dict]:
    """Extract subtitle entries from SRT file"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    return [
        {
            'index': int(m[0]),
            'start': m[1],
            'end': m[2],
            'text': m[3].strip()
        }
        for m in matches
    ]


def write_srt_file(srt_path: str, entries: List[Dict]) -> None:
    """
    Write subtitle entries to SRT file with smart splitting.
    If a line is too long, it splits it into sequential time slots.
    """
    new_entries = []
    
    for entry in entries:
        text = clean_subtitle_line(entry['text'])
        
        # Check strict length limit
        parts = split_text_at_comma(text, max_chars=60)
        
        if len(parts) == 1:
            new_entries.append({
                'start': entry['start'],
                'end': entry['end'],
                'text': parts[0]
            })
        else:
            # We need to split the TIME duration too
            start_seconds = parse_srt_time(entry['start'])
            end_seconds = parse_srt_time(entry['end'])
            total_duration = end_seconds - start_seconds
            
            total_chars = sum(len(p) for p in parts)
            current_start = start_seconds
            
            for part in parts:
                part_duration = total_duration * (len(part) / total_chars)
                # Ensure minimum duration of 1s unless very short
                part_duration = max(part_duration, 1.0) if total_duration > 2.0 else part_duration
                
                # Cap at end time
                current_end = min(current_start + part_duration, end_seconds)
                
                # Only add if valid duration
                if current_end > current_start:
                    new_entries.append({
                        'start': format_time(current_start),
                        'end': format_time(current_end),
                        'text': part
                    })
                    current_start = current_end
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(new_entries, 1):
            f.write(f"{i}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")


def transcribe_video(video_path: str, model_size: str = 'medium', language: str = 'en', correct_with_api: bool = False, api_key: str = None) -> str:
    """Transcribe video using Whisper and return SRT path"""
    print(f"Transcribing video with Whisper ({model_size})...")
    
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    # Get total duration for progress tracking
    probe_result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ], capture_output=True, text=True)
    
    total_duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0
    
    print(f"  Processing audio (0%)...", end='', flush=True)
    
    segments_list = []
    last_percent = 0
    
    segments, info = model.transcribe(
        video_path,
        language=language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=5,  # Better quality
        word_timestamps=True # Better segmentation
    )
    
    for seg in segments:
        segments_list.append(seg)
        
        if total_duration > 0:
            percent = min(int((seg.end / total_duration) * 100), 100)
            if percent > last_percent:
                print(f"\r  Processing audio ({percent}%)...", end='', flush=True)
                last_percent = percent
    
    print(f"\r  Processing audio (100%) ✓")
    
    base_name = os.path.splitext(video_path)[0]
    srt_path = f"{base_name}_{language}.srt" if language != 'en' else f"{base_name}.srt"
    
    # Extract texts for correction
    original_texts = [seg.text.strip() for seg in segments_list if seg.text.strip()]
    corrected_texts = original_texts.copy()
    
    # Correct with DeepSeek if requested
    if correct_with_api and api_key:
        print(f"  Correcting transcription with DeepSeek API...")
        batch_size = 20
        all_corrected = []
        
        for i in range(0, len(original_texts), batch_size):
            batch = original_texts[i:i+batch_size]
            start_line = i + 1
            end_line = min(i + batch_size, len(original_texts))
            percent = int((end_line / len(original_texts)) * 100)
            
            print(f"    Correcting lines {start_line}–{end_line} of {len(original_texts)} ({percent}%)")
            
            corrected = correct_transcription_with_deepseek(batch, api_key, language)
            all_corrected.extend(corrected)
        
        corrected_texts = all_corrected
        
        # Show and save corrections
        corrections = []
        changes_count = 0
        for i, (orig, corr) in enumerate(zip(original_texts, corrected_texts), 1):
            if orig != corr:
                changes_count += 1
                change_info = f"Line {i}:\n  Before: {orig}\n  After:  {corr}\n"
                corrections.append(change_info)
                print(f"  ✓ {change_info.strip()}")
        
        if changes_count > 0:
            # Save corrections to file
            corrections_file = f"{base_name}_corrections.txt"
            with open(corrections_file, 'w', encoding='utf-8') as f:
                f.write(f"Transcription Corrections for: {os.path.basename(video_path)}\n")
                f.write(f"Language: {language.upper()}\n")
                f.write(f"Total changes: {changes_count}\n")
                f.write("=" * 60 + "\n\n")
                f.write("\n".join(corrections))
            
            print(f"  📝 Total corrections: {changes_count}")
            print(f"  💾 Corrections saved to: {corrections_file}")
        else:
            print(f"  ℹ️  No corrections needed - transcription looks good!")
    
    print(f"  Saving transcription: {srt_path}")
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, (seg, text) in enumerate(zip(segments_list, corrected_texts), 1):
            if text:
                f.write(f"{i}\n{format_time(seg.start)} --> {format_time(seg.end)}\n{text}\n\n")
    
    return srt_path


def process_video_subtitles(
    video_path: str,
    source_lang: str,
    target_langs: List[str],
    model_size: str = 'medium',
    render: bool = False,
    force_transcribe: bool = False,
    use_deepseek_transcribe: bool = False,
    correct_transcription: bool = True,
    custom_subtitle: str = None
) -> Dict[str, str]:
    """
    Main processing function
    Returns dict of {lang_code: srt_path}
    """
    # 0. Handle Custom Subtitle (Bypass generation)
    if custom_subtitle:
        if not os.path.exists(custom_subtitle):
            raise FileNotFoundError(f"Custom subtitle file not found: {custom_subtitle}")
        
        print(f"  Using custom subtitle file: {custom_subtitle}")
        
        # Determine output path
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_video = f"{video_name}_subtitled.mp4"
        
        # If it's an ASS file, use it directly
        ext = os.path.splitext(custom_subtitle)[1].lower()
        if ext == '.ass':
            render_video_with_subtitles(video_path, custom_subtitle, output_video)
            return {"custom": custom_subtitle}
        
        # If it's SRT, convert to ASS first to apply our formatting
        final_ass = f"temp_custom_{int(time.time())}.ass"
        try:
            create_ass_with_font(custom_subtitle, final_ass, lang_code=source_lang)
            render_video_with_subtitles(video_path, final_ass, output_video)
        finally:
            if os.path.exists(final_ass):
                os.remove(final_ass)
        
        return {"custom": custom_subtitle}
    print(f"Processing video: {video_path}")
    print(f"Source language: {source_lang}")
    print(f"Target languages: {', '.join(target_langs)}\n")
    
    base_path = os.path.splitext(video_path)[0]
    api_key = load_api_key()
    
    result_files = {}
    
    # Step 1: Get source language subtitle
    source_srt = find_existing_subtitle(base_path, source_lang)
    
    if source_srt and not force_transcribe:
        print(f"Found existing {source_lang.upper()} subtitle: {source_srt}")
    else:
        if force_transcribe:
            print(f"Force transcribing (--force-transcribe enabled)...")
        else:
            print(f"No existing {source_lang.upper()} subtitle found.")
        
        # Use DeepSeek or Whisper based on flag
        if use_deepseek_transcribe:
            source_srt = transcribe_with_deepseek(video_path, api_key, source_lang)
        else:
            source_srt = transcribe_video(video_path, model_size, source_lang, correct_transcription, api_key)
    
    # Only add source to result if it's in target_langs
    if source_lang in target_langs:
        result_files[source_lang] = source_srt
    
    # Step 2: Extract source text
    source_entries = extract_subtitles_from_srt(source_srt)
    source_texts = [e['text'] for e in source_entries]
    total_lines = len(source_texts)
    
    # Step 3: Translate to each target language
    for target_lang in target_langs:
        if target_lang == source_lang:
            continue
        
        target_srt = f"{base_path}_{target_lang}.srt"
        
        # Check if translation already exists
        existing = find_existing_subtitle(base_path, target_lang)
        if existing:
            print(f"Found existing {target_lang.upper()} subtitle: {existing}")
            
            # Check for untranslated lines (Smart Resume)
            print(f"  Checking for untranslated lines in {existing}...")
            existing_entries = extract_subtitles_from_srt(existing)
            
            # Create a map of existing translations
            # We assume index matches
            untranslated_indices = []
            
            # Ensure we don't go out of bounds
            check_len = min(len(source_texts), len(existing_entries))
            
            for idx in range(check_len):
                src_text = clean_subtitle_line(source_texts[idx])
                # Remove RLM marks and whitespace for comparison
                tgt_text = existing_entries[idx]['text'].replace('\u200f', '').strip()
                
                # If target looks exactly like source (and source isn't numbers/symbols only)
                # We check length > 1 to avoid false positives on simple punctuations/numbers
                if src_text == tgt_text and len(src_text) > 1 and not src_text.isdigit():
                    untranslated_indices.append(idx)
            
            if not untranslated_indices:
                print("  ✓ File appears fully translated.")
                result_files[target_lang] = existing
                continue
            
            print(f"  ⚠️ Found {len(untranslated_indices)} untranslated lines. Resuming translation...")
            
            all_translations_map = {} # index -> new_translation
            
            batch_size = 10  # Reduced for stability
            for i in range(0, len(untranslated_indices), batch_size):
                batch_indices = untranslated_indices[i:i+batch_size]
                batch_texts = [source_texts[idx] for idx in batch_indices]
                
                print(f"    Re-translating {len(batch_texts)} lines (Indices {batch_indices[0]+1}-{batch_indices[-1]+1})...")
                
                new_translations = translate_with_deepseek(batch_texts, target_lang, api_key, source_lang)
                
                for idx, trans in zip(batch_indices, new_translations):
                    existing_entries[idx]['text'] = trans
            
            # Save updated file
            write_srt_file(existing, existing_entries)
            print(f"  ✓ Updated {existing} with {len(untranslated_indices)} new translations.")
            result_files[target_lang] = existing
            continue
        
        # Translate
        print(f"Translating to {target_lang.upper()}...")
        
        translations = []
        batch_size = 10  # Reduced from 20 to avoid timeouts/incomplete answers
        
        for i in range(0, total_lines, batch_size):
            batch_texts = source_texts[i:i+batch_size]
            start_line = i + 1
            end_line = min(i + batch_size, total_lines)
            
            print(f"  Translating lines {start_line}–{end_line} of {total_lines} ({int((i/total_lines)*100)}%)")
            
            batch_translations = translate_with_deepseek(batch_texts, target_lang, api_key, source_lang)
            translations.extend(batch_translations)
            
            time.sleep(1)  # Increased delay slightly
        
        # Write translated SRT
        translated_entries = [
            {**entry, 'text': trans}
            for entry, trans in zip(source_entries, translations)
        ]
        write_srt_file(target_srt, translated_entries)
        print(f"Created: {target_srt}")
        result_files[target_lang] = target_srt
    
    # Step 3.5: Enforce splitting/formatting on ALL result files (new or existing)
    print("\nEnforcing subtitle formatting (splitting long lines)...")
    for lang_code, srt_path in result_files.items():
        # Read, existing logic in write_srt_file handles the splitting
        entries = extract_subtitles_from_srt(srt_path)
        write_srt_file(srt_path, entries)

    # Step 4: Create ASS files
    print("\nCreating ASS subtitle files...")
    for lang_code, srt_path in result_files.items():
        ass_path = srt_path.replace('.srt', '.ass')
        # Always regenerate ASS to ensure latest font/style settings are applied
        create_ass_with_font(srt_path, ass_path, lang_code)
        print(f"  Created/Updated: {ass_path}")

    # Step 5: Render video if requested
    if render:
        # Determine output filename
        if len(result_files) == 1:
            lang_suffix = list(result_files.keys())[0]
        else:
            lang_suffix = "_".join(sorted(result_files.keys()))
        
        output_video = f"{base_path}_{lang_suffix}_subtitled.mp4"
        
        if os.path.exists(output_video):
            print(f"\nSubtitled video already exists: {output_video}")
        else:
            print(f"\nRendering video with subtitles...")
            
            # Create combined ASS (works for both single and multiple languages)
            combined_ass = f"{base_path}_combined.ass"
            subtitle_files = [(srt, lang) for lang, srt in result_files.items()]
            create_combined_ass(subtitle_files, combined_ass, video_path)
            
            render_video_with_subtitles(video_path, combined_ass, output_video)
            print(f"Created: {output_video}")
    
    # Summary
    print("\n" + "="*50)
    print("Processing complete!")
    print("="*50)
    for lang, path in result_files.items():
        print(f"  {lang.upper()}: {path}")
    if render:
        print(f"  Video: {output_video}")
    
    return result_files


# ====================== MAIN ======================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-language video subtitle generator with DeepSeek API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transcribe English and translate to Persian
  python script.py video.mp4 -s en -t fa
  
  # Translate to multiple languages
  python script.py video.mp4 -s en -t fa ar es
  
  # Render video with subtitles
  python script.py video.mp4 -s en -t fa -r
  
  # Use smaller/faster Whisper model
  python script.py video.mp4 -s en -t fa -m base
  
  # Disable automatic transcription correction
  python script.py video.mp4 -s en -t fa --no-correction
  
  # List supported languages
  python script.py --list-languages
        """
    )
    
    parser.add_argument("video", nargs='?', help="Video file path")
    parser.add_argument(
        "-s", "--source",
        default="en",
        help=f"Source language code (default: en). Available: {', '.join(LANGUAGE_CONFIG.keys())}"
    )
    parser.add_argument(
        "-t", "--target",
        nargs='+',
        default=['fa'],
        help=f"Target language code(s). Default: fa. Available: {', '.join(LANGUAGE_CONFIG.keys())}"
    )
    parser.add_argument(
        "-m", "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: medium)"
    )
    parser.add_argument(
        "-r", "--render",
        action="store_true",
        help="Render video with embedded subtitles"
    )
    parser.add_argument(
        "-f", "--force-transcribe",
        action="store_true",
        help="Force re-transcription even if subtitle exists"
    )
    parser.add_argument(
        "--deepseek-transcribe",
        action="store_true",
        help="Use DeepSeek API for transcription instead of Whisper"
    )
    parser.add_argument(
        "--no-correction",
        action="store_true",
        help="Disable automatic transcription correction with DeepSeek"
    )
    parser.add_argument(
        "--subtitle", "-sub",
        type=str,
        help="Path to an existing subtitle file (SRT/ASS) to burn into the video"
    )
    parser.add_argument(
        "-l", "--list-languages",
        action="store_true",
        help="List all supported languages"
    )
    
    args = parser.parse_args()
    
    # List languages
    if args.list_languages:
        print("Supported languages:")
        print("-" * 40)
        for code, info in sorted(LANGUAGE_CONFIG.items()):
            print(f"  {code:4s} - {info['name']}")
        exit(0)
    
    # Validate arguments
    if not args.video:
        parser.error("Video file path required (or use --list-languages)")
    
    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        exit(1)
    
    if not args.target:
        parser.error("At least one target language required (-t)")
    
    # Validate language codes
    invalid_langs = [lang for lang in [args.source] + args.target if lang not in LANGUAGE_CONFIG]
    if invalid_langs:
        print(f"Error: Invalid language code(s): {', '.join(invalid_langs)}")
        print(f"Use --list-languages to see available options")
        exit(1)
    
    # Process video
    try:
        process_video_subtitles(
            args.video,
            args.source,
            args.target,
            model_size=args.model,
            render=args.render,
            force_transcribe=args.force_transcribe,
            use_deepseek_transcribe=args.deepseek_transcribe,
            correct_transcription=not args.no_correction,
            custom_subtitle=args.subtitle
        )
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        exit(1)