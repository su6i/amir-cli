import cv2
import numpy as np
import sys
import os

def process_scan(input_path, output_path, bw=True):
    # ---------- 1. Load image ----------
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file {input_path} not found.")
        sys.exit(1)
        
    img = cv2.imread(input_path)
    if img is None:
        print(f"❌ Error: Could not read image {input_path}")
        sys.exit(1)

    # ---------- 2. Convert to Grayscale ----------
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ---------- 3. Background Normalization ----------
    # Use a much larger kernel to avoid local "halos" around text
    h, w = gray.shape
    kernel_size = int(max(h, w) / 10) | 1 # Ensure odd number
    background = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

    # Normalize illumination (Flatten the paper to white)
    normalized = cv2.divide(gray, background, scale=255)

    # ---------- 4. Histogram-based Crushing (User Request) ----------
    # Instead of complex adaptive logic, we crush the top of the histogram
    # Most paper grain is in the top 10-20% of intensity after normalization
    normalized = cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX)
    
    # ---------- 5. Final Result Selection ----------
    result = normalized

    # ---------- 6. Professional Administrative Binarization ----------
    if bw:
        # Simple thresholding: Anything above 180 (light grey) is white
        # Anything below is black (with morphological cleanup)
        _, result = cv2.threshold(normalized, 180, 255, cv2.THRESH_BINARY)
        
        # Cleanup "chicken pox" (dots)
        result = cv2.medianBlur(result, 3)

    # ---------- 7. Save result ----------
    cv2.imwrite(output_path, result)
    print(f"✅ Saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python doc_scan.py <input> <output> [--no-bw]")
        sys.exit(1)
        
    in_file = sys.argv[1]
    out_file = sys.argv[2]
    bw_mode = "--no-bw" not in sys.argv
    
    process_scan(in_file, out_file, bw=bw_mode)
