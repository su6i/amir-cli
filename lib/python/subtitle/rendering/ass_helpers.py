import re
from typing import Callable, Dict, List, Optional, Tuple

# Import vis_len for proper Unicode character counting
try:
    from subtitle.segmentation import vis_len
except ImportError:
    import unicodedata
    def vis_len(s: str) -> int:
        """Fallback: visual character length excluding zero-width Unicode format chars."""
        return sum(1 for c in s if unicodedata.category(c) != "Cf")


def compute_ass_layout(
    style,
    lang: str,
    secondary_srt: Optional[str],
    video_width: int,
    video_height: int,
    en_font_scale: float,
    fa_font_scale: float,
    fa_font_name: str,
    top_raise_px: int = 0,
    bottom_raise_px: int = 0,
) -> Dict[str, object]:
    """Compute stable ASS layout and font settings for mono/bilingual output.
    
    For vertical/portrait videos (9:16 aspect ratio):
    - Reduce horizontal margins to prevent text from going out of frame
    - Adjust vertical margins for proper subtitle positioning in narrow viewport
    """
    is_portrait = bool(video_width and video_height and video_height > video_width)
    # FIX: Horizontal margins should be smaller for portrait to fit text in narrow width
    margin_h = 32 if is_portrait else 64
    # Base vertical margins. Per-run offsets allow shifting each subtitle lane.
    # Portrait videos need extra bottom safe-area so Persian glyph descenders
    # and outline/shadow never clip outside the visible frame.
    if is_portrait:
        base_bottom_margin_v = max(34, int(style.font_size * 1.35))
        base_top_margin_v = max(34, int(style.font_size * 1.2))
    else:
        base_bottom_margin_v = 10
        base_top_margin_v = 24
    fa_margin_v = max(0, base_bottom_margin_v + int(bottom_raise_px or 0))
    top_margin_v = max(0, base_top_margin_v + int(top_raise_px or 0))

    fa_style = None
    if lang == "fa" or secondary_srt:
        base_size = style.font_size / en_font_scale if en_font_scale > 0 else style.font_size
        fa_font_size = int(base_size * fa_font_scale)
        fa_style = (
            f"Style: FaDefault,{fa_font_name},{fa_font_size},&H00FFFFFF,&H000000FF,&H00000000,{style.back_color},"
            f"-1,0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},"
            f"{style.alignment},{margin_h},{margin_h},{fa_margin_v},1"
        )

    return {
        "is_portrait": is_portrait,
        "margin_h": margin_h,
        "fa_margin_v": fa_margin_v,
        "top_margin_v": top_margin_v,
        "fa_style": fa_style,
    }


def build_ass_styles(style, secondary_srt: Optional[str], fa_style: Optional[str], margin_h: int, fa_margin_v: int, top_margin_v: int) -> str:
    """Create ASS styles block with primary and optional bilingual styles."""
    format_line = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
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

    styles_block = f"{format_line}\n{primary_style_full}"
    if secondary_srt:
        styles_block += f"\n{top_style}"
    if fa_style:
        styles_block += f"\n{fa_style}"
    return styles_block


def build_ass_header(styles_block: str, secondary_srt: Optional[str], video_width: int = 0, video_height: int = 0) -> str:
    """Compose full ASS header text."""
    wrap_style = "2" if secondary_srt else "0"
    res_info = f"PlayResX: {video_width}\nPlayResY: {video_height}\n" if video_width and video_height else ""
    return f"""[Script Info]
ScriptType: v4.00+
{res_info}WrapStyle: {wrap_style}

[V4+ Styles]
{styles_block}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_secondary_map(sec_entries: List[Dict]) -> Dict[str, str]:
    """Build index-based secondary subtitle map for deterministic pairing."""
    secondary_map: Dict[str, str] = {}
    for entry in sec_entries:
        secondary_map[entry["index"]] = entry["text"]
    return secondary_map


def _wrap_parentheses_with_smaller_font(text: str) -> str:
    pattern = r"[\u200F]?\(([a-zA-Z0-9\s/_\-\.]+)\)[\u200F]?"
    replacement = r"{\fscx75\fscy75}(\1){\fscx100\fscy100}"
    return re.sub(pattern, replacement, text)


def _normalize_primary_text(text: str, secondary_srt: Optional[str], is_portrait: bool) -> str:
    """Normalize primary (top) subtitle text for display.
    
    For bilingual subtitles in vertical videos:
    - Avoid aggressive truncation that breaks sync between audio and visual text
    - Use vis_len for proper Unicode character counting
    - Preserve full text for audio/video sync, only truncate as last resort
    
    Design: For short-form vertical videos (Instagram Reels, TikTok, YouTube Shorts),
    the primary (top) line should allow up to 50 characters to prevent overflow.
    Aggressive truncation breaks audio/text synchronization.
    """
    out = text.replace("\n", " ").replace("\\N", " ").replace("\\n", " ").strip()
    out = " ".join(out.split())
    
    if secondary_srt:
        # CRITICAL FIX: Portrait character limits must strictly match the narrow width
        # to ensure it breaks properly, especially for YouTube auto-sub imports.
        # Max 36 chars ensures it rarely spans more than 2 safe lines.
        max_top_chars = 36 if is_portrait else 80
        
        # Use vis_len for proper visual character counting (handles Unicode zero-width chars)
        visual_len = vis_len(out)
        if visual_len > max_top_chars:
            # For sync integrity, reduce character limit gracefully only if necessary
            # This preserves most of the text while preventing frame overflow
            cut_pos = max(15, max_top_chars - 5)
            out = out[:cut_pos].rsplit(" ", 1)[0] + "…"
    return out


def _srt_to_ass_time(t_str: str, time_offset: float) -> str:
    h, m, s_ms = t_str.replace(",", ".").split(":")
    s, ms = s_ms.split(".")
    total_ms = int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
    total_ms = max(0, total_ms - int(time_offset * 1000))
    out_h = total_ms // 3600000
    out_m = (total_ms % 3600000) // 60000
    out_s = (total_ms % 60000) // 1000
    out_cs = (total_ms % 1000) // 10
    return f"{out_h}:{out_m:02d}:{out_s:02d}.{out_cs:02d}"


def _strip_bidi_controls(text: str) -> str:
    for cp in (
        "\u200f",
        "\u200e",
        "\u200d",
        "\u202b",
        "\u202a",
        "\u202c",
        "\u202e",
        "\u202d",
    ):
        text = text.replace(cp, "")
    return text


def build_ass_events(
    entries: List[Dict],
    secondary_map: Dict[str, str],
    lang: str,
    style,
    is_portrait: bool,
    secondary_srt: Optional[str],
    time_offset: float,
    clean_bidi_fn: Callable[[str], str],
    fix_persian_text_fn: Callable[[str], str],
    max_lines: int = 1,
) -> List[str]:
    """Build ASS dialogue events for mono/bilingual subtitle rendering."""
    events: List[str] = []

    for entry in entries:
        text = _normalize_primary_text(entry["text"], secondary_srt, is_portrait)
        
        # Ensure proper RTL formatting and punctuation for monolingual Persian output
        if lang == "fa":
            text = clean_bidi_fn(text)
            text = fix_persian_text_fn(text)

        # If single-line mode is requested, enforce it at event text level.
        if max_lines <= 1:
            text = text.replace("\\N", " ").replace("\\n", " ").replace("\n", " ")
            text = " ".join(text.split())
        final_text = text
        bi_fa_text = None

        if secondary_map:
            sec_text = secondary_map.get(entry["index"])
            if sec_text:
                sec_text = clean_bidi_fn(sec_text)
                sec_text_fixed = fix_persian_text_fn(sec_text)
                if max_lines <= 1:
                    sec_text_fixed = sec_text_fixed.replace("\\N", " ").replace("\\n", " ").replace("\n", " ")
                    sec_text_fixed = " ".join(sec_text_fixed.split())
                sec_text_formatted = _wrap_parentheses_with_smaller_font(sec_text_fixed)
                top_scale = 0.65 if is_portrait else 0.82
                top_fs = max(11, int(style.font_size * top_scale))
                bot_fs = style.font_size
                top_wrap = "{\\q0}" if is_portrait else ("{\\q2}" if max_lines <= 1 else "")
                fa_wrap = "{\\q0}" if is_portrait else ("{\\q2}" if max_lines <= 1 else "")
                final_text = f"{top_wrap}{{\\fs{top_fs}}}{{\\c&H808080}}{text}"
                bi_fa_text = f"{fa_wrap}{{\\b1}}{{\\fs{bot_fs}}}{sec_text_formatted}"

        ass_start = _srt_to_ass_time(entry["start"], time_offset)
        ass_end = _srt_to_ass_time(entry["end"], time_offset)

        final_text = _strip_bidi_controls(final_text)
        if bi_fa_text:
            bi_fa_text = _strip_bidi_controls(bi_fa_text)

        # Monolingual path also needs no-wrap in single-line mode.
        if not bi_fa_text and max_lines <= 1 and not final_text.startswith("{\\q2}"):
            final_text = "{\\q2}" + final_text

        event_style = "FaDefault" if (lang == "fa" and not secondary_map) else "Default"
        if bi_fa_text:
            events.append(f"Dialogue: 0,{ass_start},{ass_end},FaDefault,,0,0,0,,{bi_fa_text}")
            events.append(f"Dialogue: 0,{ass_start},{ass_end},TopDefault,,0,0,0,,{final_text}")
        else:
            events.append(f"Dialogue: 0,{ass_start},{ass_end},{event_style},,0,0,0,,{final_text}")

    return events
