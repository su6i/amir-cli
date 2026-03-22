import json
from pathlib import Path
from typing import Optional

from subtitle.models import ProcessingCheckpoint, ProcessingStage


def get_checkpoint_path(cache_dir: Path, video_path: str) -> Path:
    import hashlib

    video_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
    return cache_dir / f"checkpoint_{video_hash}.json"


def save_checkpoint(cache_dir: Path, checkpoint: ProcessingCheckpoint) -> None:
    checkpoint_file = get_checkpoint_path(cache_dir, checkpoint.video_path)
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "video_path": checkpoint.video_path,
                "stage": checkpoint.stage.value,
                "source_lang": checkpoint.source_lang,
                "target_langs": checkpoint.target_langs,
                "timestamp": checkpoint.timestamp,
                "data": checkpoint.data,
            },
            f,
            indent=2,
        )


def load_checkpoint(cache_dir: Path, video_path: str) -> Optional[ProcessingCheckpoint]:
    checkpoint_file = get_checkpoint_path(cache_dir, video_path)
    if not checkpoint_file.exists():
        return None

    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ProcessingCheckpoint(
            video_path=data["video_path"],
            stage=ProcessingStage(data["stage"]),
            source_lang=data["source_lang"],
            target_langs=data["target_langs"],
            timestamp=data["timestamp"],
            data=data["data"],
        )
    except Exception:
        return None


def clear_checkpoint(cache_dir: Path, video_path: str) -> None:
    checkpoint_file = get_checkpoint_path(cache_dir, video_path)
    if checkpoint_file.exists():
        checkpoint_file.unlink()
