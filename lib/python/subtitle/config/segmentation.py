"""
Segmentation configuration loader.
Loads word count constraints from root-level config.yaml.
"""

from pathlib import Path
from typing import Dict, Any, Optional

# Try to import yaml, fallback to manual parsing if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class SegmentationConfig:
    """Manages subtitle segmentation constraints."""

    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """Initialize with config data or load from YAML."""
        if config_data is None:
            config_data = self._load_from_yaml()
        
        self.config = config_data
        self._extract_constraints()

    @staticmethod
    def _load_from_yaml() -> Dict[str, Any]:
        """Load config.yaml from project root with local fallback for compatibility."""
        project_root = Path(__file__).resolve().parents[4]
        candidate_paths = [
            project_root / 'config.yaml',
            Path(__file__).parent / 'segmentation.yaml',
        ]

        for config_path in candidate_paths:
            if not config_path.exists():
                continue

            try:
                if HAS_YAML:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data:
                            return data
                else:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = SegmentationConfig._parse_yaml_manual(f.read())
                        if data:
                            return data
            except Exception as e:
                print(f"Warning: Failed to load config file at {config_path}: {e}")

        return SegmentationConfig._default_config()

    @staticmethod
    def _parse_yaml_manual(yaml_content: str) -> Dict[str, Any]:
        """Manual YAML parser for simple config structure (no external dependency)."""
        config = {}
        current_section = None
        current_subsection = None
        
        for line in yaml_content.split('\n'):
            line = line.rstrip()
            
            # Skip comments and empty lines
            if not line.strip() or line.strip().startswith('#'):
                continue
            
            # Check for section (no leading spaces)
            if line and line[0] not in (' ', '\t'):
                current_section = line.rstrip(':')
                current_subsection = None
                config[current_section] = {}
                continue
            
            # Parse key: value pairs
            if ':' in line:
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                
                key, value = stripped.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Convert value to appropriate type
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                else:
                    try:
                        value = float(value) if '.' in value else int(value)
                    except ValueError:
                        pass  # Keep as string
                
                # Determine nesting level
                if indent >= 4:  # Sub-section
                    if current_section:
                        if isinstance(config[current_section], dict):
                            # Create subsection if needed
                            for k in config[current_section]:
                                if isinstance(config[current_section][k], dict):
                                    config[current_section][k][key] = value
                                    break
                            else:
                                # No subsection found, try to detect one
                                if key in ('vertical', 'horizontal'):
                                    config[current_section][key] = {key: value}
                                else:
                                    config[current_section][key] = value
                        else:
                            config[current_section] = {key: value}
                else:  # Top-level in section
                    if current_section and isinstance(config[current_section], dict):
                        config[current_section][key] = value
        
        # Second pass: properly structure nested sections
        result = {'vertical': {}, 'horizontal': {}, 'timing': {}, 'low_ram': {'vertical': {}, 'horizontal': {}}}
        
        for section, content in config.items():
            if isinstance(content, dict):
                for key, value in content.items():
                    if isinstance(value, dict):
                        result[section][key] = value
                    else:
                        if section not in result:
                            result[section] = {}
                        result[section][key] = value
        
        return result if any(result.values()) else SegmentationConfig._default_config()

    def _extract_constraints(self):
        """Extract and cache commonly accessed values."""
        # Vertical (portrait) constraints
        vertical = self.config.get('vertical', {})
        self.vertical_min_words = vertical.get('min_words', 5)
        self.vertical_max_words = vertical.get('max_words', 7)
        self.vertical_max_chars = vertical.get('max_chars', 30)

        # Horizontal (landscape) constraints
        horizontal = self.config.get('horizontal', {})
        self.horizontal_min_words = horizontal.get('min_words', 5)
        self.horizontal_max_words = horizontal.get('max_words', 10)
        self.horizontal_max_chars = horizontal.get('max_chars', 42)

        # Timing constraints
        timing = self.config.get('timing', {})
        self.max_segment_seconds = timing.get('max_segment_seconds', 6.0)
        self.min_duration = timing.get('min_duration', 0.4)

        # Low-RAM mode constraints
        low_ram = self.config.get('low_ram', {})
        vertical_low = low_ram.get('vertical', {})
        horizontal_low = low_ram.get('horizontal', {})

        self.low_ram_vertical_min = vertical_low.get('min_words', 4)
        self.low_ram_vertical_max = vertical_low.get('max_words', 6)
        self.low_ram_horizontal_min = horizontal_low.get('min_words', 4)
        self.low_ram_horizontal_max = horizontal_low.get('max_words', 8)

    def get_constraints(self, is_vertical: bool = True, low_ram: bool = False) -> Dict[str, int]:
        """
        Get word count constraints for a given video orientation.
        
        Args:
            is_vertical: True for portrait (vertical) videos, False for landscape (horizontal)
            low_ram: True if running in low-RAM mode
        
        Returns:
            Dictionary with 'min_words' and 'max_words' keys
        """
        if low_ram:
            if is_vertical:
                return {
                    'min_words': self.low_ram_vertical_min,
                    'max_words': self.low_ram_vertical_max,
                }
            else:
                return {
                    'min_words': self.low_ram_horizontal_min,
                    'max_words': self.low_ram_horizontal_max,
                }
        else:
            if is_vertical:
                return {
                    'min_words': self.vertical_min_words,
                    'max_words': self.vertical_max_words,
                }
            else:
                return {
                    'min_words': self.horizontal_min_words,
                    'max_words': self.horizontal_max_words,
                }

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """Return default configuration if YAML loading fails."""
        return {
            'vertical': {
                'min_words': 5,
                'max_words': 7,
                'max_chars': 30,
            },
            'horizontal': {
                'min_words': 5,
                'max_words': 10,
                'max_chars': 42,
            },
            'timing': {
                'max_segment_seconds': 6.0,
                'min_duration': 0.4,
            },
            'low_ram': {
                'vertical': {
                    'min_words': 4,
                    'max_words': 6,
                },
                'horizontal': {
                    'min_words': 4,
                    'max_words': 8,
                },
            },
        }


# Global instance for reuse
_segmentation_config_instance: Optional[SegmentationConfig] = None


def get_segmentation_config() -> SegmentationConfig:
    """Get or create the global SegmentationConfig instance."""
    global _segmentation_config_instance
    if _segmentation_config_instance is None:
        _segmentation_config_instance = SegmentationConfig()
    return _segmentation_config_instance
