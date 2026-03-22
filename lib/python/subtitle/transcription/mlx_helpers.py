import os
import re
from typing import List, Optional, Tuple


def resolve_mlx_repo_path(model_name: str) -> str:
    """Resolve mlx-whisper HF repo path from configured model name."""
    if "/" in model_name:
        return model_name
    if model_name == "turbo":
        return "mlx-community/whisper-turbo"
    if model_name.startswith("large-v3"):
        return "mlx-community/whisper-large-v3-mlx"
    return f"mlx-community/whisper-{model_name}-mlx"


def build_mlx_worker_script(repo_path: str, language: str, video_path: str, result_json_path: str) -> str:
    """Build isolated Python worker script that runs mlx transcription."""
    return f"""
import os
import sys
import json

def run():
    try:
        import mlx_whisper
        import mlx.core as mx

        try:
            mx.set_cache_limit(1024 * 1024 * 512)
        except:
            pass

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
        if "{language}":
            kwargs["language"] = "{language}"
        result = mlx_whisper.transcribe("{video_path}", **kwargs)

        simplified = []
        for segment in result.get('segments', []):
            if 'words' in segment:
                for w in segment['words']:
                    simplified.append({{'start': w['start'], 'end': w['end'], 'word': w['word']}})

        payload = {{"language": result.get("language", ""), "words": simplified}}
        with open("{result_json_path}", "w", encoding="utf-8") as f:
            json.dump(payload, f)

        try:
            mx.clear_cache()
        except:
            pass
        os._exit(0)

    except Exception as e:
        print(f"WORKER_ERROR: {{e}}")
        os._exit(1)

if __name__ == "__main__":
    run()
"""


def parse_whisper_progress_time(line: str) -> Optional[float]:
    """Parse current timestamp from whisper verbose log line."""
    match = re.search(r"-->\s+\[?(\d+:)?(\d+):(\d+)[\.,](\d+)\]?", line)
    if not match:
        return None

    groups = match.groups()
    h = int(groups[0].strip(":")) if groups[0] else 0
    m = int(groups[1])
    s = int(groups[2])
    ms = int(groups[3])
    ms_val = ms / (10 ** len(groups[3]))
    return h * 3600 + m * 60 + s + ms_val


def parse_verbose_segment_line(raw: str) -> Optional[Tuple[float, float, str]]:
    """Extract (start_s, end_s, text) from whisper verbose segment line."""
    match = re.match(
        r"\[(?:(\d+):)?(\d+):(\d+[\.,]\d+)\s+-->\s+(?:(\d+):)?(\d+):(\d+[\.,]\d+)\]\s*(.*)",
        raw.strip(),
    )
    if not match:
        return None

    def _to_sec(hg, mg, sg):
        return (int(hg) if hg else 0) * 3600 + int(mg) * 60 + float(sg.replace(",", "."))

    return (
        _to_sec(match.group(1), match.group(2), match.group(3)),
        _to_sec(match.group(4), match.group(5), match.group(6)),
        match.group(7),
    )


def to_srt_tc(sec: float) -> str:
    """Convert seconds to SRT timestamp format."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s_i = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s_i:02d},{ms:03d}"


def flush_partial_entries(partial_entries: List[Tuple[float, float, str]], partial_srt_path: str) -> None:
    """Persist partial transcription entries to checkpoint SRT file."""
    if not partial_entries:
        return

    lines = []
    for idx, (start, end, text) in enumerate(partial_entries, 1):
        lines.extend([str(idx), f"{to_srt_tc(start)} --> {to_srt_tc(end)}", text.strip(), ""])

    with open(partial_srt_path, "w", encoding="utf-8") as pf:
        pf.write("\n".join(lines))


def cleanup_paths(paths: List[str]) -> None:
    """Best-effort cleanup of temporary files."""
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
