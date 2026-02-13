// ==UserScript==
// @name         AI Studio Audio Downloader 🎙️💾
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Adds a premium download button to Google AI Studio TTS page.
// @author       Antigravity (Amir CLI)
// @match        https://aistudio.google.com/generate-speech*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=google.com
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const STYLE = `
        .amir-download-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background-color: #1a73e8;
            color: white;
            border: none;
            border-radius: 20px;
            padding: 6px 16px;
            margin-left: 12px;
            font-family: 'Google Sans', Roboto, sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.2s, box-shadow 0.2s, transform 0.1s;
            box-shadow: 0 1px 3px rgba(60,64,67,0.3);
            z-index: 1000;
        }

        .amir-download-btn:hover {
            background-color: #1557b1;
            box-shadow: 0 1px 3px 1px rgba(60,64,67,0.15);
        }

        .amir-download-btn:active {
            transform: scale(0.98);
        }

        .amir-download-btn svg {
            margin-right: 8px;
            fill: currentColor;
        }

        .amir-pulse {
            animation: amir-pulse-animation 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        @keyframes amir-pulse-animation {
            0%, 100% { opacity: 1; }
            50% { opacity: .7; }
        }
    `;

    const DOWNLOAD_ICON = `<svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 0 24 24" width="20"><path d="M0 0h24v24H0V0z" fill="none"/><path d="M19 9h-4V3H9v6H5l7 7 7-7zm-8 2V5h2v6h1.17L12 13.17 9.83 11H11zm-6 7h14v2H5z"/></svg>`;

    function injectStyles() {
        const styleEl = document.createElement('style');
        styleEl.textContent = STYLE;
        document.head.append(styleEl);
    }

    function createButton() {
        const btn = document.createElement('button');
        btn.className = 'amir-download-btn amir-pulse';
        btn.innerHTML = `${DOWNLOAD_ICON} <span>Download Audio</span>`;
        btn.onclick = handleDownload;
        return btn;
    }

    function handleDownload(e) {
        e.preventDefault();
        const player = document.querySelector('video') || document.querySelector('audio');
        if (player && player.src) {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            const fileName = `gemini-speech-${timestamp}.wav`;
            
            const a = document.createElement('a');
            a.href = player.src;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            // Visual feedback
            const span = this.querySelector('span');
            const originalText = span.textContent;
            span.textContent = 'Saving...';
            this.style.backgroundColor = '#1e8e3e';
            setTimeout(() => {
                span.textContent = originalText;
                this.style.backgroundColor = '';
            }, 2000);
        } else {
            alert('No audio generated yet!');
        }
    }

    function init() {
        if (document.querySelector('.amir-download-btn')) return;

        const observer = new MutationObserver((mutations) => {
            const container = document.querySelector('.speech-prompt-footer-actions-player');
            if (container && !container.querySelector('.amir-download-btn')) {
                const player = container.querySelector('audio, video');
                if (player) {
                    injectStyles();
                    container.appendChild(createButton());
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // Run on load
    console.log('🎙️ AI Studio Audio Downloader loaded...');
    init();

})();
