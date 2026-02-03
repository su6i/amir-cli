import sys
import re

def bake_svg_animation(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Extract Keyframes (animation_name -> final_properties)
    # Regex to find @keyframes NAME { ... }
    # Note: This is a simplified parser assuming standard formatting as seen in the user file.
    keyframes = {}
    
    # helper to find matching brace
    def find_block_content(text, start_index):
        depth = 0
        content_start = text.find('{', start_index)
        if content_start == -1: return None, start_index
        
        depth = 1
        current = content_start + 1
        while current < len(text) and depth > 0:
            if text[current] == '{': depth += 1
            elif text[current] == '}': depth -= 1
            current += 1
        return text[content_start+1:current-1], current

    # Iterate over all @keyframes
    pos = 0
    while True:
        match = re.search(r'@keyframes\s+([\w-]+)\s*', content[pos:])
        if not match: break
        
        anim_name = match.group(1)
        full_match_start = pos + match.start()
        block_content, next_pos = find_block_content(content, full_match_start)
        pos = next_pos
        
        if block_content:
            # Find 'to' or '100%' block
            end_state_match = re.search(r'(?:to|100%)\s*\{([^}]+)\}', block_content)
            if end_state_match:
                props = end_state_match.group(1).strip()
                # Clean up formatting (multiline to single line)
                props = ' '.join(props.split())
                keyframes[anim_name] = props

    # 2. Find Selectors using these animations
    # Regex: selector { ... animation: NAME ... }
    # or animation-name: NAME
    
    overrides = []
    
    # We scan the <style> content again roughly or just regex the whole file for selectors
    # Simpler: Look for "selector { ... animation: ... }" patterns
    # Using a similar block scanner for standard CSS rules
    
    style_start = 0
    while True:
        # Find start of a style rule (very rough: something followed by {)
        # Avoiding @ starting blocks to skip keyframes/media queries roughly
        # This is fragile but fits the user's file structure
        
        # Strategy B: simpler regex for usage
        # This regex finds "Class/Id { ... animation: NAME ... }"
        # It captures the selector and the body
        pass # moving to regex iterator below
        break
        
    # Regex to find selectors using animation
    # format:  .classname { ... animation: name ... }
    # We iterate over the file looking for css blocks
    
    css_iter = re.finditer(r'([^{}@]+)\{([^}]+)\}', content)
    for match in css_iter:
        selector = match.group(1).strip()
        body = match.group(2)
        
        # Check for animation property
        anim_match = re.search(r'animation:\s*([\w-]+)', body)
        if not anim_match:
            # check animation-name
            anim_match = re.search(r'animation-name:\s*([\w-]+)', body)
            
        if anim_match:
            used_anim_name = anim_match.group(1)
            if used_anim_name in keyframes:
                # Create override rule
                final_props = keyframes[used_anim_name]
                override = f"{selector} {{ {final_props} !important; animation: none !important; transition: none !important; }}"
                overrides.append(override)

    # 3. Inject Overrides
    if overrides:
        override_css = "\n<style>\n" + "\n".join(overrides) + "\n</style>\n"
        if "</svg>" in content:
            new_content = content.replace("</svg>", override_css + "</svg>")
        else:
            new_content = content + override_css
    else:
        new_content = content
        print(f"Warning: No animations mapped. Copying original.")

    # 4. Fix for librsvg/rsvg-convert whitespace collapsing
    # We replace standalone spaces in tspans with Non-Breaking Space (\u00A0) literal
    # AND add xml:space="preserve" just in case.
    
    def replacer(m):
        # m.group(1): opening tag, m.group(2): closing tag
        tag_open = m.group(1)
        tag_close = m.group(2)
        # Add xml:space if not present
        if "xml:space" not in tag_open:
            tag_open = tag_open.rstrip('>') + ' xml:space="preserve">'
        
        return f"{tag_open}\u00A0{tag_close}"

    new_content = re.sub(r'(<tspan[^>]*>)\s+(</tspan>)', replacer, new_content)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Baked {len(overrides)} animation end-states to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python svg_bake.py <input> <output>")
        sys.exit(1)
    
    bake_svg_animation(sys.argv[1], sys.argv[2])
