const fs = require('fs');
const contentJson = JSON.parse(fs.readFileSync('content.json', 'utf-8'));
const post = contentJson.find(p => p.id === '1780672699032');
if (post) {
  post.photo = 'images/news/nri_tax.png';
  fs.writeFileSync('content.json', JSON.stringify(contentJson, null, 2));
  console.log('Added photo to post');
}
