const fs = require('fs');

const html = fs.readFileSync('C:\\\\Users\\\\Vilfiin\\\\Downloads\\\\Multi Screener\\\\education.html', 'utf8');

// Parse out JLPT_DATA, openMocTestModal, renderMocQuestions, updateMocTimerDisplay, esc
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/g);
let fullScript = "";
if (scriptMatch) {
  fullScript = scriptMatch.map(s => s.replace(/<\/?script>/g, '')).join('\n');
}

// Mock DOM
global.document = {
  documentElement: {
    setAttribute: () => {}
  },
  getElementById: (id) => {
    return {
      innerText: '',
      innerHTML: '',
      style: {},
      classList: {
        add: () => {},
        remove: () => {}
      },
      textContent: ''
    };
  },
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => {
    return {
      set innerText(val) { this._innerText = val; },
      get innerHTML() { return this._innerText; }
    };
  }
};
  addEventListener: () => {},
  createElement: () => {
    return {
      set innerText(val) { this._innerText = val; },
      get innerHTML() { return this._innerText; }
    };
  }
};

global.window = global;
global.clearInterval = () => {};
global.setInterval = () => {};
global.alert = console.log;
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };

// Expose variables
global._activeJlptLevel = 5;

try {
  eval(fullScript);
  console.log("Functions loaded.");
  
  openMocTestModal();
  console.log('MOC Test opened successfully!');
  console.log('Questions rendered:', _mocQuestions.length);
} catch (e) {
  console.error("Error evaluating:", e.message);
  console.error(e.stack);
}
