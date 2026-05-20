const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

async function renderMarkdown(inputPath, outputPath, fontPath, userDataDir, freeSize, pageWidthArg, pageHeightArg, themeArg) {
    const isFreeSize = freeSize === 'true';
    const hasCustomWidth = typeof pageWidthArg === 'string' && pageWidthArg.trim() !== '';
    const hasCustomHeight = typeof pageHeightArg === 'string' && pageHeightArg.trim() !== '';
    const rawContent = fs.readFileSync(inputPath, 'utf8');
    const htmlContent = marked(rawContent);
    const fontName = 'B-Nazanin-Local';

    // Smart Document Language Detection
    const faMatch = rawContent.match(/[\u0600-\u06FF]/g);
    const enMatch = rawContent.match(/[A-Za-z]/g);
    const faCount = faMatch ? faMatch.length : 0;
    const enCount = enMatch ? enMatch.length : 0;
    const isLtrPrimary = enCount > faCount;
    
    const docDir = isLtrPrimary ? 'ltr' : 'rtl';
    const docAlign = isLtrPrimary ? 'left' : 'right';
    const docLang = isLtrPrimary ? 'en' : 'fa';
    const docFont = isLtrPrimary ? '"Times New Roman", \'' + fontName + '\', serif' : '\'' + fontName + '\', "Times New Roman", serif';

    const parsePixels = (value) => {
        if (!value) {
            return null;
        }
        const cleaned = String(value).trim();
        const match = cleaned.match(/^([0-9]+(?:\.[0-9]+)?)\s*(px)?$/i);
        if (!match) {
            return null;
        }
        return Math.ceil(Number(match[1]));
    };

    const customWidthPx = parsePixels(pageWidthArg);
    const customHeightPx = parsePixels(pageHeightArg);
    const pageWidthMode = !customWidthPx && hasCustomWidth
        ? String(pageWidthArg).trim().toLowerCase()
        : '';
    const useMaxContentWidth = pageWidthMode === 'max-content';
    const useFitContentWidth = pageWidthMode === 'fit-content';
    const useNoWrap = pageWidthMode === 'nowrap';
    const enforceNoWrapCells = useNoWrap || Boolean(customWidthPx);
    const tableWidthCss = customWidthPx
        ? `${customWidthPx}px`
        : useMaxContentWidth
            ? 'max-content'
            : useFitContentWidth
                ? 'fit-content'
                : '100%';
    const tableMinWidthCss = customWidthPx ? `${customWidthPx}px` : '100%';
    const bodyWidthCss = customWidthPx ? `${customWidthPx}px` : 'auto';
    
    // Read and encode font as base64 for reliable loading
    let fontBase64 = '';
    try {
        const fontBuffer = fs.readFileSync(fontPath);
        fontBase64 = fontBuffer.toString('base64');
    } catch (e) {
        console.error(`❌ Could not load font from ${fontPath}`);
    }


    // ── Theme support ──────────────────────────────────────────
    let themeCSS = '';
    const isCarouselTheme = themeArg && themeArg.trim() === 'carousel';
    if (themeArg && themeArg.trim() !== '') {
        const themePath = path.join(__dirname, '..', 'themes', themeArg.trim() + '.css');
        if (fs.existsSync(themePath)) {
            themeCSS = fs.readFileSync(themePath, 'utf8');
        } else {
            console.error(`⚠️  Theme not found: ${themePath}`);
        }
    }
    // Carousel: inject fixed square page size + reset base renderer styles
    if (isCarouselTheme) {
        themeCSS = `@page { size: 1080px 1080px; margin: 0; }
body {
    padding: 0 !important;
    margin: 0 !important;
    width: 1080px !important;
    max-width: 1080px !important;
    background: #0a0a0f !important;
    font-size: 15px !important;
    line-height: 1.5 !important;
}
h1, h2, h3 {
    font-family: 'Inter', -apple-system, sans-serif !important;
    border-bottom: none !important;
    padding-bottom: 0 !important;
}
` + themeCSS;
    }

    const style = `
        * {
            box-sizing: border-box;
        }
        @font-face { 
            font-family: '${fontName}'; 
            src: url('data:font/ttf;base64,${fontBase64}') format('truetype'); 
            font-weight: normal;
            font-style: normal;
        }
        ${(!isFreeSize && !hasCustomWidth && !hasCustomHeight && !isCarouselTheme) ? `
        @page { 
            size: A4; 
            margin: 20mm; 
        }` : `
        @page {
            margin: 0;
        }
        body {
            margin: 0 !important;
        }
        `}
        body {
            font-family: ${docFont};
            direction: ${docDir}; 
            text-align: ${docAlign}; 
            width: ${bodyWidthCss};
            padding: 20px; 
            font-size: 18px; 
            line-height: 1.6;
            background: white;
            -webkit-font-smoothing: antialiased;
        }
        h1, h2, h3, table, img {
            page-break-inside: avoid;
            break-inside: avoid;
        }
        h1, h2, h3 { 
            font-family: '${fontName}', serif;
            border-bottom: 2px solid #EEE; 
            padding-bottom: 10px; 
            page-break-after: avoid; 
        }
        table { 
            border-collapse: collapse; 
            width: ${tableWidthCss}; 
            min-width: ${tableMinWidthCss};
            ${useMaxContentWidth ? 'display: inline-table;' : ''}
            ${useFitContentWidth ? 'display: inline-table;' : ''}
            margin: 20px 0; 
            direction: ${docDir}; 
            table-layout: auto;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: ${docAlign}; 
            ${enforceNoWrapCells ? 'white-space: nowrap;' : ''}
        }
        pre {
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            direction: ltr !important;
            text-align: left !important;
            font-family: "Courier New", Courier, monospace !important;
        }
        code {
            direction: ltr !important;
            font-family: "Courier New", Courier, monospace !important;
            background: #f4f4f4; 
            padding: 2px 5px; 
            border-radius: 3px;
        }
    ${themeCSS}
    `;

    const fullHtml = `<!DOCTYPE html><html dir="${docDir}" lang="${docLang}"><head><meta charset="UTF-8"><style>${style}</style></head><body>${htmlContent}</body></html>`;
    
    const chromePaths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        '/usr/bin/google-chrome'
    ];
    let executablePath = chromePaths.find(p => fs.existsSync(p));
    
    if (!executablePath) {
        process.exit(1);
    }

    const launchArgs = ['--no-sandbox', '--disable-setuid-sandbox'];
    if (userDataDir) {
        launchArgs.push(`--user-data-dir=${userDataDir}`);
    }

    const browser = await puppeteer.launch({ executablePath, args: launchArgs });
    const page = await browser.newPage();

    if (isCarouselTheme) {
        await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 1 });
    } else if (customWidthPx) {
        await page.setViewport({ width: customWidthPx, height: customHeightPx || 2000, deviceScaleFactor: 1 });
    }

    // For carousel: wrap body content in a 1080px container to prevent overflow
    const htmlToLoad = isCarouselTheme
        ? fullHtml.replace('<body>', '<body><div id="carousel-root" style="width:1080px;max-width:1080px;overflow:hidden;margin:0;padding:0;">')
                  .replace('</body>', '</div></body>')
        : fullHtml;

    await page.setContent(htmlToLoad, { waitUntil: 'networkidle0' });
    
    // Fallback detection logic if mixed languages exist within tags
    await page.evaluate((persianFont) => {
        const isEnglish = (text) => {
            const match = text.match(/[A-Za-z\u0600-\u06FF]/);
            if (!match) return false;
            return /[A-Za-z]/.test(match[0]);
        };

        const elements = document.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, th, td, blockquote');
        elements.forEach(el => {
            const text = el.textContent || '';
            // Only force LTR if the element explicitly starts with English, even in FA doc
            if (isEnglish(text)) {
                el.setAttribute('dir', 'ltr');
                el.style.textAlign = 'left';
                el.style.fontFamily = `"Times New Roman", '${persianFont}', serif`;
            }
        });
        
        // Align list containers based on their first item to fix bullet placement
        document.querySelectorAll('ul, ol').forEach(list => {
            const firstItem = list.querySelector('li');
            if (firstItem && firstItem.getAttribute('dir') === 'ltr') {
                list.setAttribute('dir', 'ltr');
            }
        });
    }, fontName);

    // ── Carousel: fix emoji visibility in gradient headings ────
    if (isCarouselTheme) {
        await page.evaluate(() => {
            const emojiRegex = /(\p{Emoji_Presentation}|\p{Extended_Pictographic})/gu;
            document.querySelectorAll('h1, h2, h3').forEach(el => {
                if (!emojiRegex.test(el.textContent)) return;
                emojiRegex.lastIndex = 0;
                el.innerHTML = el.innerHTML.replace(emojiRegex, (match) => {
                    return `<span style="
                        background: none !important;
                        -webkit-background-clip: unset !important;
                        -webkit-text-fill-color: unset !important;
                        color: unset !important;
                        font-style: normal;
                    ">${match}</span>`;
                });
            });
        });

        // Wrap each slide's content (h2 + siblings until next h2) in a .slide div for vertical centering
        await page.evaluate(() => {
            const root = document.getElementById('carousel-root');
            if (!root) return;
            const allElements = Array.from(root.children);
            const groups = [[]];
            allElements.forEach(el => {
                if (el.tagName === 'H2') groups.push([el]);
                else groups[groups.length - 1].push(el);
            });
            root.innerHTML = '';
            groups.forEach((group, i) => {
                if (!group.length) return;
                const div = document.createElement('div');
                div.className = i === 0 ? 'slide slide-cover' : 'slide';
                group.forEach(el => div.appendChild(el));
                root.appendChild(div);
            });
        });

        // Force layout via addStyleTag (highest reliability in Puppeteer)
        await page.addStyleTag({ content: `
            html { margin: 0 !important; padding: 0 !important; }
            body { margin: 0 !important; padding: 0 !important; width: 1080px !important; max-width: 1080px !important; overflow: hidden !important; }
            #carousel-root { width: 1080px !important; max-width: 1080px !important; overflow: visible !important; }
            .slide { width: 1080px !important; height: 1080px !important; display: flex !important; flex-direction: column !important; justify-content: center !important; overflow: hidden !important; page-break-before: always !important; break-before: page !important; page-break-inside: avoid !important; break-inside: avoid !important; box-sizing: border-box !important; }
            .slide-cover { page-break-before: avoid !important; break-before: avoid !important; }
            table { width: 976px !important; max-width: 976px !important; min-width: 0 !important; margin-left: 52px !important; margin-right: 52px !important; table-layout: fixed !important; border-collapse: collapse !important; }
            th:nth-child(1), td:nth-child(1) { width: 48px !important; text-align: center !important; }
            th:nth-child(2), td:nth-child(2) { width: 390px !important; white-space: normal !important; }
            th:nth-child(3), td:nth-child(3) { width: 95px !important; text-align: right !important; }
            th:nth-child(4), td:nth-child(4) { width: 245px !important; text-align: center !important; }
            th:nth-child(5), td:nth-child(5) { width: 198px !important; text-align: center !important; white-space: nowrap !important; }
        `});
    }

    await page.evaluateHandle('document.fonts.ready');
    
    let pdfOptions = {
        path: outputPath, 
        printBackground: true,
        displayHeaderFooter: false
    };

    if (!isFreeSize && !hasCustomWidth && !hasCustomHeight) {
        pdfOptions.displayHeaderFooter = true;
        pdfOptions.headerTemplate = '<span></span>';
        pdfOptions.footerTemplate = '<div style="font-size: 11px; width: 100%; text-align: center; font-family: sans-serif; color: rgba(0,0,0,0.6); margin-bottom: 5px;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>';
    }

    if (isCarouselTheme) {
        // Carousel: let @page { size: 1080px 1080px } from theme CSS control the page size
        pdfOptions = {
            ...pdfOptions,
            preferCSSPageSize: true,
            printBackground: true,
        };
    } else if (isFreeSize || hasCustomWidth || hasCustomHeight) {
        // padding buffer slightly increased to account for exact clipping
        const contentWidth = await page.evaluate(() => Math.ceil(Math.max(
            document.documentElement.scrollWidth,
            document.body.scrollWidth,
            document.body.offsetWidth,
            document.documentElement.offsetWidth
        )));
        const bodyHandle = await page.$('body');
        const boundingBox = await bodyHandle.boundingBox();
        
        // Ensure minimum required width is passed (no clipping)
        const minReqWidth = Math.max(contentWidth, Math.ceil(boundingBox.width));
        
        // For custom widths, we just use the custom width. But if the actual content overflows,
        // box-sizing: border-box helps prevent it. Add 10px buffer anyway.
        const width = customWidthPx || (useMaxContentWidth || useFitContentWidth || useNoWrap ? minReqWidth + 40 : minReqWidth + 40);
        const height = customHeightPx || Math.ceil(boundingBox.height + 40);
        
        pdfOptions = {
            ...pdfOptions,
            width: `${width}px`,
            height: `${height}px`,
            preferCSSPageSize: false
        };
        await bodyHandle.dispose();
    } else {
        pdfOptions = {
            ...pdfOptions,
            format: 'A4',
            preferCSSPageSize: true
        };
    }

    await page.pdf(pdfOptions);
    await browser.close();
}

const args = process.argv.slice(2);
renderMarkdown(args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7]).catch((err) => { console.error(err); process.exit(1); });
