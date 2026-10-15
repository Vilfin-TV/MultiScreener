// Temporary: render each fund house's portfolio-disclosure page and list spreadsheet links.
const { chromium } = require('playwright');
const fs = require('fs');
const PAGES = {
  sbi: 'https://www.sbimf.com/portfolios', icici: 'https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=Monthly%20Portfolio%20Disclosures',
  hdfc: 'https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio', nippon: 'https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures',
  kotak: 'https://www.kotakmf.com/Information/portfolios', axis: 'https://www.axismf.com/statutory-disclosures',
  absl: 'https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio', uti: 'https://www.utimf.com/downloads/consolidate-all-portfolio-disclosure',
  mirae: 'https://www.miraeassetmf.co.in/downloads/portfolio', dsp: 'https://www.dspim.com/mandatory-disclosures/portfolio-disclosures',
  tata: 'https://www.tatamutualfund.com/schemes-related/portfolio', motilal: 'https://www.motilaloswalmf.com/download/scheme-portfolio',
  bandhan: 'https://bandhanmutual.com/downloads/disclosures', edelweiss: 'https://www.edelweissmf.com/statutory-disclosures/portfolio-disclosure',
  canara: 'https://www.canararobeco.com/documents/statutory-disclosures/scheme-monthly-portfolio/', franklin: 'https://www.franklintempletonindia.com/downloads/fund-documents/monthly-portfolio',
  hsbc: 'https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library', invesco: 'https://www.invescomutualfund.com/literature-forms/monthly-holdings/equity',
  quant: 'https://quantmutual.com/statutory-disclosures', ppfas: 'https://amc.ppfas.com/downloads/portfolio-disclosure/',
};
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', locale: 'en-IN' });
  const out = {};
  for (const [k, u] of Object.entries(PAGES)) {
    const p = await ctx.newPage();
    const net = new Set();
    p.on('response', r => { const ct = r.headers()['content-type'] || ''; const url = r.url(); if (/\.(xlsx?|zip)(\?|$)/i.test(url) || /spreadsheet|excel|zip/i.test(ct)) net.add(url); });
    try {
      const resp = await p.goto(u, { waitUntil: 'networkidle', timeout: 60000 });
      await p.waitForTimeout(3000);
      const links = await p.$$eval('a', as => as.map(a => a.href).filter(h => /\.(xlsx?|zip|xlsm)(\?|#|$)/i.test(h)));
      const text = (await p.content()).length;
      const recent = links.filter(h => /2026|sep|sept|oct/i.test(h));
      out[k] = { status: resp && resp.status(), html: text, links: links.length, recent: recent.slice(0, 8), sample: links.slice(0, 5), net: [...net].slice(0, 5), final: p.url() };
    } catch (e) { out[k] = { err: String(e).slice(0, 200) }; }
    console.log(k, JSON.stringify(out[k]).slice(0, 1200));
    await p.close();
  }
  await b.close();
  fs.mkdirSync('.probe', { recursive: true });
  fs.writeFileSync('.probe/holdings_probe.json', JSON.stringify(out, null, 1));
})();
