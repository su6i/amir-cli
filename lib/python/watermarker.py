#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from PIL import Image, ImageOps, ImageDraw, ImageFont

"""
🌊 Universal Watermarker (Housi / Amir-CLI)
author: Su6i Assistant
version: 1.1.0

Features:
- Images: Watermark with Logo (File) or Text.
- Videos: Watermark with Logo (File) or Text (using ffmpeg).
- Supports positioning (Corners, Center).
- Supports scaling.
- Supports resizing output (--resize WxH).
"""

def watermark_image(base_path, output_path, watermark_file=None, watermark_text=None, position='SE', opacity=255, resize=None):
    try:
        base = Image.open(base_path).convert("RGBA")
        
        # Apply Resize if requested
        if resize:
            try:
                w, h = map(int, resize.lower().split('x'))
                base = base.resize((w, h), Image.Resampling.LANCZOS)
            except:
                print("❌ Invalid resize format. Use WxH (e.g. 400x120)")
                return

        # Create a transparent layer for the watermark
        layer = Image.new("RGBA", base.size, (0,0,0,0))
        
        wm_width, wm_height = 0, 0
        wm_img = None
        
        if watermark_file:
            # === IMAGE MODE ===
            wm = Image.open(watermark_file).convert("RGBA")
            
            # Smart Scaling (default 20% of base width)
            target_width = int(base.width * 0.20)
            aspect_ratio = wm.height / wm.width
            target_height = int(target_width * aspect_ratio)
            wm = wm.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            wm_img = wm
            wm_width, wm_height = wm.size
            
        elif watermark_text:
            # === TEXT MODE ===
            draw = ImageDraw.Draw(layer)
            # Try to load a font (default fallback)
            font_size = int(base.height * 0.05) # 5% of height
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()
            
            # Calculate text size
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            wm_width = bbox[2] - bbox[0]
            wm_height = bbox[3] - bbox[1]
            wm_img = None 
            
        else:
            print("❌ Error: Provide either --text or --image")
            return

        # Calculate Position (Padding 5%)
        padding = int(base.width * 0.05)
        x, y = 0, 0
        
        if position == 'SE': # Bottom Right
            x = base.width - wm_width - padding
            y = base.height - wm_height - padding
        elif position == 'SW': # Bottom Left
            x = padding
            y = base.height - wm_height - padding
        elif position == 'NE': # Top Right
            x = base.width - wm_width - padding
            y = padding
        elif position == 'NW': # Top Left
            x = padding
            y = padding
        elif position == 'C': # Center
            x = (base.width - wm_width) // 2
            y = (base.height - wm_height) // 2

        # Draw
        if watermark_file:
            layer.paste(wm_img, (x, y))
        elif watermark_text:
            draw = ImageDraw.Draw(layer)
            # Draw Text with Shadow
            draw.text((x+1, y+1), watermark_text, font=font, fill=(0,0,0,100))
            draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, opacity))

        # Composite
        final = Image.alpha_composite(base, layer)
        
        # Save
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            final = final.convert("RGB") # Remove Alpha for JPG
        final.save(output_path)
        print(f"✅ Image Saved: {output_path}")

    except Exception as e:
        print(f"❌ Image Error: {e}")

def watermark_video(base_path, output_path, watermark_file=None, watermark_text=None, position='SE', resize=None):
    """
    Uses ffmpeg to overlay watermark and optionally resize.
    """
    if not watermark_file and not watermark_text:
        print("❌ Video Mode requires --image (Text not fully supported in simple mode yet, use image)")
        return

    # FFMPEG Overlay Position Logic
    overlay_cmd = ""
    scale_filter = ""
    
    if resize:
        w, h = resize.lower().split('x')
        # [0:v]scale=W:H[bg]; ...
    
    # Position Logic
    if position == 'SE':
        overlay_cmd = "main_w-overlay_w-20:main_h-overlay_h-20"
    elif position == 'SW':
        overlay_cmd = "20:main_h-overlay_h-20"
    elif position == 'NE':
        overlay_cmd = "main_w-overlay_w-20:20"
    elif position == 'NW':
        overlay_cmd = "20:20"
    elif position == 'C':
        overlay_cmd = "(main_w-overlay_w)/2:(main_h-overlay_h)/2"

    cmd = []
    if watermark_file:
        filter_str = ""
        if resize:
             w, h = resize.lower().split('x')
             # Resize Base -> [bg]
             # Resize Watermark -> [wm]
             # Overlay
             filter_str = f"[0:v]scale={w}:{h}[bg];[1:v]scale=iw*0.5:-1[wm];[bg][wm]overlay={overlay_cmd}"
        else:
             filter_str = f"[1:v]scale=iw*0.5:-1[wm];[0:v][wm]overlay={overlay_cmd}"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", base_path,
            "-i", watermark_file,
            "-filter_complex", filter_str,
            "-codec:a", "copy",
            output_path
        ]
    
    print(f"🎬 Processing Video: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Video Saved: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error: {e}")
    except FileNotFoundError:
        print("❌ FFmpeg not found! Please install it (brew install ffmpeg).")


def main():
    parser = argparse.ArgumentParser(description="Universal Watermarker CLI")
    parser.add_argument("input", help="Input file (Image or Video)")
    parser.add_argument("-o", "--output", help="Output file path", required=True)
    parser.add_argument("-i", "--image", help="Path to watermark image")
    parser.add_argument("-t", "--text", help="Watermark text")
    parser.add_argument("-p", "--pos", default="SE", choices=['SE', 'SW', 'NE', 'NW', 'C'], help="Position")
    parser.add_argument("-r", "--resize", help="Resize output (e.g. 400x120)")
    
    args = parser.parse_args()
    
    # Detect File Type
    ext = os.path.splitext(args.input)[1].lower()
    
    if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
         watermark_image(args.input, args.output, args.image, args.text, args.pos, resize=args.resize)
             
    elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
        watermark_video(args.input, args.output, args.image, args.text, args.pos, resize=args.resize)
    else:
        print("❌ Unknown file type.")

def process_resize_image(input_path, output_path, size_str):
    pass 

if __name__ == "__main__":
    main()
