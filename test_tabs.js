const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const html = fs.readFileSync('education.html', 'utf8');

const dom = new JSDOM(html, { runScripts: "dangerously" });
const window = dom.window;
const document = window.document;

function assertDisplay(id, expected) {
    const el = document.getElementById(id);
    if (!el) {
        console.log(`ERROR: Element ${id} not found`);
        return false;
    }
    const display = window.getComputedStyle(el).display || el.style.display;
    if (display !== expected) {
        console.log(`ERROR: Element ${id} display is '${display}', expected '${expected}'`);
        return false;
    }
    return true;
}

try {
    // 1. Initial State
    console.log("Testing initial state...");
    // Should be in kana layout or whatever is default, but let's just trigger clicks.

    // 2. Click Hiragana & Katakana Hub
    console.log("Clicking Hiragana & Katakana Hub...");
    window.switchJpSubHub('chart');
    assertDisplay('jp-kana-section', 'grid');
    assertDisplay('jp-kanji-casual-section', 'none');
    assertDisplay('jp-levels-section', 'none');
    assertDisplay('jp-dict-section', 'none');

    // 3. Click Kanji & Casual Japanese
    console.log("Clicking Kanji & Casual Japanese...");
    window.switchJpSubHub('kanji');
    assertDisplay('jp-kana-section', 'none');
    assertDisplay('jp-kanji-casual-section', 'grid');
    assertDisplay('jp-levels-section', 'none');
    assertDisplay('jp-dict-section', 'none');

    // 4. Click JLPT Exam Center
    console.log("Clicking JLPT Exam Center...");
    window.switchJpSubHub('levels');
    assertDisplay('jp-kana-section', 'none');
    assertDisplay('jp-kanji-casual-section', 'none');
    assertDisplay('jp-levels-section', 'block');
    assertDisplay('jp-dict-section', 'none');

    // 5. Click Dictionary
    console.log("Clicking Dictionary...");
    window.switchJpSubHub('dict');
    assertDisplay('jp-kana-section', 'none');
    assertDisplay('jp-kanji-casual-section', 'none');
    assertDisplay('jp-levels-section', 'none');
    assertDisplay('jp-dict-section', 'block');

    console.log("ALL TABS PASSED SUCCESSFULLY!");
} catch (e) {
    console.error("Test failed with exception:", e);
}
