#!/usr/bin/env node
/**
 * Pre-commit validation:
 *  - JSON fence stripping logic
 *  - jsonToTabText for HDFC Bank (Stock), HDFC Flexi Cap (MF), Niftybees (ETF)
 */

'use strict';

// ── Reproduce stripMarkdownFences ──────────────────────────────────────────────
function stripMarkdownFences(text) {
  if (!text) return text;
  let t = text.trim();
  t = t.replace(/^```(?:json|html|javascript|js|text|markdown)?\s*/i, '');
  t = t.replace(/\s*```\s*$/, '');
  t = t.replace(/^```(?:json|html|javascript|js|text|markdown)?\s*/gim, '');
  t = t.replace(/```\s*$/gim, '');
  return t.trim();
}

// ── Reproduce extractFromCodeBlock ────────────────────────────────────────────
function extractFromCodeBlock(text) {
  if (!text) return null;
  const jsonMatchClosed = text.match(/```json\s*([\s\S]*?)```/i);
  if (jsonMatchClosed) return { content: jsonMatchClosed[1].trim(), type: 'json' };
  const htmlMatchClosed = text.match(/```html\s*([\s\S]*?)```/i);
  if (htmlMatchClosed) return { content: htmlMatchClosed[1].trim(), type: 'html' };
  const anyMatchClosed = text.match(/```\w*\s*([\s\S]*?)```/i);
  if (anyMatchClosed) return { content: anyMatchClosed[1].trim(), type: 'unknown' };
  const jsonMatchOpen = text.match(/```json\s*([\s\S]+)/i);
  if (jsonMatchOpen) {
    const inner = jsonMatchOpen[1].trim();
    if (inner.startsWith('{') || inner.startsWith('[')) return { content: inner, type: 'json' };
  }
  const htmlMatchOpen = text.match(/```html\s*([\s\S]+)/i);
  if (htmlMatchOpen) return { content: htmlMatchOpen[1].trim(), type: 'html' };
  const stripped = stripMarkdownFences(text);
  if ((stripped.startsWith('{') || stripped.startsWith('[')) && stripped.length > 10) {
    return { content: stripped, type: 'json' };
  }
  return null;
}

// ── Reproduce jsonToTabText ────────────────────────────────────────────────────
function jsonToTabText(obj) {
  if (!obj || !Array.isArray(obj.tabs)) return null;
  let out = '';
  obj.tabs.forEach(tab => {
    out += `\n## TAB ${tab.id || ''}: ${tab.name || 'Tab'}\n`;
    if (tab.fields && typeof tab.fields === 'object') {
      Object.entries(tab.fields).forEach(([k, v]) => { out += `${k}: ${v}\n`; });
    }
    if (Array.isArray(tab.subsections)) {
      tab.subsections.forEach(sub => {
        if (sub.title) out += `### ${sub.title}\n`;
        if (sub.fields && typeof sub.fields === 'object') {
          Object.entries(sub.fields).forEach(([k, v]) => { out += `${k}: ${v}\n`; });
        }
      });
    }
  });
  return out.trim();
}

// ── Test fixtures ──────────────────────────────────────────────────────────────

const hdfcBankJSON = {
  tabs: [
    { id: '01', name: 'Company Overview', fields: { 'Full Name': 'HDFC Bank Ltd', 'Sector': 'Banking', 'Exchange': 'NSE / BSE' } },
    { id: '02', name: 'Live Market Data', fields: { 'CMP': '₹1,710', 'Market Cap': '₹13.1L Cr' } },
    { id: '03', name: 'Valuation & Fundamentals', fields: { 'P/E': '18.4', 'EPS': '₹92.8', 'ROE': '17.2%' } },
    { id: '04', name: 'Technicals', subsections: [
      { title: 'Trend', fields: { 'Trend': 'Bullish', '20 DMA': '₹1,695' } },
      { title: 'Oscillators', fields: { 'RSI (14)': '58.4', 'MACD': 'Positive crossover' } }
    ]},
    { id: '05', name: 'Financials', subsections: [
      { title: 'Income', fields: { 'Revenue (FY24)': '₹2,40,000 Cr', 'PAT': '₹60,812 Cr' } }
    ]},
    { id: '06', name: 'Ownership & Corporate', fields: { 'FII': '47.2%', 'DII': '22.1%' } },
    { id: '07', name: 'Recent News & Events', fields: { 'Q4 FY24': 'PAT +37% YoY' } },
    { id: '08', name: 'Analyst Ratings', fields: { 'Consensus': 'Strong Buy', 'Target': '₹1,980' } },
    { id: '09', name: 'Tax Compliance', fields: { 'STCG': '20%', 'LTCG': '12.5% above ₹1.25L' } },
    { id: '10', name: 'Final Verdict', fields: { 'View': 'Accumulate', 'Risk': 'Medium' } }
  ]
};

const hdfcMFJSON = {
  tabs: [
    { id: '01', name: 'Fund Overview', fields: { 'Fund House': 'HDFC AMC', 'Category': 'Flexi Cap', 'AUM': '₹62,000 Cr' } },
    { id: '02', name: 'Live NAV & Returns', fields: { 'NAV': '₹1,842.50', '1Y Return': '+38.2%', '3Y CAGR': '+24.1%' } },
    { id: '03', name: 'Portfolio & Holdings', fields: { 'Top 5': 'HDFC Bank, ICICI Bank, Infosys', 'Equity %': '96.2%' } },
    { id: '04', name: 'Risk Metrics', fields: { 'Beta': '0.92', 'Sharpe': '1.38', 'Std Dev': '14.2%' } },
    { id: '05', name: 'Cost & Benchmarks', fields: { 'Expense Ratio': '0.78%', 'Benchmark': 'NIFTY 500 TRI' } },
    { id: '06', name: 'Ownership & Corporate', fields: { 'Remark': 'N/A for Mutual Funds' } },
    { id: '07', name: 'Recent News', fields: { 'Update': 'Category outperformed benchmark by 6% in FY24' } },
    { id: '08', name: 'Analyst Ratings', fields: { 'Rating': '5 Star (ValueResearch)', 'Rank': '#2 in Flexi Cap' } },
    { id: '09', name: 'Tax Compliance', fields: { 'STCG': '20%', 'LTCG': '12.5% above ₹1.25L', 'SIP Tax': 'Each SIP has own clock' } },
    { id: '10', name: 'Final Verdict', fields: { 'View': 'Hold / SIP Continue', 'Risk': 'Moderate-High' } }
  ]
};

const niftybeeJSON = {
  tabs: [
    { id: '01', name: 'ETF Overview', fields: { 'Full Name': 'Nippon India ETF Nifty BeES', 'Underlying': 'Nifty 50 TRI' } },
    { id: '02', name: 'Live Market Data', fields: { 'CMP': '₹252.80', 'iNAV Gap': '-0.12%', 'AUM': '₹28,000 Cr' } },
    { id: '03', name: 'Valuation', fields: { 'Tracking Error': '0.03%', 'Expense Ratio': '0.04%', 'P/E': '22.1' } },
    { id: '04', name: 'Technicals', subsections: [
      { title: 'Trend', fields: { 'Trend': 'Sideways-to-Bullish', '50 DMA': '₹249.10', '200 DMA': '₹235.60' } }
    ]},
    { id: '05', name: 'Holdings', fields: { 'Top 5': 'HDFC Bank, Reliance, Infosys, ICICI, TCS' } },
    { id: '06', name: 'Ownership', fields: { 'Note': 'ETF — no promoter structure.' } },
    { id: '07', name: 'News & Events', fields: { 'Upcoming': 'Nifty 50 rebalancing June 2024' } },
    { id: '08', name: 'Analyst View', fields: { 'View': 'Neutral / Index-track' } },
    { id: '09', name: 'Tax Compliance', fields: { 'STCG': '20%', 'LTCG': '12.5% above ₹1.25L', 'Type': 'Equity ETF' } },
    { id: '10', name: 'Final Verdict', fields: { 'View': 'Core portfolio holding', 'Risk': 'Low (index fund)' } }
  ]
};

let allPassed = true;

// ── Test A: Fence stripping ────────────────────────────────────────────────────
console.log('\n═══ TEST A: Markdown Fence Stripping ═══');

const fenceTests = [
  { label: 'Closed fence (normal)',     input: '```json\n{"tabs":[]}\n```' },
  { label: 'Open fence (truncated)',    input: '```json\n{"tabs":[]}' },
  { label: 'Leading whitespace',        input: '   ```json\n{"tabs":[]}\n```  ' },
  { label: 'No fence (bare JSON)',      input: '{"tabs":[]}' },
  { label: 'Double-wrapped fences',     input: '```json\n```json\n{"tabs":[]}\n```\n```' },
];

fenceTests.forEach(({ label, input }) => {
  const stripped = stripMarkdownFences(input);
  let pass = false;
  try { JSON.parse(stripped); pass = true; } catch (e) {}
  console.log(`  ${pass ? '✅' : '❌'} ${label} → "${stripped.slice(0, 40)}"`);
  if (!pass) allPassed = false;
});

// ── Test B: extractFromCodeBlock ──────────────────────────────────────────────
console.log('\n═══ TEST B: extractFromCodeBlock ═══');

const blockTests = [
  { label: 'Closed ```json block',    input: '```json\n{"tabs":[{"id":"01","name":"Test","fields":{}}]}\n```' },
  { label: 'Open ```json (no close)', input: '```json\n{"tabs":[{"id":"01","name":"Test","fields":{}}]}' },
  { label: 'Bare JSON (no fences)',   input: '{"tabs":[{"id":"01","name":"Test","fields":{}}]}' },
  { label: 'Text before JSON block',  input: 'Here is the data:\n```json\n{"tabs":[{"id":"01","name":"Test","fields":{}}]}\n```\nDone.' },
];

blockTests.forEach(({ label, input }) => {
  const extracted = extractFromCodeBlock(input);
  let pass = false;
  if (extracted && (extracted.type === 'json' || extracted.type === 'unknown')) {
    try { JSON.parse(extracted.content); pass = true; } catch (e) {}
  }
  console.log(`  ${pass ? '✅' : '❌'} ${label} → type: ${extracted ? extracted.type : 'null'}`);
  if (!pass) allPassed = false;
});

// ── Test C: jsonToTabText for all three asset types ───────────────────────────
console.log('\n═══ TEST C: jsonToTabText Tab Mapping ═══');

const fixtures = [
  { name: 'HDFC Bank (Stock)', json: hdfcBankJSON },
  { name: 'HDFC Flexi Cap Direct Growth (MF)', json: hdfcMFJSON },
  { name: 'Niftybees (ETF)', json: niftybeeJSON },
];

fixtures.forEach(({ name, json }) => {
  const result = jsonToTabText(json);
  if (!result) {
    console.log(`  ❌ ${name}: jsonToTabText returned null`);
    allPassed = false;
    return;
  }

  const tabCount    = (result.match(/^## TAB/gm) || []).length;
  const noRawFences = !result.includes('```');
  const noUndef     = !result.includes('undefined');
  const pass        = tabCount === 10 && noRawFences && noUndef;

  console.log(`  ${pass ? '✅' : '❌'} ${name}: ${tabCount}/10 tabs | no fences: ${noRawFences} | no undefined: ${noUndef}`);
  if (!pass) allPassed = false;

  // Print all tab header lines
  result.split('\n').filter(l => l.startsWith('## TAB')).forEach(l => console.log(`       ${l}`));
});

// ── Test D: MF/ETF with missing stock-specific fields don't crash ──────────────
console.log('\n═══ TEST D: MF/ETF missing-field safety ═══');

const minimalMF = {
  tabs: [
    { id: '01', name: 'Fund Overview' },           // no fields, no subsections
    { id: '02', name: 'NAV', fields: null },        // null fields
    { id: '03', name: 'Holdings', subsections: [] },// empty subsections
    { id: '04', name: 'Risk', subsections: [{ title: 'Metrics' }] }, // subsection no fields
    { id: '05', name: 'Tax', fields: {} },
    { id: '06', name: 'Tab 6' },
    { id: '07', name: 'Tab 7' },
    { id: '08', name: 'Tab 8' },
    { id: '09', name: 'Tab 9' },
    { id: '10', name: 'Tab 10' },
  ]
};

try {
  const result = jsonToTabText(minimalMF);
  const pass = result && !result.includes('undefined') && (result.match(/^## TAB/gm) || []).length === 10;
  console.log(`  ${pass ? '✅' : '❌'} MF with null/missing fields handled gracefully`);
  if (!pass) allPassed = false;
} catch (e) {
  console.log(`  ❌ Crash on null/missing fields: ${e.message}`);
  allPassed = false;
}

// ── Summary ────────────────────────────────────────────────────────────────────
console.log('\n' + '═'.repeat(50));
console.log(allPassed ? '✅  ALL TESTS PASSED — safe to commit.' : '❌  SOME TESTS FAILED — do NOT commit.');
console.log('═'.repeat(50) + '\n');
process.exit(allPassed ? 0 : 1);
