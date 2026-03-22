from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


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
    secondary_font_size: Optional[int] = None


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
        use_banner=False,
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
        animation="fade",
    ),
}
