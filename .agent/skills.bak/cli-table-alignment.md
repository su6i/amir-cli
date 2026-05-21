---
name: cli-table-alignment
description: CLI Table Alignment Technical Encyclopedia: Padding Math, ANSI Escapes, Unicode Normalization, and Professional Data Visualization.
---

# Skill: Scientific CLI Table Alignment

Comprehensive technical protocols for the design and construction of aligned, readable, and professional tables within a Command Line Interface (CLI) in the 2025 ecosystem. This document defines the standards for padding calculations, Unicode-safe width normalization, and ANSI-compatible formatting.

[Back to README](../../README.md)

---

## 1. The Science of Alignment (Padding Math)
Standardizing the structure of columns to ensure visual clarity across varying terminal widths.

### 1.1 Dynamic Column Sizing
*   **Logic:** Calculating the maximum character count for each column in a dataset before generating the output.
*   **Padding Protocol:** Mandatory 1-space or 2-space padding between columns to prevent "text merging."
*   **Alignment Directions:**
    *   **Left-Align:** Standard for text/labels.
    *   **Right-Align:** Standard for numerical data (monetary, counts, IDs) to ensure decimal/digit alignment.
    *   **Center-Align:** Restricted to headers and status badges.

### 1.2 Implementation Protocol (Bash/Zsh)
```bash
# 1.2.1 Utilizing the 'column' Utility (BSD/Linux)
# -t: Creates a table. -s: Defines the delimiter.
printf "ID|NAME|STATUS\n1|System|ON\n2|Disk|OFF" | column -t -s "|"
```

---

## 2. 🛑 The Problem: Emojis & Unicode Breakage
Standard Bash tools (`printf`, `wc -m`, `wc -c`) and even basic Python `len()` calls fail to calculate the correct **visual width** of strings in modern terminals for two reasons:

1.  **Double-Width Characters:** Emojis like `📂` or `🚀` often take up 2 columns visually, but count as 1 character in simple string length logic.
2.  **Zero-Width Modifiers:** Emojis often have hidden "Variation Selectors" (e.g., `VS16`) or combining marks (e.g., skin tone) that add to the character count but *do not* consume extra visual space.

**Result:** A table that looks aligned in code (`printf "%-20s"`) breaks visually when Emojis are involved.

---

## 3. ✅ The Solution: Standard Unicode Width Calculation
The only reliable, cross-platform way to calculate visual width is to use the **Unicode East Asian Width** standard, while explicitly ignoring zero-width categories.

### 3.1 The Python Logic (One-Liner)
This logic iterates through characters and:
- Adds **2** if East Asian Width is 'W' (Wide) or 'F' (Fullwidth).
- Adds **0** if category is `Mn` (Non-spacing Mark), `Me` (Enclosing Mark), or `Cf` (Format).
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

### 3.2 Robust Bash Implementation
Copy this function to ensure pixel-perfect alignment in shell scripts.

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
    
    if [[ $pad_len -lt 0 ]]; then
        local truncated="$text"
        while [[ $(get_visual_width "$truncated") -gt $((target_width - 2)) ]]; do
            truncated="${truncated%?}"
        done
        echo -n "${truncated}.."
        vis_len=$(get_visual_width "${truncated}..")
        pad_len=$((target_width - vis_len))
    else
        echo -n "$text"
    fi
    
    if [[ $pad_len -gt 0 ]]; then
        printf "%${pad_len}s" ""
    fi
}
```

---

## 4. ANSI-Escape Handling & Performance
Fixing common "Table Breakage" bugs in modern terminals.

### 4.1 ANSI-Strip Alignment
*   **Problem:** Color codes (e.g., `\033[31m`) have length but zero visual width.
*   **Protocol:** Always strip ANSI codes before calculating widths, then re-apply them.

### 4.2 High-Performance Visualization (`rich`)
The 2025 Python standard for complex tables. Use `box.ROUNDED` for professional aesthetics.

---

## 5. Technical Appendix: Table Alignment Reference
| Attribute | Technical Implementation | Purpose |
| :--- | :--- | :--- |
| **Header** | Uppercase + Bold | Hierarchy |
| **Separators** | `-`, `|`, `+` (Unicode) | Structuring |
| **Padding** | `str.ljust()` / `rjust()` | Spacing |
| **Sorting** | `sort -k2` | Order |

---
[Back to README](../../README.md)
