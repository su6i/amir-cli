// WO-amir-cli-0012 item 1 D4, no network, run via `node tests/test_pdf_rtl.js`

const path = require('path');
const assert = require('assert');

const { hasPersianChar, isEnglishText } = require(
  path.join(__dirname, '..', 'lib', 'nodejs', 'render_puppeteer.js')
);

let passed = 0;
let failed = 0;

function runTest(description, fn) {
  try {
    fn();
    console.log(`OK: ${description}`);
    passed++;
  } catch (err) {
    console.error(`FAIL: ${description} - ${err.message}`);
    failed++;
  }
}

// Required test table for isEnglishText
runTest('isEnglishText: Pure Latin "Hello world" -> true', () => {
  assert.strictEqual(isEnglishText('Hello world'), true);
});

runTest('isEnglishText: Pure Persian "سلام دنیا" -> false', () => {
  assert.strictEqual(isEnglishText('سلام دنیا'), false);
});

runTest('isEnglishText: Latin sentence containing one Persian word, Latin-leading "Hello سلام world" -> false', () => {
  assert.strictEqual(isEnglishText('Hello سلام world'), false);
});

runTest('isEnglishText: Persian sentence containing one Latin word, Persian-leading "سلام Hello دنیا" -> false', () => {
  assert.strictEqual(isEnglishText('سلام Hello دنیا'), false);
});

runTest('isEnglishText: Numbers and punctuation only "123 !?" -> false', () => {
  assert.strictEqual(isEnglishText('123 !?'), false);
});

runTest('isEnglishText: Empty string "" -> false', () => {
  assert.strictEqual(isEnglishText(''), false);
});

// Direct checks for hasPersianChar
runTest('hasPersianChar: Mixed text "Hello سلام world" -> true', () => {
  assert.strictEqual(hasPersianChar('Hello سلام world'), true);
});

runTest('hasPersianChar: Pure Latin "Hello world" -> false', () => {
  assert.strictEqual(hasPersianChar('Hello world'), false);
});

console.log(`\nResults: ${passed} passed, ${failed} failed, ${passed + failed} total`);

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
