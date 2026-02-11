#!/usr/bin/env python3
import sys
import os
import cv2
import numpy as np
import subprocess
import re
import tempfile
import pytesseract

def order_points(pts):
    # order points: top-left, top-right, bottom-right, bottom-left
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def get_orientation(img_path):
    """Detects orientation using Tesseract OSD (Orientation and Script Detection)"""
    try:
        # Check if tesseract is available in path
        cmd = ['tesseract', img_path, 'stdout', '--psm', '0']
        # Tesseract OSD output example:
        # Orientation in degrees: 90
        # Orientation confidence: 4.89
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
        
        match = re.search(r'Orientation in degrees: (\d+)', result)
        if match:
            # Tesseract 5.x Orientation results:
            # 0: Upright (Perfect)
            # 90: Need 270 rotation (CCW 90)
            # 180: Need 180 rotation
            # 270: Need 90 rotation (CW 90)
            return int(match.group(1))
    except Exception:
        pass
    return 0

def apply_rotation(img, orientation):
    # OpenCV rotation constants
    if orientation == 90:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif orientation == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif orientation == 270:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    return img

def get_smart_filename(img, original_path):
    """
    UNIVERSAL: Multi-strategy OCR for ID cards from ANY country
    Supports: English, French, Spanish, German, Italian, Portuguese, Arabic, Persian, Chinese, Japanese, Korean, Russian, etc.
    """
    from collections import Counter
    
    # === Helper Functions ===
    def preprocess_multipass(img, strategy='balanced'):
        """3 different preprocessing strategies"""
        h, w = img.shape[:2]
        
        if strategy == 'high_contrast':
            scale = 3000.0 / w
            resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
        elif strategy == 'balanced':
            scale = 2500.0 / w
            resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            gray = cv2.bilateralFilter(gray, 9, 75, 75)
            return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        else:  # soft
            scale = 2000.0 / w
            resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gray = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
            return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    def normalize_name(name):
        """Fix common OCR digit->letter errors"""
        if not name:
            return ""
        corrections = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '6': 'G'}
        return ''.join(corrections.get(c, c) if c.isdigit() else c for c in name)
    
    # === UNIVERSAL Configuration for ALL Countries ===
    # Name field labels in 50+ languages
    name_labels = {
        # Latin-based (Europe, Americas, Africa)
        'NAME', 'SURNAME', 'LASTNAME', 'FIRSTNAME', 'GIVEN', 'FAMILY',
        'NOM', 'PRENOM', 'PRENOMS', 'FAMILLE',  # French
        'NOMBRE', 'APELLIDO', 'APELLIDOS',  # Spanish
        'NOME', 'SOBRENOME', 'APELIDO',  # Portuguese
        'COGNOME', 'NOME',  # Italian
        'NACHNAME', 'VORNAME', 'FAMILIENNAME',  # German
        'ACHTERNAAM', 'VOORNAAM',  # Dutch
        'EFTERNAVN', 'FORNAVN',  # Danish
        'SUKUNIMI', 'ETUNIMI',  # Finnish
        'EFTERNAMN', 'FÖRNAMN',  # Swedish
        'ETTERNAVN', 'FORNAVN',  # Norwegian
        'NAZWISKO', 'IMIĘ',  # Polish
        'PŘÍJMENÍ', 'JMÉNO',  # Czech
        'PRIEZVISKO', 'MENO',  # Slovak
        'VEZETÉKNÉV', 'UTÓNÉV',  # Hungarian
        'SOYAD', 'ADI',  # Turkish
        
        # Cyrillic (Russia, Eastern Europe)
        'ФАМИЛИЯ', 'ИМЯ', 'ОТЧЕСТВО',  # Russian
        'ПРІЗВИЩЕ', "ІМ'Я",  # Ukrainian
        'ПРЕЗИМЕ', 'ИМЕ',  # Bulgarian/Serbian
        
        # Arabic script (Middle East, North Africa)
        'اسم', 'الاسم', 'اللقب', 'العائلة',  # Arabic
        'نام', 'نام خانوادگی',  # Persian/Farsi
        
        # Asian
        '姓名', '姓', '名',  # Chinese
        '名前', '氏名', '姓',  # Japanese
        '이름', '성명', '성',  # Korean
        'ชื่อ', 'นามสกุล',  # Thai
        'TÊN', 'HỌ',  # Vietnamese
        
        # Generic/Universal
        'ID', 'IDENTITY', 'HOLDER', 'BEARER', 'OWNER'
    }
    
    # Universal noise words (document headers, not names)
    noise_words = {
        # English
        'REPUBLIC', 'KINGDOM', 'STATE', 'FEDERAL', 'NATIONAL', 'IDENTITY', 'CARD', 'PASSPORT',
        'DOCUMENT', 'NUMBER', 'DATE', 'BIRTH', 'ISSUED', 'EXPIRES', 'VALID', 'UNTIL',
        # French
        'REPUBLIQUE', 'FRANCAISE', 'PREFECTURE', 'DEMANDE', 'CARTE', 'SEJOUR', 
        'RECEPISSE', 'TITRE', 'DOSSIER', 'NATIONALITE', 'ADRESSE',
        # Spanish
        'REPUBLICA', 'NACIONAL', 'IDENTIDAD', 'CEDULA', 'DOCUMENTO',
        # German
        'BUNDESREPUBLIK', 'AUSWEIS', 'PERSONALAUSWEIS',
        # Arabic (transliterated)
        'JUMHURIYAH', 'WATANIYA', 'BITAQA',
        # Generic
        'SIGNATURE', 'PHOTO', 'ADDRESS', 'NATIONALITY', 'SEX', 'HEIGHT', 'EYES'
    }
    
    try:
        print("🌍 Universal OCR: Multi-language extraction...")
        
        # === STRATEGY 1: Position-Based (Most Reliable) ===
        name_position = None
        try:
            processed = preprocess_multipass(img, 'balanced')
            # Use all available languages (Tesseract supports 100+ languages)
            data = pytesseract.image_to_data(processed, 
                                            lang='eng+fra+spa+deu+ita+por+rus+ara+chi_sim+jpn+kor',
                                            output_type=pytesseract.Output.DICT)
            
            for i, text in enumerate(data['text']):
                if not text.strip() or int(data['conf'][i]) < 30:
                    continue
                    
                text_upper = text.upper().strip()
                # Check if it matches any name label (any language)
                if any(label in text_upper for label in name_labels):
                    # Check next words
                    for j in range(i+1, min(i+5, len(data['text']))):
                        next_text = data['text'][j].strip()
                        if next_text and int(data['conf'][j]) > 40:
                            # Extract alphanumeric (works for Latin, Cyrillic, Arabic, CJK)
                            clean = re.sub(r'[^\w]+', '', next_text.upper())
                            if len(clean) >= 3 and clean not in noise_words:
                                name_position = clean
                                print(f"  ✅ Position-based: {name_position}")
                                break
                if name_position:
                    break
        except Exception as e:
            print(f"  ⚠️  Position strategy failed: {e}")
        
        # === STRATEGY 2: Multi-Pass OCR ===
        text_results = {}
        for strategy in ['balanced', 'high_contrast', 'soft']:
            try:
                processed = preprocess_multipass(img, strategy)
                # Multi-language OCR
                text_results[strategy] = pytesseract.image_to_string(
                    processed, 
                    lang='eng+fra+spa+deu+ita+por+rus+ara+chi_sim+jpn+kor',
                    config='--psm 6'
                )
            except:
                text_results[strategy] = ""
        
        # === STRATEGY 3: Pattern Matching (Universal) ===
        name_patterns = []
        for strategy, text in text_results.items():
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            for line in lines:
                line_up = line.upper()
                # Try to find name labels
                for label in name_labels:
                    if label in line_up.split():
                        # Split by label and take what comes after
                        parts = re.split(r'\b' + re.escape(label) + r'\b', line_up, maxsplit=1)
                        if len(parts) > 1:
                            raw = re.sub(r'^[:\.\-°\(\)\s]+', '', parts[1].strip())
                            # Remove common prefixes (Mr., Mrs., M., Mme, etc.)
                            raw = re.sub(r'^(MR|MRS|MS|M|MME|MLLE|DR|PROF|SIR|MISS)[\.\s]+', '', raw)
                            
                            # Extract words (works for all alphabets)
                            # Keep letters from ANY alphabet (Latin, Cyrillic, Arabic, CJK, etc.)
                            words = [w for w in re.split(r'[^\w]+', raw) if len(w) >= 3 and w not in noise_words]
                            
                            if words:
                                name_patterns.append(('_'.join(words[:2]), strategy))
                                break
        
        # === COMBINE STRATEGIES ===
        final_name = None
        if name_position:
            final_name = name_position
        elif name_patterns:
            balanced = [n[0] for n in name_patterns if n[1] == 'balanced']
            final_name = balanced[0] if balanced else name_patterns[0][0]
        
        if final_name:
            final_name = normalize_name(final_name)
            print(f"  ✅ Extracted name: {final_name}")
        
        # === EXTRACT NUMBER (Universal - works for all countries) ===
        # ID numbers vary: 6-20 digits (SSN, passport, national ID, etc.)
        numbers = []
        for text in text_results.values():
            # Normalize: O→0, I/l→1, S→5
            clean = text.upper().replace(" ", "").replace("-", "")
            clean = clean.replace("O", "0").replace("I", "1").replace("L", "1").replace("S", "5")
            
            # Find number sequences (6-20 digits for universal coverage)
            matches = re.findall(r'\d{6,20}', clean)
            numbers.extend(matches)
        
        # Vote for most common number (likely the correct ID)
        number = None
        if numbers:
            counter = Counter(numbers)
            # Take most common, but prefer longer numbers (more likely to be ID)
            sorted_nums = sorted(counter.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
            number = sorted_nums[0][0]
            print(f"  ✅ Document number: {number}")
        
        # === GENERATE FILENAME ===
        if final_name and number:
            return f"{final_name}_{number}.png"
        elif number:
            return f"ID_{number}.png"
        elif final_name:
            return f"{final_name}_scan.png"
            
    except Exception as e:
        print(f"  ⚠️  OCR failed: {e}")
    
    # Fallback
    base = os.path.splitext(os.path.basename(original_path))[0]
    return f"{base}_smart.png"

def expand_box(box, scale):
    """
    Expands the rotated rectangle by a scale factor from its center.
    """
    box = np.array(box, dtype="float32")
    center = np.mean(box, axis=0)
    vectors = box - center
    expanded = center + vectors * scale
    return expanded.astype("int")

def detect_document(img, kernel_size):
    """
    Returns (box, mask) for the largest document found.
    Uses Canny + Morph for better edge response.
    FIXED: Removed aggressive erosion that was cutting off document edges.
    """
    h_small = 800
    ratio = img.shape[0] / float(h_small)
    w_small = int(img.shape[1] / ratio)
    
    small = cv2.resize(img, (w_small, h_small))
    
    # 1. Pad for safety
    pad = 50
    small = cv2.copyMakeBorder(small, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    
    # 2. Contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    
    # 3. Blur
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # 4. Hybrid Segmentation: Gaussian (texture) + Mean (mass)
    # This combination is extremely robust for white paper on gray/dark desks
    thresh_g = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 201, 10)
    thresh_m = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 201, 10)
    mask = cv2.bitwise_and(thresh_g, thresh_m)
    mask = cv2.bitwise_not(mask) # Objects white
    
    k_size = int(kernel_size)
    if k_size % 2 == 0: k_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
    
    # 5. Connect and bridge
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # FIXED: Fill small holes (like punch holes) instead of aggressive erosion
    # This preserves document edges while cleaning up noise
    mask_filled = mask.copy()
    contours_holes, _ = cv2.findContours(cv2.bitwise_not(mask), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours_holes:
        area = cv2.contourArea(c)
        # Fill holes smaller than 5000 pixels (punch holes, stamps, etc.)
        if area < 5000:
            cv2.drawContours(mask_filled, [c], -1, 255, -1)
    mask = mask_filled
    
    # Clean padding in mask
    mask[0:pad, :] = 0
    mask[-pad:, :] = 0
    mask[:, 0:pad] = 0
    mask[:, -pad:] = 0
    
    # 6. Find Contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None, mask
    
    # 7. EXPLICIT FILTER: Only take contours that are 10% to 90% of image area
    total_area = (h_small + 2*pad) * (w_small + 2*pad)
    valid = []
    for c in contours:
        area = cv2.contourArea(c)
        if total_area * 0.10 < area < total_area * 0.95:
            valid.append(c)
            
    if not valid: 
        valid = sorted(contours, key=cv2.contourArea, reverse=True)
        if cv2.contourArea(valid[0]) > total_area * 0.98 and len(valid) > 1:
            valid = valid[1:]
 
    # Sort descending
    valid = sorted(valid, key=cv2.contourArea, reverse=True)
    
    screenCnt = None
    for c in valid[:5]:
        # USE HULL to ensure we don't cut corners of the document
        hull = cv2.convexHull(c)
        peri = cv2.arcLength(hull, True)
        # PRECISION: Lower factor (0.005) follows corners more accurately
        approx = cv2.approxPolyDP(hull, 0.005 * peri, True)
        if len(approx) == 4:
            screenCnt = approx.reshape(4, 2)
            break
            
    if screenCnt is None and valid:
        rect = cv2.minAreaRect(valid[0])
        box = cv2.boxPoints(rect)
        screenCnt = np.array(box, dtype="int")
        
    # Scale back
    screenCnt = (screenCnt - pad) * ratio
    return screenCnt.astype("int"), mask

def smart_crop(input_path, output_path, margin=20, mode="crop", dilation=9, offsets=(0,0,0,0)):
    """
    Smart document cropping with perspective correction and auto-rotation.
    
    Args:
        input_path: Path to input image
        output_path: Path to output (file or directory)
        margin: White margin to add around document (pixels)
        mode: 'crop', 'preview', 'tuning', or 'scan'
        dilation: Kernel size for morphological operations
        offsets: (top, bottom, left, right) additive pixel offsets
    """
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
        
    img = cv2.imread(input_path)
    if img is None:
        print(f"❌ Error: Could not read image: {input_path}")
        sys.exit(1)
    
    print(f"📷 Loaded image: {img.shape[1]}x{img.shape[0]} pixels")
    
    # FIXED: More generous expansion
    scale_factor = 1.0 + (margin / 350.0)

    if mode == "tuning":
        import shutil
        input_name = os.path.basename(input_path)
        base, _ = os.path.splitext(input_name)
        tuning_dir = os.path.join(os.path.dirname(output_path), f"tuning_{base}")
        
        # Clean start
        if os.path.exists(tuning_dir):
            shutil.rmtree(tuning_dir)
        os.makedirs(tuning_dir, exist_ok=True)
        
        print(f"Running Tuning Mode... Output folder: {tuning_dir}")
        kernels = range(1, 101, 2)
        
        for k in kernels:
            box, mask = detect_document(img, k)
            preview = img.copy()
            status = "FAILED"
            
            if box is not None:
                box_expanded = expand_box(box, scale_factor)
                # Explicitly draw lines to ensure closure
                # Draw 4 explicit lines for the polygon
                for i in range(4):
                    cv2.line(preview, tuple(box_expanded[i]), tuple(box_expanded[(i+1)%4]), (0, 255, 255), 60)
                # Draw corners
                for p in box_expanded:
                    cv2.circle(preview, tuple(p), 80, (0, 0, 255), -1)
                status = f"DETECTED k={k}"
                # Debug output to stdout
                print(f"k={k} points: {box_expanded.tolist()}")
            
            # Label on White BG
            label = f"{status} | Margin: {margin}px"
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 4.0, 10)[0]
            tx, ty = 100, 200
            cv2.rectangle(preview, (tx-20, ty-text_size[1]-40), (tx+text_size[0]+20, ty+40), (255, 255, 255), -1)
            cv2.putText(preview, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 4.0, (0, 0, 0), 10)
            
            # Save as JPG to save space
            cv2.imwrite(os.path.join(tuning_dir, f"k{k:02d}_res.jpg"), preview, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            cv2.imwrite(os.path.join(tuning_dir, f"k{k:02d}_mask.jpg"), mask)
            
        print(f"✅ Generated 50 samples in: {tuning_dir}")
        return

    # Standard / Preview Mode
    box, mask = detect_document(img, dilation)
    if box is None:
        print("⚠️  Warning: No document detected. Saving original image.")
        # Ensure output directory exists
        output_is_dir = os.path.isdir(output_path) or output_path.endswith('/')
        output_dir = output_path if output_is_dir else os.path.dirname(output_path)
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        if output_is_dir:
            output_path = os.path.join(output_path, os.path.basename(input_path))
        
        cv2.imwrite(output_path, img)
        print(f"📄 Saved original: {output_path}")
        return

    print(f"✅ Document detected successfully!")
    
    if mode == "preview":
        # Expand for visibility in preview
        box_expanded = expand_box(box, scale_factor)
        preview = img.copy()
        cv2.drawContours(preview, [box_expanded], -1, (0, 255, 0), 20)
        mask_vis = np.zeros_like(img)
        cv2.drawContours(mask_vis, [box_expanded], -1, (255, 255, 255), -1)
        darkened = (img.astype(np.float32) * 0.3).astype(np.uint8)
        preview = np.where(mask_vis == 255, preview, darkened)
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        cv2.imwrite(output_path, preview)
        print(f"👁️  Preview saved: {output_path}")
    else:
        # 1. Extract 4 corners
        pts = box.reshape(4, 2).astype("float32")
        
        # 2. FIXED: More generous expansion (1.04 instead of 1.02)
        # This ensures punch holes and edges are never cut off
        box_standard = expand_box(pts, 1.04)
        rect_std = order_points(box_standard.astype("float32"))
        
        # 3. Calculate ideal rectangle dimensions
        (tl_std, tr_std, br_std, bl_std) = rect_std
        widthA = np.sqrt(((br_std[0] - bl_std[0]) ** 2) + ((br_std[1] - bl_std[1]) ** 2))
        widthB = np.sqrt(((tr_std[0] - tl_std[0]) ** 2) + ((tr_std[1] - tl_std[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr_std[0] - br_std[0]) ** 2) + ((tr_std[1] - br_std[1]) ** 2))
        heightB = np.sqrt(((tl_std[0] - bl_std[0]) ** 2) + ((tl_std[1] - bl_std[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")

        # --- STABLE ORIENTATION DETECTION ---
        # Run OSD on a clean "Standard Crop" buffer
        M_std = cv2.getPerspectiveTransform(rect_std, dst)
        warped_std = cv2.warpPerspective(img, M_std, (maxWidth, maxHeight))
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, warped_std)
        orientation = get_orientation(tmp_path)
        os.unlink(tmp_path)

        # === ORIENTATION-AWARE OFFSET MAPPING ===
        # Map visual offsets (top, bottom, left, right) to geometric offsets based on orientation
        o_t, o_b, o_l, o_r = offsets
        if orientation == 180:
            top_off, bot_off, left_off, right_off = o_b, o_t, o_r, o_l
        elif orientation == 90: # CCW 90 (Geometric Right -> Visual Top)
            top_off, bot_off, left_off, right_off = o_l, o_r, o_b, o_t
        elif orientation == 270: # CW 90 (Geometric Left -> Visual Top)
            top_off, bot_off, left_off, right_off = o_r, o_l, o_t, o_b
        else: # 0
            top_off, bot_off, left_off, right_off = o_t, o_b, o_l, o_r

        # Start with standard rect and apply mapped offsets
        rect = rect_std.copy()
        if any(o != 0 for o in [top_off, bot_off, left_off, right_off]):
            (tl, tr, br, bl) = rect
            # vectors for directions
            v_up = tl - bl
            v_down = bl - tl
            v_l = tl - tr
            v_r = tr - tl
            
            def move_side(p1, p2, vec, pixels):
                if pixels == 0: return p1, p2
                n = vec / np.linalg.norm(vec)
                return p1 + n * pixels, p2 + n * pixels
            
            tl, tr = move_side(tl, tr, v_up, top_off)
            bl, br = move_side(bl, br, v_down, bot_off)
            tl, bl = move_side(tl, bl, v_l, left_off)
            tr, br = move_side(tr, br, v_r, right_off)
            rect = np.array([tl, tr, br, bl], dtype="float32")

        # 3b. RE-CALCULATE ideal rectangle dimensions for final offset rect
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth_f = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight_f = max(int(heightA), int(heightB))
        
        dst_f = np.array([
            [0, 0],
            [maxWidth_f - 1, 0],
            [maxWidth_f - 1, maxHeight_f - 1],
            [0, maxHeight_f - 1]], dtype="float32")

        # Final Perspective Transform
        M = cv2.getPerspectiveTransform(rect, dst_f)
        warped_final = cv2.warpPerspective(img, M, (maxWidth_f, maxHeight_f))
        
        if orientation != 0:
            warped_final = apply_rotation(warped_final, orientation)
 
        # 6. Add white border margin
        if margin > 0:
            warped_final = cv2.copyMakeBorder(warped_final, margin, margin, margin, margin, 
                                              cv2.BORDER_CONSTANT, value=[255, 255, 255])
        
        # 7. Professional scan processing
        if "scan" in mode:
            print("✨ Applying Professional Magic Scan processing...")
            img_float = warped_final.astype(np.float32) / 255.0
            bg = cv2.GaussianBlur(img_float, (101, 101), 0)
            res = cv2.divide(img_float, bg)
            res = (res * 255).clip(0, 255).astype(np.uint8)
            warped_final = cv2.normalize(res, None, 0, 255, cv2.NORM_MINMAX)
            
        # 8. Final Naming Logic
        # Priority: 
        # 1. Exact user output_path (if it's a file)
        # 2. Smart OCR name (if output_path is a directory or empty)
        # 3. Original name + _smart suffix (fallback)
        
        output_is_dir = os.path.isdir(output_path) or output_path.endswith('/') or not output_path
        
        if output_is_dir:
            smart_name = get_smart_filename(warped_final, input_path)
            # If output_path is empty, use CWD
            base_dir = output_path if output_path else "."
            output_path = os.path.join(base_dir, smart_name)
            print(f"💡 Smart Name Suggested: {smart_name}")
        else:
            # User provided a specific filename (e.g. "amir.jpg")
            # If it's just a filename without path, it will be relative to CWD
            pass
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Force PNG extension if not present
        if not output_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            output_path += '.png'
            
        # Try to write with error handling and dynamic parameters
        is_jpg = output_path.lower().endswith(('.jpg', '.jpeg'))
        params = [int(cv2.IMWRITE_JPEG_QUALITY), 95] if is_jpg else [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
        
        success = cv2.imwrite(output_path, warped_final, params)
        if not success:
            print(f"❌ Error: Could not save file to {output_path}")
            sys.exit(1)
                
        print(f"✅ Document Saved: {output_path}")
 
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python smart_crop.py <input> <output> [margin] [mode] [kernel_size] [extra_offsets]")
        sys.exit(1)
        
    in_file = sys.argv[1]
    out_file = sys.argv[2]
    margin_px = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    mode_arg = sys.argv[4] if len(sys.argv) > 4 else "crop"
    kernel_size = int(sys.argv[5]) if len(sys.argv) > 5 else 9
    
    # Offsets: top, bottom, left, right
    offsets = [0, 0, 0, 0]
    if len(sys.argv) > 6:
        # Expected format: "top=50,bottom=20" or just "50" for all
        raw = sys.argv[6]
        if "=" in raw:
            pairs = raw.split(',')
            for p in pairs:
                k, v = p.split('=')
                v = int(v)
                if k == 'top': offsets[0] = v
                elif k == 'bottom': offsets[1] = v
                elif k == 'left': offsets[2] = v
                elif k == 'right': offsets[3] = v
        else:
            v = int(raw)
            offsets = [v, v, v, v]
            
    smart_crop(in_file, out_file, margin_px, mode_arg, kernel_size, tuple(offsets))
