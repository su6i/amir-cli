# subtitle/cli.py
# Command Line Interface for Subtitle Engine

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


def _parse_sub_lang_tokens(tokens: List[str]) -> Tuple[List[str], Dict[str, int]]:
    """Parse --sub tokens supporting inline size per language.

    Examples:
      --sub en fa            -> langs=['en','fa'], sizes={}
      --sub en 18 fa 20      -> langs=['en','fa'], sizes={'en':18,'fa':20}
      --sub fa 22            -> langs=['fa'],      sizes={'fa':22}
    """
    langs: List[str] = []
    sizes: Dict[str, int] = {}

    i = 0
    while i < len(tokens):
        tok = str(tokens[i]).strip()
        if not tok:
            i += 1
            continue

        if tok.isdigit():
            raise ValueError(f"Unexpected size token '{tok}' without a preceding language in --sub")

        lang = tok.lower()
        langs.append(lang)

        if i + 1 < len(tokens):
            nxt = str(tokens[i + 1]).strip()
            if nxt.isdigit():
                sz = int(nxt)
                if sz <= 0:
                    raise ValueError(f"Invalid font size '{nxt}' for language '{lang}'")
                sizes[lang] = sz
                i += 2
                continue

        i += 1

    if not langs:
        langs = ['en', 'fa']

    return langs, sizes


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
    parser.add_argument("--sub", "-t", nargs='+', dest="sub_langs", default=['en', 'fa'], metavar='LANG',
        help="Subtitle languages to display, in top-to-bottom order. "
             "Each language is translated from --source if needed. "
             "Default: en fa. "
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
    parser.add_argument("--post", nargs='*', dest="post_platforms", default=['telegram'],
                        metavar='PLATFORM',
                        help=("Generate social media post(s). "
                              "No value → telegram only. "
                              "Default: telegram. "
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
    parser.add_argument("--save", nargs='*', dest="save_formats", default=['pdf'],
                        metavar='FMT',
                        help=("Export subtitle text as clean document(s) without timestamps. "
                              "Formats: txt, md, html, pdf. Multiple allowed: --save txt pdf. "
                              "No value → pdf. "
                              "Default: pdf"))

    # Final render passthrough (applied when subtitle burn is enabled)
    parser.add_argument("--resolution", type=int, default=None,
                        help="Final burn resolution height (e.g., 360, 480, 720)")
    parser.add_argument("--quality", type=int, default=None,
                        help="Final burn quality 0-100 (mapped to CRF for libx264)")
    parser.add_argument("--fps", type=int, default=None,
                        help="Final burn output FPS (e.g., 10)")
    parser.add_argument("--split", type=int, default=None,
                        help="Split final rendered video into ~N MB chunks")

    args = parser.parse_args()

    try:
        parsed_sub_langs, per_lang_sizes = _parse_sub_lang_tokens(args.sub_langs or [])
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(2)

    args.sub_langs = parsed_sub_langs

    # Map inline per-language sizes to existing primary/secondary font knobs.
    # Explicit --font-size / --sec-font-size still have priority.
    if per_lang_sizes:
        primary_lang = args.sub_langs[0] if args.sub_langs else None
        secondary_lang = args.sub_langs[1] if len(args.sub_langs) > 1 else None

        if args.font_size is None and primary_lang in per_lang_sizes:
            args.font_size = per_lang_sizes[primary_lang]
        if args.sec_font_size is None and secondary_lang in per_lang_sizes:
            args.sec_font_size = per_lang_sizes[secondary_lang]

    # --save with no format argument → default to pdf
    if args.save_formats is not None and len(args.save_formats) == 0:
        args.save_formats = ['pdf']

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
    result = processor.run_workflow(
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
        render_resolution=args.resolution,
        render_quality=args.quality,
        render_fps=args.fps,
        render_split_mb=args.split,
    )

    def _collect_output_paths(value, acc):
        if isinstance(value, str) and os.path.exists(value):
            acc.add(os.path.abspath(value))
        elif isinstance(value, dict):
            for v in value.values():
                _collect_output_paths(v, acc)
        elif isinstance(value, list):
            for v in value:
                _collect_output_paths(v, acc)

    output_paths = set()
    if isinstance(result, dict):
        _collect_output_paths(result, output_paths)

    if output_paths:
        print("\nGenerated files:")
        for p in sorted(output_paths):
            print(f" - {Path(p).name}")

if __name__ == "__main__":
    main()
