# subtitle/cli.py
# Command Line Interface for Subtitle Engine

import argparse
import os
import sys
from typing import Optional, Tuple
from .processor import SubtitleProcessor, SubtitleStyle


def _parse_time_str(s: str) -> Optional[float]:
    """Convert a time string to seconds.
    Accepts: 'begin' (→ 0.0), 'end' (→ None), plain number (seconds),
    or HH:MM:SS / H:MM:SS / MM:SS timestamp.
    """
    if s.lower() in ('begin', 'start'):
        return 0.0
    if s.lower() == 'end':
        return None  # signals "to end of video"
    try:
        return float(s)
    except ValueError:
        pass
    parts = s.split(':')
    try:
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + float(sec)
        elif len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + float(sec)
    except (ValueError, TypeError):
        pass
    raise ValueError(f"Cannot parse time value: '{s}'")


def _parse_limit_args(limit_args) -> Tuple[Optional[float], Optional[float]]:
    """Parse --limit arguments into (start_sec, end_sec) tuple.
    - No args  → (None, None)
    - 1 arg    → (0.0, N)  — backward compat: first N seconds
    - 2 args   → (start, end)
    end_sec=None means to the end of the video.
    """
    if not limit_args:
        return None, None
    if len(limit_args) == 1:
        val = _parse_time_str(limit_args[0])
        return (0.0, val)
    if len(limit_args) == 2:
        start = _parse_time_str(limit_args[0])
        end   = _parse_time_str(limit_args[1])
        return (start or 0.0, end)
    raise ValueError(f"--limit accepts 1 or 2 time arguments, got {len(limit_args)}")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-language video subtitle generator (2026 Pro Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Note:
  This tool is for subtitle generation. For video trimming/cutting,
  use the dedicated video module:
    amir video cut <file> [options]
    amir video trim <file> [options]
"""
    )
    parser.add_argument("video", help="Video file path")
    parser.add_argument("-s", "--source", default="en", help="Source language (audio language for Whisper transcription)")
    parser.add_argument("--sub", "-t", nargs='+', dest="sub_langs", default=['fa'], metavar='LANG',
        help="Subtitle languages to display, in top-to-bottom order. "
             "Each language is translated from --source if needed. "
             "Examples: --sub fa | --sub en fa | --sub fr fa en")
    parser.add_argument("-r", "--render", action="store_true", default=True, help="Burn subtitles into video (default: enabled)")
    parser.add_argument("--no-render", action="store_false", dest="render", help="Skip burning — generate subtitle files only")
    
    parser.add_argument("-f", "--force", action="store_true", help="Force re-transcription and skip SRT smart resume (still uses local hash cache + provider KV caches)")
    parser.add_argument("-c", "--correct", action="store_true", help="Correct transcription with AI")
    parser.add_argument("-l", "--limit", nargs='+', metavar='TIME',
        help="Limit transcription to a time range. "
             "1 arg: first N seconds from start (e.g. --limit 120). "
             "2 args: start end (e.g. --limit 120 end, --limit begin 00:50:38, --limit 1800 1:22:00). "
             "Use 'begin'/'end' as aliases for start/end of video.")
    
    # New Pro Arguments
    parser.add_argument("--style", type=str, default="lecture", choices=[e.value for e in SubtitleStyle], help="Subtitle style template")
    parser.add_argument("--max-lines", type=int, default=1, help="Maximum lines per subtitle (1 or 2)")
    parser.add_argument("--speaker", action="store_true", help="Enable Speaker Diarization")

    # BERT options (optional)
    parser.add_argument("--use-bert", action="store_true", help="Enable BERT masked-LM collocation scoring")
    parser.add_argument("--bert-model", type=str, help="BERT model name (e.g., bert-base-uncased)")
    
    # Style Overrides
    parser.add_argument("--alignment", type=int, help="ASS alignment (2=Bottom, 8=Top, 5=Center)")
    parser.add_argument("--font-size", type=int, help="Primary font size (e.g., 25)")
    parser.add_argument("--sec-font-size", type=int, help="Secondary font size (e.g., 18)")
    
    # Visual Overrides (Pro)
    parser.add_argument("--shadow", type=int, help="Shadow depth (default: 0)")
    parser.add_argument("--outline", type=int, help="Outline width (default: 2)")
    parser.add_argument("--back-color", type=str, help="Background color (ASS hex, e.g., &H80000000)")
    parser.add_argument("--primary-color", type=str, help="Primary color (ASS hex, e.g., &H00FFFFFF)")
    
    # AI Tuning (Pro)
    parser.add_argument("--llm", type=str, default="deepseek", choices=["deepseek", "gemini", "litellm", "minimax", "grok"], help="LLM bridge for translation (default: deepseek)")
    parser.add_argument("--model", type=str, help="Specific model name (required for LiteLLM, e.g., gpt-4o)")
    parser.add_argument("--whisper-model", type=str, default="turbo", help="Whisper model size (e.g., large-v3, turbo)")
    parser.add_argument("--initial-prompt", type=str, help="Whisper initial prompt (context)")
    parser.add_argument("--temperature", type=float, default=0.0, help="Model temperature (0.0-1.0)")
    parser.add_argument("--openai-fallback", action="store_true", help="Use OpenAI if DeepSeek fails")
    
    # Logic Overrides (Pro)
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum subtitle duration (seconds)")

    # Social media post generation
    _post_platforms = ['telegram', 'youtube', 'linkedin']
    parser.add_argument("--post", nargs='*', dest="post_platforms", default=None,
                        metavar='PLATFORM',
                        help=("Generate social media post(s). "
                              "No value → telegram only. "
                              f"Choices: {', '.join(_post_platforms)}. "
                              "Example: --post telegram youtube linkedin"))
    parser.add_argument("--post-only", nargs='*', dest="post_only_platforms", default=None,
                        metavar='PLATFORM',
                        help="Generate post(s) from existing SRTs only (skip subtitle processing). "
                             "Same platform choices as --post.")
    parser.add_argument("--prompt-file", dest="prompt_file", default=None, metavar='FILE',
                        help=("Override LLM user prompt from a .txt file for this run. "
                              "Supports variables: {title}, {srt_lang_name}, {full_text}. "
                              "Persistent per-platform override: ~/.amir/prompts/{platform}.txt"))
    parser.add_argument("--post-lang", nargs='+', dest="post_langs", default=None, metavar='LANG',
                        help=("Languages to generate posts for (default: fa only). "
                              "Example: --post-lang fa de en"))

    # Document Export
    parser.add_argument("--save", nargs='+', dest="save_formats", default=None,
                        metavar='FMT',
                        help=("Export subtitle text as clean document(s) without timestamps. "
                              "Formats: txt, md, html, pdf. Multiple allowed: --save txt pdf"))

    args = parser.parse_args()

    # Resolve platform lists
    # --post with no value → ['telegram'], --post telegram youtube → ['telegram', 'youtube']
    _platforms = None
    _post_only = False
    if args.post_only_platforms is not None:
        _post_only = True
        _platforms = args.post_only_platforms or ['telegram']
    elif args.post_platforms is not None:
        _platforms = args.post_platforms or ['telegram']

    if not os.path.exists(args.video) and not _post_only:
        print(f"Error: {args.video} not found")
        sys.exit(1)
        
    # Convert string style to Enum
    style_enum = SubtitleStyle(args.style)
        
    processor = SubtitleProcessor(
        style=style_enum, 
        model_size=args.whisper_model,
        max_lines=args.max_lines,
        alignment=args.alignment,
        font_size=args.font_size,
        sec_font_size=args.sec_font_size,
        shadow=args.shadow,
        outline=args.outline,
        back_color=args.back_color,
        primary_color=args.primary_color,
        initial_prompt=args.initial_prompt,
        temperature=args.temperature,
        use_openai_fallback=args.openai_fallback,
        min_duration=args.min_duration,
        llm=args.llm,
        custom_model=args.model
        ,use_bert=args.use_bert,
        bert_model=args.bert_model
    )
    limit_start, limit_end = _parse_limit_args(args.limit)
    processor.run_workflow(
        args.video,
        args.source,
        args.sub_langs,
        render=args.render,
        force=args.force,
        correct=args.correct,
        limit_start=limit_start,
        limit_end=limit_end,
        detect_speakers=args.speaker,
        platforms=_platforms,
        post_only=_post_only,
        prompt_file=args.prompt_file,
        post_langs=args.post_langs,
        save_formats=args.save_formats,
    )

if __name__ == "__main__":
    main()
