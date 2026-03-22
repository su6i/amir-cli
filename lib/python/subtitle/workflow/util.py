"""Common utilities for workflow stages"""
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import os


def emit_stage_progress(
    emit_progress: Optional[Callable],
    percentage: int,
    message: str
) -> None:
    """Emit progress update if callback provided"""
    if emit_progress:
        try:
            emit_progress(percentage, message)
        except Exception:
            pass


def ensure_output_directory(base_path: str) -> str:
    """Ensure output directory exists"""
    Path(base_path).mkdir(parents=True, exist_ok=True)
    return base_path


def get_output_file_path(
    base_path: str,
    stem: str,
    lang: str,
    extension: str
) -> str:
    """Generate standardized output file path"""
    filename = f"{stem}.{lang}.{extension}"
    return os.path.join(base_path, filename)


def validate_context_keys(context: Dict[str, Any], required_keys: List[str]) -> bool:
    """Validate context dict has all required keys"""
    return all(key in context for key in required_keys)


def merge_context_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two context dictionaries"""
    result = base.copy()
    result.update(updates)
    return result


def safe_get_from_context(context: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from context dict"""
    return context.get(key, default)


def create_stage_context(**kwargs) -> Dict[str, Any]:
    """Create a new stage context dict"""
    return {**kwargs}


def log_stage_start(logger, stage_name: str, target_lang: Optional[str] = None) -> None:
    """Log stage initialization"""
    if target_lang:
        logger.info(f"▶️ {stage_name} for {target_lang}")
    else:
        logger.info(f"▶️ {stage_name}")


def log_stage_complete(logger, stage_name: str, target_lang: Optional[str] = None) -> None:
    """Log stage completion"""
    if target_lang:
        logger.info(f"✅ {stage_name} completed for {target_lang}")
    else:
        logger.info(f"✅ {stage_name} completed")


def log_stage_error(logger, stage_name: str, error: Exception) -> None:
    """Log stage error"""
    logger.error(f"❌ {stage_name} failed: {error}")


def file_exists(path: str) -> bool:
    """Check if file exists"""
    return Path(path).exists()


def get_file_size(path: str) -> int:
    """Get file size in bytes, or 0 if not found"""
    try:
        return Path(path).stat().st_size
    except FileNotFoundError:
        return 0


def delete_temp_file(path: Optional[str]) -> bool:
    """Delete temporary file if it exists"""
    if not path:
        return False
    
    try:
        if Path(path).exists():
            os.remove(path)
            return True
    except Exception:
        pass
    
    return False


def get_relative_path(full_path: str, base_path: str) -> str:
    """Get relative path from base"""
    try:
        return str(Path(full_path).relative_to(base_path))
    except ValueError:
        return full_path
