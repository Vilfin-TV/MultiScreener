const fs = require('fs');

const html = fs.readFileSync('C:\\\\Users\\\\Vilfiin\\\\Downloads\\\\Multi Screener\\\\education.html', 'utf8');
const scripts = html.match(/<script>([\s\S]*?)<\/script>/g).map(s => s.replace(/<\/?script>/g, '')).join('\n');

global.document = {
  documentElement: { setAttribute: () => {} },
  getElementById: (id) => {
    return {
      id: id,
      style: { setProperty: (a,b,c) => {} },
      classList: { add: () => {}, remove: () => {} },
      set innerText(v) { this._innerText = v; },
      get innerText() { return this._innerText; },
      set innerHTML(v) { this._innerHTML = v; },
      get innerHTML() { return this._innerHTML; }
    };
  },
  querySelectorAll: () => [],
  createElement: (tag) => {
    return {
      set innerText(v) { this._innerText = v; },
      get innerHTML() { return this._innerText; }, // mocked esc logic
      appendChild: () => {}
    };
  },
  createTextNode: (str) => {
    return { text: str };
  },
  addEventListener: () => {},
  body: {
    appendChild: () => {}
  }
};

global.window = global;
global.clearInterval = () => {};
global.setInterval = () => { return 1; };
global.alert = (msg) => { console.log('ALERT CALLED:', msg); };
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
global._activeJlptLevel = 5;

try {
  eval(scripts);
  console.log("Scripts loaded successfully.");
  openMocTestModal();
  console.log("MOC Test Modal Opened successfully!");
  console.log("Questions generated:", _mocQuestions.length);
  const container = document.getElementById('moc-body-content');
  console.log("Container HTML length:", (container.innerHTML || "").length);
} catch (e) {
  console.error("CRASH:", e);
}
