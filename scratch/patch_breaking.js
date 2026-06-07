const fs = require('fs');

let content = fs.readFileSync('scripts/build_live_news.js', 'utf8');

// Update data paths
content = content.replace('live_news.json', 'breaking_news.json');

// Remove FEEDS parsing from index.html and replace with direct array
const feedsDef = `// Use direct publisher RSS feeds for requested regions that include images
const FEEDS = [
  { url: 'https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml', name: 'US', id: 'us' },
  { url: 'https://feeds.bbci.co.uk/news/world/europe/rss.xml', name: 'Europe', id: 'eu' },
  { url: 'https://japantoday.com/feed', name: 'Japan', id: 'jp' },
  { url: 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms', name: 'India', id: 'in' },
  { url: 'https://www.thehindu.com/news/national/kerala/feeder/default.rss', name: 'Kerala', id: 'kl' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/2950623.cms', name: 'Tamil Nadu', id: 'tn' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms', name: 'Mumbai', id: 'mh' },
  { url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128839598.cms', name: 'Delhi', id: 'dl' },
  { url: 'https://feeds.bbci.co.uk/news/world/asia/rss.xml', name: 'Asia', id: 'as' },
  { url: 'https://feeds.bbci.co.uk/news/world/middle_east/rss.xml', name: 'Middle East', id: 'me' }
];`;

content = content.replace(/const INDEX_FILE =[^;]+;/, feedsDef);
content = content.replace(/\/\/ Extract NEWS_SOURCES[\s\S]+?let sources = \[\];[\s\S]+?catch\(e\) \{[\s\S]+?\}[\s\S]+?console\.log\([^\n]+\n/, 'const sources = FEEDS;\n');

// Change dictionary to flat array
content = content.replace(/liveNewsData\[src\.id\] = items;/g, 'allItems.push(...items.filter(i => i.image));');
content = content.replace(/const liveNewsData = \{\};/, 'let allItems = [];');

// Add deduplication and sorting logic
const dedupeLogic = `
  // Deduplicate
  const seen = new Set();
  const uniqueItems = [];
  for (let item of allItems) {
    const key = item.title.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!seen.has(key)) {
      seen.add(key);
      uniqueItems.push({
        title: item.title,
        link: item.link,
        description: item.description,
        publishedAt: item.pubDate ? new Date(item.pubDate).getTime() : Date.now(),
        imageUrl: item.image
      });
    }
  }

  // Sort by newest
  uniqueItems.sort((a, b) => b.publishedAt - a.publishedAt);
  const finalItems = uniqueItems.slice(0, 20);

  // Save output
  fs.writeFileSync(DATA_FILE, JSON.stringify(finalItems, null, 2));
  fs.writeFileSync(CACHE_FILE, JSON.stringify(pexelsCache, null, 2));
  console.log('Build complete! Data saved to data/breaking_news.json');
`;

content = content.replace(/\/\/ Save output[\s\S]+?console\.log[^\n]+;/g, dedupeLogic);

fs.writeFileSync('scripts/build_breaking_news.js', content);
console.log('Successfully generated build_breaking_news.js');
