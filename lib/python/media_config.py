#!/usr/bin/env python3
"""
Centralized Media Configuration API
Industry Best Practice: Single Source of Truth for encoding parameters
Used by: subtitle/processor.py and all Python-based media tools
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional, Dict, List


class MediaConfig:
    """Singleton configuration loader for media encoding standards"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load configuration from lib/config/media.json"""
        # Find AMIR_ROOT
        amir_root = os.getenv("AMIR_ROOT")
        if not amir_root:
            # Try to find it relative to this file
            current_file = Path(__file__).resolve()
            amir_root = current_file.parent.parent.parent
        
        config_path = Path(amir_root) / "lib" / "config" / "media.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Media config not found: {config_path}")
        
        with open(config_path, 'r') as f:
            self._config = json.load(f)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key_path: Dot-separated path (e.g., 'encoding.bitrate.multiplier')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Example:
            >>> config = MediaConfig()
            >>> config.get('encoding.bitrate.multiplier')
            1.1
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    # Convenience methods for common parameters
    
    def get_bitrate_multiplier(self) -> float:
        """Get the bitrate multiplier for source-aware encoding"""
        return float(self.get('encoding.bitrate.multiplier', 1.1))
    
    def get_fallback_bitrate(self) -> str:
        """Get fallback bitrate when source detection fails"""
        return self.get('encoding.bitrate.fallback', '2.5M')
    
    def get_default_crf(self) -> int:
        """Get default CRF value for CPU encoding"""
        return int(self.get('encoding.quality.default_crf', 23))
    
    def get_default_preset(self) -> str:
        """Get default preset for CPU encoding"""
        return self.get('encoding.quality.default_preset', 'medium')
    
    def detect_best_hw_encoder(self) -> Dict[str, str]:
        """
        Automatically detect the best available hardware encoder on this system
        
        Returns:
            Dictionary with 'encoder', 'codec', and 'platform' keys
            
        Example:
            >>> config = MediaConfig()
            >>> result = config.detect_best_hw_encoder()
            >>> result
            {'encoder': 'hevc_videotoolbox', 'codec': 'h265', 'platform': 'apple_silicon'}
        """
        priority_list = self.get('encoding.hardware_acceleration.priority', [])
        
        # Check each encoder in priority order
        for item in priority_list:
            encoder = item.get('encoder')
            if self._is_encoder_available(encoder):
                return {
                    'encoder': encoder,
                    'codec': item.get('codec', 'h264'),
                    'platform': item.get('platform', 'unknown')
                }
        
        # Fallback to CPU encoder
        fallback = self.get('encoding.hardware_acceleration.fallback', {})
        return {
            'encoder': fallback.get('encoder', 'libx264'),
            'codec': fallback.get('codec', 'h264'),
            'platform': 'cpu'
        }
    
    def _is_encoder_available(self, encoder: str) -> bool:
        """
        Check if a specific encoder is available in ffmpeg
        
        Args:
            encoder: Encoder name (e.g., 'hevc_videotoolbox')
            
        Returns:
            True if encoder is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-encoders'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return encoder in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_audio_codec(self) -> str:
        """Get standard audio codec"""
        return self.get('audio.codec', 'aac')
    
    def get_audio_sample_rate(self) -> int:
        """Get standard audio sample rate"""
        return int(self.get('audio.sample_rate', 44100))


# Global singleton instance
_media_config = MediaConfig()

# Convenience functions for direct import
def get_bitrate_multiplier() -> float:
    """Get the bitrate multiplier for source-aware encoding"""
    return _media_config.get_bitrate_multiplier()

def get_fallback_bitrate() -> str:
    """Get fallback bitrate when source detection fails"""
    return _media_config.get_fallback_bitrate()

def get_default_crf() -> int:
    """Get default CRF value for CPU encoding"""
    return _media_config.get_default_crf()

def detect_best_hw_encoder() -> Dict[str, str]:
    """
    Automatically detect the best available hardware encoder
    
    Returns:
        Dictionary with 'encoder', 'codec', and 'platform' keys
    """
    return _media_config.detect_best_hw_encoder()

