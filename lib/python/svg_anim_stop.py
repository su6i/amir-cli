import sys
import os

def inject_stop_css(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # CSS to force animations to end state
    # - delay: negative large value forces it to 'end'
    # - play-state: paused stops it there
    # - iteration-count: 1 ensures it doesn't loop (if delay doesn't cover it)
    stop_style = """
    <style>
      * {
        animation-delay: -36000s !important;
        animation-play-state: paused !important;
        transition-delay: -36000s !important;
        transition-duration: 0s !important;
      }
    </style>
    """

    # Insert before closing tag
    if "</svg>" in content:
        new_content = content.replace("</svg>", stop_style + "\n</svg>")
    else:
        # Fallback append
        new_content = content + stop_style

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Prepared: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python svg_anim_stop.py <input> <output>")
        sys.exit(1)
    
    inject_stop_css(sys.argv[1], sys.argv[2])
