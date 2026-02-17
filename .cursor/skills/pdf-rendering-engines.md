---
name: pdf-rendering-engines
description: Multi-Engine PDF Rendering Technical Encyclopedia: Headless Browsers (Puppeteer), RTL Optimization, Base64 Font Embedding, and Robust Fallback logic.
---

# Skill: Multi-Engine PDF Rendering (Technical Encyclopedia)

Comprehensive technical protocols for generating high-fidelity PDF documents from Markdown, HTML, and images using heterogeneous rendering engines in the 2026 ecosystem.

## 1. Headless Browser Orchestration (Puppeteer)
Targeting maximum fidelity for modern web standards (D3.js, Flexbox, Grid).

### 1.1 Base64 Font Embedding Protocol
*   **The Security Constraint:** Headless browsers often block local file access (`file://`) for security reasons when rendering external content.
*   **The Resolution:** Mandatory use of Base64 Data URIs for font loading.
    ```javascript
    const fontBuffer = fs.readFileSync(fontPath);
    const fontBase64 = fontBuffer.toString('base64');
    const style = `@font-face { font-family: 'LocalFont'; src: url('data:font/ttf;base64,${fontBase64}') format('truetype'); }`;
    ```
*   **A4 PDF Print Settings:**
    ```javascript
    await page.pdf({ 
        format: 'A4', 
        printBackground: true,
        preferCSSPageSize: true
    });
    ```

### 1.2 RTL & Persian Typography Standards
*   **Directionality:** Explicit use of `direction: rtl` and `text-align: right` in the body/container.
*   **Break Prevention:** Mandatory use of `page-break-inside: avoid` for tables, headers, and images to prevent mid-element pagination cuts.

## 2. Robust Fallback Pipeline (PIL)
Ensuring content survival when advanced rendering engines fail.

### 2.1 Infinite Pagination Logic
*   **Strategy:** Vertically tile text blocks into long strips and then split into A4-sized segments.
*   **Indexing:** Pages must be saved with a standard index suffix (e.g., `_page_0.png`) to allow easy globbing and re-assembly.

## 3. Storage & Performance Optimization
### 3.1 External Disk Redirection
*   **Logic:** When the root filesystem capacity is > 95%, redirect all temporary operations to external high-speed storage.
*   **Implementation:** Export `TMPDIR`, `UV_CACHE_DIR`, and `MAGICK_TEMPORARY_PATH` to the external mount point.

### 3.2 macOS Finder Metadata Refresh
*   **Problem:** Finder's "Date Added" does not refresh on simple file overwrites.
*   **Solution:** Mandatory use of `touch [output_file]` after generation to force a metadata refresh and move the file to the top of the "Recently Added" view.

---
*Updated: 2026-02-17 - Added Multi-Engine protocols and RTL Base64 font embedding.*
