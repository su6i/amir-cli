const puppeteer = require('puppeteer-core');
const fs = require('fs');
const { marked } = require('marked');

async function renderMarkdown(inputPath, outputPath, fontPath, userDataDir, freeSize) {
    const isFreeSize = freeSize === 'true';
    const rawContent = fs.readFileSync(inputPath, 'utf8');
    const htmlContent = marked(rawContent);
    const fontName = 'B-Nazanin-Local';
    
    // Read and encode font as base64 for reliable loading
    let fontBase64 = '';
    try {
        const fontBuffer = fs.readFileSync(fontPath);
        fontBase64 = fontBuffer.toString('base64');
    } catch (e) {
        console.error(`❌ Could not load font from ${fontPath}`);
    }

    const style = `
        @font-face { 
            font-family: '${fontName}'; 
            src: url('data:font/ttf;base64,${fontBase64}') format('truetype'); 
            font-weight: normal;
            font-style: normal;
        }
        ${!isFreeSize ? `
        @page { 
            size: A4; 
            margin: 20mm; 
        }` : `
        @page {
            margin: 0;
        }
        body {
            margin: 20px !important;
        }
        `}
        body {
            font-family: '${fontName}', "Times New Roman", serif;
            direction: rtl; 
            text-align: right; 
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
            width: 100%; 
            margin: 20px 0; 
            direction: rtl; 
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: right; 
        }
    `;

    const fullHtml = `<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="UTF-8"><style>${style}</style></head><body>${htmlContent}</body></html>`;
    
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
    
    await page.setContent(fullHtml, { waitUntil: 'networkidle0' });
    
    // Smart language detection to fix RTL/LTR and fonts for mixed content
    await page.evaluate((persianFont) => {
        const isEnglish = (text) => {
            const match = text.match(/[A-Za-z\u0600-\u06FF]/);
            if (!match) return false;
            return /[A-Za-z]/.test(match[0]);
        };

        const elements = document.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, th, td, blockquote');
        elements.forEach(el => {
            const text = el.textContent || '';
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

    await page.evaluateHandle('document.fonts.ready');
    
    let pdfOptions = {
        path: outputPath, 
        printBackground: true,
        displayHeaderFooter: false
    };

    if (isFreeSize) {
        // Measure the exact height and width of the content
        const bodyHandle = await page.$('body');
        const boundingBox = await bodyHandle.boundingBox();
        
        // Add a small buffer to prevent cutting off the edges
        const width = Math.ceil(boundingBox.width + 40); 
        const height = Math.ceil(boundingBox.height + 40);
        
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
renderMarkdown(args[0], args[1], args[2], args[3], args[4]).catch(() => process.exit(1));
