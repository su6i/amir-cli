import os
import sys
import requests
import random
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def create_premium_gradient(output_path):
    """Generates a modern, professional mesh-style gradient with subtle noise."""
    width, height = 1280, 720
    # Pick two harmonious deep colors
    base_colors = [
        (random.randint(10, 40), random.randint(20, 50), random.randint(60, 100)), # Deep blue/purple
        (random.randint(40, 80), random.randint(10, 30), random.randint(50, 90)),   # Deep magenta/violet
        (random.randint(10, 30), random.randint(50, 80), random.randint(40, 70)),   # Deep teal
    ]
    c1 = random.choice(base_colors)
    c2 = random.choice([c for c in base_colors if c != c1])
    
    # Create base linear gradient
    base = Image.new('RGB', (width, height), c1)
    draw = ImageDraw.Draw(base)
    
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * (y / height))
        g = int(c1[1] + (c2[1] - c1[1]) * (y / height))
        b = int(c1[2] + (c2[2] - c1[2]) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Add a glowing orb for 'mesh' feel
    orb = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    orb_draw = ImageDraw.Draw(orb)
    orb_size = random.randint(600, 1000)
    orb_pos = (random.randint(0, width), random.randint(0, height))
    
    for r in range(orb_size, 0, -2):
        alpha = int(80 * (1 - r / orb_size))
        orb_draw.ellipse([orb_pos[0]-r, orb_pos[1]-r, orb_pos[0]+r, orb_pos[1]+r], 
                         fill=(random.randint(150, 255), random.randint(150, 255), 255, alpha))
    
    base.paste(orb, (0, 0), orb)
    base = base.filter(ImageFilter.GaussianBlur(radius=50))
    
    # Add noise/grain for high-end texture
    noise = Image.new('RGB', (width, height))
    pixels = noise.load()
    for x in range(width):
        for y in range(height):
            n = random.randint(-15, 15)
            pixels[x, y] = (max(0, min(255, base.getpixel((x,y))[0] + n)),
                            max(0, min(255, base.getpixel((x,y))[1] + n)),
                            max(0, min(255, base.getpixel((x,y))[2] + n)))
    
    noise.save(output_path, quality=95)
    print(f"✨ Created premium mesh gradient fallback: {output_path}")

def get_relevant_image(query, output_path):
    print(f"🔍 Searching for visual assets for: '{query}'...")
    
    # Filter out common stop words and short words to get better image results
    # This prevents long technical titles from returning random cats (source.unsplash fallback)
    stop_words = {'the', 'when', 'with', 'and', 'from', 'build', 'themselves', 'part', 'merged'}
    raw_keywords = query.replace(" ", "_").replace("-", "_").split("_")
    filtered = [w for w in raw_keywords if len(w) > 3 and w.lower() not in stop_words]
    
    if not filtered:
        filtered = ["technology", "abstract", "digital"]
    
    # Use top 3 filtered keywords for better accuracy
    keywords = ",".join(filtered[:3])
    print(f"🎯 Refined keywords: {keywords}")

    sources = [
        f"https://loremflickr.com/1280/720/{keywords},technology/all",
        f"https://source.unsplash.com/1280x720/?{keywords},abstract"
    ]
    
    for url in sources:
        try:
            response = requests.get(url, timeout=8, allow_redirects=True)
            if response.status_code == 200 and len(response.content) > 1000:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ High-quality image fetched from {url.split('/')[2]}")
                return True
        except Exception:
            continue

    # Premium Fallback if APIs fail
    create_premium_gradient(output_path)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    get_relevant_image(sys.argv[1], sys.argv[2])
