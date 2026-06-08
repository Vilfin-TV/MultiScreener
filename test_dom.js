const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const html = fs.readFileSync('education.html', 'utf8');

const dom = new JSDOM(html, { runScripts: "dangerously" });
console.log("No initial JS runtime errors!");
