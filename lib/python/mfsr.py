#!/usr/bin/env python3
"""
Amir CLI: Multi-frame Super-Resolution (Burst Mode)
Ultra-Memory-Efficient Engine (Pyramid Alignment + Running Sum)
Optimized for 100MP+ images (e.g. 4x upscaled documents)
"""

import cv2
import numpy as np
import sys
import os
import time

# Config
ALIGN_MAX_DIM = 1000  # Max dimension for alignment calculation

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='█', print_end="\r"):
    """Call in a loop to create terminal progress bar"""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    if iteration == total: 
        print()

def align_ecc_pyramid(target_gray, source_gray, warp_mode=cv2.MOTION_HOMOGRAPHY):
    """
    Calculates alignment warp matrix using a downscaled version of images
    to save memory and CPU on massive files.
    """
    h, w = target_gray.shape[:2]
    scale = 1.0
    
    # Calculate scale factor
    if max(h, w) > ALIGN_MAX_DIM:
        scale = ALIGN_MAX_DIM / float(max(h, w))
        t_small = cv2.resize(target_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        s_small = cv2.resize(source_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        t_small = target_gray
        s_small = source_gray

    # Initial warp matrix
    if warp_mode == cv2.MOTION_HOMOGRAPHY:
        warp_matrix = np.eye(3, 3, dtype=np.float32)
    else:
        warp_matrix = np.eye(2, 3, dtype=np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-8)

    try:
        # Run ECC on small images
        (cc, warp_matrix) = cv2.findTransformECC(t_small, s_small, warp_matrix, warp_mode, criteria, None, 1)
        
        # Scale the warp matrix back for full resolution
        if warp_mode == cv2.MOTION_HOMOGRAPHY:
            # For homography, we adjust the scale in the matrix
            # H_large = S * H_small * S_inv where S is scaling matrix
            # Simplified for uniform scaling:
            warp_matrix[0, 2] /= scale
            warp_matrix[1, 2] /= scale
            warp_matrix[2, 0] *= scale
            warp_matrix[2, 1] *= scale
        else:
            # For Euclidean/Affine:
            warp_matrix[0, 2] /= scale
            warp_matrix[1, 2] /= scale
            
        return warp_matrix
    except Exception:
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: mfsr.py <output> <input1> <input2> ...", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.abspath(sys.argv[1])
    input_paths = sys.argv[2:]
    total_files = len(input_paths)

    if total_files < 2:
        print("❌ At least 2 input images are required.", file=sys.stderr)
        sys.exit(1)

    print(f"⚖️ Processing {total_files} frames (Pyramid Memory Optimization)...")
    
    # 1. Load reference frame
    ref_bgr = cv2.imread(input_paths[0])
    if ref_bgr is None:
        print(f"❌ Could not read reference frame: {input_paths[0]}", file=sys.stderr)
        sys.exit(1)

    ref_gray = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY)
    h, w = ref_bgr.shape[:2]
    
    # Use float32 for buffer (half the RAM of float64, enough for hundreds of frames)
    sum_buffer = ref_bgr.astype(np.float32) / 255.0
    count = 1
    
    # Clear large ref_bgr ASAP
    del ref_bgr
    
    start_time = time.time()
    
    # 2. Iterate through remaining frames
    for i in range(1, total_files):
        img_path = input_paths[i]
        curr_bgr = cv2.imread(img_path)
        
        if curr_bgr is None:
            continue
            
        curr_gray = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)
        
        # Pyramid Alignment calculation
        warp_matrix = align_ecc_pyramid(ref_gray, curr_gray)
        
        if warp_matrix is not None:
            # Warp current frame to match reference (at full resolution)
            warped = cv2.warpPerspective(
                curr_bgr.astype(np.float32) / 255.0, 
                warp_matrix, (w, h), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
            )
            sum_buffer += warped
            count += 1
            del warped # Free immediately
        
        # Aggressive cleanup
        del curr_bgr
        del curr_gray

        # Progress calculation
        elapsed = time.time() - start_time
        avg_time = elapsed / i
        remaining = total_files - i - 1
        eta = avg_time * remaining
        
        suffix = f'({i+1}/{total_files}) Aligned: {count} | ETA: {int(eta)}s'
        print_progress(i + 1, total_files, prefix='Processing:', suffix=suffix, length=30)

    # 3. Final average and save
    print(f"🧬 Finalizing merge of {count} aligned frames...")
    result = sum_buffer / count
    del sum_buffer
    
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    
    cv2.imwrite(output_path, result)
    print(f"✅ Success! Reconstructed image saved at:")
    print(f"👉 {output_path}")

if __name__ == "__main__":
    main()
