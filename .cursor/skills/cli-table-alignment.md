---
description: How to implement pixel-perfect ASCII table alignment in CLI tools, handling Emojis and Unicode correctly.
---

# Skill: Scientific CLI Table Alignment

This skill documents the robust, standard-compliant method for aligning ASCII tables in CLI applications, specifically addressing challenges with Emojis, Variation Selectors, and mixed-width Unicode characters.

## 🛑 The Problem

Standard Bash tools (`printf`, `wc -m`, `wc -c`) and even some simple Python `len()` calls fail to calculate the correct **visual width** of strings in modern terminals for two reasons:

1.  **Double-Width Characters:** Emojis like `📂` or `🚀` often take up 2 columns visually, but count as 1 character in simple string length logic.
2.  **Zero-Width Modifiers:** Emojis often have hidden "Variation Selectors" (e.g., `VS16`) or combining marks (e.g., skin tone) that add to the character count but *do not* consume extra visual space.

**Result:** A table that looks aligned in code (`printf "%-20s"`) breaks visually when Emojis are involved.

## ✅ The Solution: Standard Unicode Width Calculation

The only reliable, cross-platform way to calculate visual width is to use the **Unicode East Asian Width** standard, while explicitly ignoring zero-width categories.

We use a tiny embedded Python script (since Python is standard on Linux/macOS) to perform this calculation strictly.

### 1. The Python Logic (One-Liner)
This logic iterates through characters and:
- Adds **2** if East Asian Width is 'W' (Wide) or 'F' (Fullwidth).
- Adds **0** if category is `Mn` (Non-spacing Mark), `Me` (Enclosing Mark), or `Cf` (Format, e.g., Variation Selectors).
- Adds **1** otherwise.

```python
import unicodedata, sys
s = sys.argv[1]
width = sum(
    2 if unicodedata.east_asian_width(c) in 'WF' else 
    0 if unicodedata.category(c) in ('Mn', 'Me', 'Cf') else 
    1 for c in s
)
print(width)
```

### 2. Bash Implementation

Copy this function into your shell script. It uses `pad_to_width` to dynamically generate the correct number of spaces.

```bash
# Calcuates strict visual width
get_visual_width() {
    python3 -c "import unicodedata, sys; s=sys.argv[1]; print(sum(2 if unicodedata.east_asian_width(c) in 'WF' else 0 if unicodedata.category(c) in ('Mn','Me','Cf') else 1 for c in s))" "$1"
}

# Pads/Truncates text to exact visual width
pad_to_width() {
    local text="$1"
    local target_width="$2"
    local vis_len=$(get_visual_width "$text")
    local pad_len=$((target_width - vis_len))
    
    # TRUNCATION: If text is too long
    if [[ $pad_len -lt 0 ]]; then
        local truncated="$text"
        # Chop chars until it fits
        while [[ $(get_visual_width "$truncated") -gt $((target_width - 2)) ]]; do
            truncated="${truncated%?}"
        done
        echo -n "${truncated}.."
        
        # Re-calc padding for ellipsis
        vis_len=$(get_visual_width "${truncated}..")
        pad_len=$((target_width - vis_len))
    else
        echo -n "$text"
    fi
    
    # PADDING: Print spaces
    if [[ $pad_len -gt 0 ]]; then
        printf "%${pad_len}s" ""
    fi
}
```

### 3. Usage In Tables

Do **not** use `printf "%-20s"` for the text itself. Print the *padded text* as a raw string.

```bash
# Calculate column width once
col_width=30

# Pad content
row_file=$(pad_to_width "📄 File Name.txt" $col_width)
row_status=$(pad_to_width "✅ Done" $col_width)

# Print table row
printf "│ %s │ %s │\n" "$row_file" "$row_status"
```

## Why this works where others fail?

- **`wcwidth` (C Library):** Often outdated or inconsistent across OS versions (e.g., macOS vs Linux libc).
- **Manual Adjustments:** "Add 1 space for every Emoji" fails because not all emojis are 2-wide, and some are 1-wide but look like 2, or vice versa depending on fonts.
- **Python `len()`:** Counts code points, ignoring visual width entirely.

This Unicode-category-aware approach is the "Source of Truth" for modern terminal rendering.
