const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const htmlPath = path.join(process.cwd(), 'live_tv_geo_concepts.html');
  const url = 'file:///' + htmlPath.replace(/\\/g,'/');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 2000 } });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.screenshot({ path: path.join(process.cwd(), 'live_tv_geo_concepts_desktop.png'), fullPage: true });

  const page2 = await browser.newPage({ viewport: { width: 420, height: 2000 } });
  await page2.goto(url, { waitUntil: 'domcontentloaded' });
  await page2.screenshot({ path: path.join(process.cwd(), 'live_tv_geo_concepts_mobile.png'), fullPage: true });
  await browser.close();
  console.log('ok');
})();
