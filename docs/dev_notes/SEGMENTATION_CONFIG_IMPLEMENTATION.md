# Subtitle Segmentation Configuration Implementation

## Overview
Implemented a config-based system to enforce minimum and maximum word count constraints for subtitle segments across all languages and video types.

## Changes Made

### 1. Configuration File
**File**: `lib/python/subtitle/config/segmentation.yaml`

Defines word count constraints:
- **Vertical videos** (portrait): 5-7 words per segment
- **Horizontal videos** (landscape): 5-10 words per segment
- **Low-RAM mode**: Slightly reduced constraints to save memory
- **Timing**: Global max segment duration (6 seconds)

### 2. Configuration Loader
**File**: `lib/python/subtitle/config/segmentation.py`

New `SegmentationConfig` class that:
- Loads constraints from YAML without external dependencies (includes fallback parser)
- Provides `get_constraints()` method based on video orientation and RAM mode
- Automatically detects video type (vertical/horizontal) based on max_chars threshold
- Caches values globally for efficiency

### 3. Integration Points

#### A. Config Module Export
**File**: `lib/python/subtitle/config/__init__.py`
- Exports `SegmentationConfig` and `get_segmentation_config()` for module-wide use

#### B. Processor Integration
**File**: `lib/python/subtitle/processor.py`
- Line ~35: Added import for `get_segmentation_config`
- Method `segment_words_smart()`: Now loads constraints from config
- Detects video type: `is_vertical = limit < 30` (max_chars threshold)
- Uses config values for `MIN_WORDS`, `MAX_WORDS`, `MAX_SEG_SEC`
- Passes `MIN_WORDS` to `merge_orphan_segments()` call

#### C. Strict Enforcement
**File**: `lib/python/subtitle/segmentation/helpers.py`
- Function `merge_orphan_segments()`: Enhanced to strictly enforce minimum word count
- Now iteratively merges segments until no segment has fewer than `min_words` words
- Applies constraints to ALL languages (Persian, English, etc.)
- Prevents 2-word or 1-word segments from persisting

## How It Works

### Segmentation Flow
1. **Transcription**: Whisper/MLX generates word-level timestamps
2. **Initial Segmentation**: `segment_words_smart()` creates initial segments using semantic boundaries
   - Loads config constraints
   - Creates segments respecting sentence ends, punctuation, etc.
3. **Orphan Merging**: `merge_orphan_segments()` post-processes
   - Identifies segments with < MIN_WORDS words
   - Merges with adjacent segments until minimum met
   - Enforced for all languages simultaneously

### Applied to All Languages
The config is language-agnostic and applies to:
- English subtitles
- Farsi/Persian subtitles
- Any other supported language
- Bilingual combinations (English + Farsi)

## Configuration Values

```yaml
# Vertical (portrait, max_chars < 30)
vertical:
  min_words: 5    # No 1-4 word segments allowed
  max_words: 7    # Hard ceiling

# Horizontal (landscape, max_chars >= 30)  
horizontal:
  min_words: 5    # No 1-4 word segments allowed
  max_words: 10   # Hard ceiling

# Low-RAM adjustments (when multiple subtitle processes run)
low_ram:
  vertical:
    min_words: 4
    max_words: 6
  horizontal:
    min_words: 4
    max_words: 8
```

## Benefits

1. **Consistency**: All languages follow same word count rules
2. **Readability**: No tiny 1-2 word fragments (like "یک دفعه" → merged into surrounding context)
3. **No Hardcoding**: Constraints are in config.yaml, easily adjustable
4. **Language Agnostic**: Works for English, Farsi, and any future languages
5. **Video-Type Aware**: Different constraints for vertical vs horizontal videos

## Testing Results

### Before Implementation
- **English**: 117/287 entries (41%) with < 5 words
- **Farsi**: 132/287 entries (46%) with < 5 words, including 28 2-word segments and 1 single-word segment

### After Implementation
- Segments with < MIN_WORDS words are automatically merged into adjacent segments
- No violations should persist after `merge_orphan_segments()` is called

## Usage

### To Adjust Constraints
Edit `lib/python/subtitle/config/segmentation.yaml`:
```yaml
horizontal:
  min_words: 5  # Change this value
  max_words: 10 # Change this value
```

Changes apply automatically to all languages on next subtitle generation.

### To Check Current Config
```python
from subtitle.config import get_segmentation_config
config = get_segmentation_config()
constraints = config.get_constraints(is_vertical=False, low_ram=False)
print(constraints)  # {'min_words': 5, 'max_words': 10}
```

## Files Modified
1. `lib/python/subtitle/config/segmentation.yaml` - NEW
2. `lib/python/subtitle/config/segmentation.py` - NEW
3. `lib/python/subtitle/config/__init__.py` - Updated
4. `lib/python/subtitle/processor.py` - Updated (2 locations)
5. `lib/python/subtitle/segmentation/helpers.py` - Updated

## Backward Compatibility
- No breaking changes
- Falls back to defaults if config file missing
- No external dependencies (fallback YAML parser included)
