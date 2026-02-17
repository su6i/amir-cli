import sys
import os
import re
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def is_latin(char):
    return ord(char) < 0x0600

def draw_mixed_text(draw, pos, text, font_fa, font_en, fill, anchor='la'):
    if not text:
        return 0
    chunks = []
    current_font = font_en if is_latin(text[0]) else font_fa
    current_chunk = text[0]
    for char in text[1:]:
        f = font_en if is_latin(char) else font_fa
        if f == current_font:
            current_chunk += char
        else:
            chunks.append((current_chunk, current_font))
            current_chunk = char
            current_font = f
    chunks.append((current_chunk, current_font))
    total_w = 0
    chunk_data = []
    for chunk, f in chunks:
        bbox = draw.textbbox((0, 0), chunk, font=f)
        w = bbox[2] - bbox[0]
        total_w += w
        chunk_data.append((chunk, f, w))
    x, y = pos
    current_x = x - total_w if anchor == 'ra' else x
    for chunk, f, w in chunk_data:
        draw.text((current_x, y), chunk, font=f, fill=fill)
        current_x += w
    return total_w

class PageManager:
    def __init__(self, base_output_path, width, height, margin):
        self.base_output_path = base_output_path
        self.width = width
        self.height = height
        self.margin = margin
        self.pages = []
        self._new_page()

    def _new_page(self):
        img = Image.new('RGB', (self.width, self.height), color='white')
        draw = ImageDraw.Draw(img)
        self.pages.append(img)
        self.current_draw = draw
        self.current_y = self.margin

    def check_overflow(self, needed_h):
        if self.current_y + needed_h > self.height - self.margin:
            self._new_page()

    def save_all(self):
        base, ext = os.path.splitext(self.base_output_path)
        # Always save pages with a suffix if multiple, else just the base
        if len(self.pages) == 1:
            self.pages[0].save(self.base_output_path)
            return [self.base_output_path]
        else:
            paths = []
            for i, img in enumerate(self.pages):
                p = f"{base}_page_{i}{ext}"
                img.save(p)
                paths.append(p)
            return paths

def render_markdown(input_path, output_path, font_path, fallback_path):
    WIDTH, HEIGHT, MARGIN = 2480, 3508, 200
    pm = PageManager(output_path, WIDTH, HEIGHT, MARGIN)
    try:
        font_fa_h1 = ImageFont.truetype(font_path, 80)
        font_fa_p = ImageFont.truetype(font_path, 45)
        font_en_h1 = ImageFont.truetype(fallback_path, 80)
        font_en_p = ImageFont.truetype(fallback_path, 45)
    except:
        font_fa_h1 = font_fa_p = font_en_h1 = font_en_p = ImageFont.load_default()

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    def process_rtl(text):
        return get_display(arabic_reshaper.reshape(text))

    for line in lines:
        line = line.strip()
        if not line:
            pm.current_y += 40
            continue
        if line.startswith('# '):
            pm.check_overflow(150)
            draw_mixed_text(pm.current_draw, (WIDTH - MARGIN, pm.current_y), process_rtl(line[2:]), font_fa_h1, font_en_h1, 'black', anchor='ra')
            pm.current_y += 120
        elif line.startswith('## '):
            pm.check_overflow(130)
            draw_mixed_text(pm.current_draw, (WIDTH - MARGIN, pm.current_y), process_rtl(line[3:]), font_fa_h1, font_en_h1, 'black', anchor='ra')
            pm.current_y += 100
        else:
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
            words = line.split()
            current_line = []
            for word in words:
                test = " ".join(current_line + [word])
                temp_img = Image.new('RGB', (WIDTH, 100))
                w = draw_mixed_text(ImageDraw.Draw(temp_img), (0, 0), process_rtl(test), font_fa_p, font_en_p, 'black')
                if w > WIDTH - 2 * MARGIN:
                    pm.check_overflow(70)
                    draw_mixed_text(pm.current_draw, (WIDTH - MARGIN, pm.current_y), process_rtl(" ".join(current_line)), font_fa_p, font_en_p, 'black', anchor='ra')
                    pm.current_y += 70
                    current_line = [word]
                else:
                    current_line.append(word)
            if current_line:
                pm.check_overflow(70)
                draw_mixed_text(pm.current_draw, (WIDTH - MARGIN, pm.current_y), process_rtl(" ".join(current_line)), font_fa_p, font_en_p, 'black', anchor='ra')
                pm.current_y += 75
    pm.save_all()

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(1)
    render_markdown(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv)>3 else "/Library/Fonts/B-NAZANIN.TTF", sys.argv[4] if len(sys.argv)>4 else "/System/Library/Fonts/Supplemental/Times New Roman.ttf")
