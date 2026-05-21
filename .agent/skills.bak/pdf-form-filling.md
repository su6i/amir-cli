---
description: Guide to programmatic PDF form filling using Python (ReportLab + PyPDF + PDFPlumber)
---

# PDF Form Filling Automation

This skill documents the process of programmatically filling non-interactive PDF forms (flat PDFs) by generating a text overlay and merging it with the original document.

## Core Concepts

1.  **Coordinate Discovery**: Inspecting the PDF to find exact X,Y coordinates for text fields.
2.  **Overlay Generation**: Creating a transparent PDF containing only the inserted text/images at the correct positions.
3.  **Merging**: Overlaying the generated data onto the original PDF pages.

## Prerequisites

```bash
uv add reportlab pypdf pdfplumber
```

## 1. Coordinate Discovery (The Hard Part)

Use `pdfplumber` to inspect the PDF and find the coordinates of anchor text (e.g., "Name:", "Date:").

```python
import pdfplumber

def find_coordinates(pdf_path, keyword):
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            # Sort by vertical position (top to bottom)
            words.sort(key=lambda w: w['top'])
            
            for w in words:
                if keyword in w['text']:
                    # PDF coordinates usually start from bottom-left
                    # pdfplumber uses top-left, so conversion might be needed depending on the library
                    # ReportLab uses bottom-left (Cartesian)
                    
                    x = w['x0']
                    y_bottom = page.height - w['bottom'] # Convert to bottom-left origin
                    
                    print(f"Found '{w['text']}' at Page {page_num+1} | X={x:.2f}, Y={y_bottom:.2f}")
```

## 2. Overlay Generation

Use `reportlab` to create the content layer.

```python
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def create_overlay(data):
    packet = io.BytesIO()
    # verify page size matches your target PDF
    c = canvas.Canvas(packet, pagesize=A4) 
    
    # Set Font
    c.setFont("Helvetica", 10)
    
    # Draw Text (X, Y are in points, 1/72 inch, origin bottom-left)
    # Use coordinates found in Step 1, adjusting slightly for alignment
    c.drawString(100, 500, data["name"])
    
    # Draw Checkmarks
    if data["is_married"]:
        c.drawString(200, 450, "X")
        
    # Draw Image (Signature)
    if data["signature_path"]:
        c.drawImage(data["signature_path"], 300, 100, width=100, height=50, mask='auto')
        
    c.save()
    packet.seek(0)
    return packet
```

## 3. Merging

Use `pypdf` to fuse the overlay with the original.

```python
from pypdf import PdfReader, PdfWriter

def merge_pdf(original_path, overlay_packet, output_path):
    original = PdfReader(original_path)
    overlay = PdfReader(overlay_packet)
    writer = PdfWriter()
    
    for i, page in enumerate(original.pages):
        # Merge overlay if it exists for this page
        if i < len(overlay.pages):
            page.merge_page(overlay.pages[i])
        writer.add_page(page)
        
    with open(output_path, "wb") as f:
        writer.write(f)
```

## Best Practices

*   **Data Dictionary**: Keep your data separated from the drawing logic in a dictionary.
*   **Visual Debugging**: Draw a grid or red dots at target coordinates to verify alignment during development.
*   **Font Matching**: Use standard PDF fonts (Helvetica, Times-Roman, Courier) to avoid embedding issues and reduce file size, unless specific branding is required.
*   **Coordinates**: Remember that `ReportLab` uses a bottom-left origin (standard Cartesian), while many extraction tools (and screen readers) might use top-left. Always standardise to bottom-left for generation.
