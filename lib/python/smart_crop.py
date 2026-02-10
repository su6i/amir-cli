#!/usr/bin/env python3
import sys
import os
import cv2
import numpy as np

def smart_crop(input_path, output_path, margin=0):
    """
    Detects the largest subject (document/receipt) in the image and crops to it.
    """
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    img = cv2.imread(input_path)
    if img is None:
        print(f"Error: Failed to load image: {input_path}")
        sys.exit(1)

    h_orig, w_orig = img.shape[:2]
    
    # 1. Preprocessing
    # Use grayscale for detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Gaussian Blur to remove noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Gaussian Blur to remove noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Switch to Canny Edge Detection (More robust for documents on similar background)
    # Thresholds 50/150 are standard starting points
    edges = cv2.Canny(blurred, 50, 150)
    
    # Dilate edges to connect text blocks and lines into a single "blob"
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    processed = cv2.dilate(edges, kernel, iterations=4)
    
    # 2. Find Contours
    # RETR_EXTERNAL retrieves only the extreme outer contours
    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("Warning: No distinct object found. Copying original.")
        cv2.imwrite(output_path, img)
        sys.exit(0)

    # Sort by area to find the largest object
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    largest = contours[0]
    
    # 3. Calculate Bounding Box
    x, y, w, h = cv2.boundingRect(largest)
    
    # Safety Check: If the detected area is too small (< 5% of image), probably noise
    img_area = w_orig * h_orig
    contour_area = cv2.contourArea(largest)
    if contour_area / img_area < 0.05:
         print(f"Warning: Detected object is too small ({contour_area/img_area:.1%}). Copying original.")
         cv2.imwrite(output_path, img)
         sys.exit(0)

    # Apply Margin (if requested)
    # Ensure we don't go out of bounds
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(w_orig - x, w + 2*margin)
    h = min(h_orig - y, h + 2*margin)
    
    print(f"Applying Smart Crop: {w}x{h} at ({x}, {y})")
    
    # 4. Crop
    cropped = img[y:y+h, x:x+w]
    
    # 5. Save
    cv2.imwrite(output_path, cropped)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python smart_crop.py <input> <output> [margin]")
        sys.exit(1)
        
    in_file = sys.argv[1]
    out_file = sys.argv[2]
    margin_px = int(sys.argv[3]) if len(sys.argv) > 3 else 10 # Default safety margin 10px
    
    smart_crop(in_file, out_file, margin_px)
