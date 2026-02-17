const puppeteer = require('puppeteer-core');
const fs = require('fs');
const { marked } = require('marked');

async function renderMarkdown(inputPath, outputPath, fontPath, userDataDir) {
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
        @page { 
            size: A4; 
            margin: 20mm; 
        }
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
    await page.evaluateHandle('document.fonts.ready');
    
    await page.pdf({ 
        path: outputPath, 
        format: 'A4', 
        printBackground: true,
        displayHeaderFooter: false,
        preferCSSPageSize: true
    });
    
    await browser.close();
}

const args = process.argv.slice(2);
renderMarkdown(args[0], args[1], args[2], args[3]).catch(() => process.exit(1));
