# subtitle/__init__.py
from .processor import SubtitleProcessor, SubtitleStyle

# Re-exported as the package's public API (consumed via `from subtitle import ...`
# elsewhere in the codebase), not used directly in this file.
__all__ = ["SubtitleProcessor", "SubtitleStyle"]
