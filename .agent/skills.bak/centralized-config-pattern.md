# Centralized Configuration Pattern (Best Practice 2026)

## Problem Context
When building CLI tools with mixed technology stacks (Bash + Python), maintaining encoding standards across different modules leads to code duplication and inconsistency. Previously, bitrate multipliers, CRF values, and encoding parameters were hardcoded in multiple locations:
- `lib/commands/compress.sh` (Bash)
- `lib/python/subtitle/processor.py` (Python)

**Issue:** Changing a single encoding standard required modifying 2+ files, violating DRY principles.

## Solution: Single Source of Truth Pattern
Industry standard adopted by Netflix, Google, Spotify for multi-language codebases.

### Architecture

```
lib/
├── config/
│   └── media.json          # Single source of truth for encoding standards
├── python/
│   └── media_config.py     # Python API layer
└── amir_lib.sh             # Bash API layer (get_media_config function)
```

### Configuration File (`lib/config/media.json`)
```json
{
  "encoding": {
    "bitrate": {
      "multiplier": 1.1,
      "fallback": "2.5M",
      "min": "500K",
      "max": "50M"
    },
    "quality": {
      "default_crf": 23,
      "default_preset": "medium"
    },
    "hardware_acceleration": {
      "apple_silicon": "h264_videotoolbox",
      "nvidia": "hevc_nvenc",
      "intel": "hevc_qsv",
      "amd": "hevc_amf"
    }
  },
  "audio": {
    "codec": "aac",
    "sample_rate": 44100,
    "channels": "stereo"
  }
}
```

### Usage

#### In Python Scripts
```python
from lib.python.media_config import get_bitrate_multiplier, get_fallback_bitrate, get_default_crf

# Get bitrate multiplier
multiplier = get_bitrate_multiplier()  # Returns 1.1

# Get fallback bitrate
fallback = get_fallback_bitrate()  # Returns "2.5M"

# Get default CRF
crf = get_default_crf()  # Returns 23
```

#### In Bash Scripts
```bash
# Source the library
source "$AMIR_ROOT/lib/amir_lib.sh"

# Get bitrate multiplier
MULTIPLIER=$(get_media_config "encoding.bitrate.multiplier")

# Get fallback bitrate
FALLBACK=$(get_media_config "encoding.bitrate.fallback")

# Get hardware encoder for platform
HW_ENCODER=$(get_hw_encoder "apple_silicon")
```

### Benefits

1. **DRY Compliance:** One place to change encoding standards
2. **Language Agnostic:** Both Bash and Python read the same JSON file
3. **Version Control:** Standards are tracked in git with the codebase
4. **Testability:** Easy to mock/override in tests
5. **Documentation:** JSON file serves as living documentation

### Implementation Notes

**Why JSON instead of YAML?**
- Python has built-in JSON parser (no extra dependencies)
- Bash can parse JSON via Python (already a dependency)
- Faster parsing than YAML
- Type safety (strict syntax)

**File Location:**
- `lib/config/` → Part of the codebase (developer standards)
- `~/.amir/config.yaml` → User-specific preferences (separate concern)

**Backward Compatibility:**
The Python module includes fallback defaults if media.json is missing:
```python
try:
    from lib.python.media_config import get_bitrate_multiplier
except ImportError:
    def get_bitrate_multiplier(): return 1.1
```

### Migration Checklist

When adding a new encoding parameter:
1. ✅ Add value to `lib/config/media.json`
2. ✅ Add convenience function in `lib/python/media_config.py`
3. ✅ Add convenience function in `lib/amir_lib.sh`
4. ✅ Replace hardcoded values in all scripts
5. ✅ Test both Bash and Python consumers

### References
- [Netflix Tech Blog - Configuration Management](https://netflixtechblog.com/)
- [Google SRE Book - Configuration Design](https://sre.google/sre-book/configuration-design/)
- [12-Factor App - Configuration](https://12factor.net/config)

---
**Implemented:** 2026-02-16  
**Pattern Type:** Cross-Language Configuration Management  
**Complexity:** Medium
