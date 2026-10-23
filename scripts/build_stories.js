/**
 * Generate the public Stories catalog from versioned story files.
 * Run: node scripts/build_stories.js
 * Same GitHub Actions -> committed JSON -> frontend fetch pattern as News.
 */
const fs=require('node:fs');
const path=require('node:path');
const dir=path.join(__dirname,'..','stories','v1');
const files=fs.readdirSync(dir).filter(f=>f.endsWith('.json')&&f!=='index.json'&&!f.endsWith('.schema.json'));
const entries=[];
for(const file of files){
 const doc=JSON.parse(fs.readFileSync(path.join(dir,file),'utf8'));
 if(doc.schemaVersion!==1||!doc.slug||!Array.isArray(doc.chapters)||!doc.chapters.length)throw Error('Invalid story: '+file);
 if(file!==doc.slug+'.json')throw Error('Slug/filename mismatch: '+file);
 if(!Array.isArray(doc.genreIds)||!doc.genreIds.length)throw Error('Missing genres: '+file);
 const chapters=doc.chapters;
 for(const [i,ch] of chapters.entries())if(!ch.title||!Array.isArray(ch.paragraphs)||!ch.paragraphs.length)throw Error('Empty chapter '+(i+1)+' in '+file);
 entries.push({id:doc.id,slug:doc.slug,title:doc.title,synopsis:doc.synopsis||'',genreIds:doc.genreIds,levels:doc.levels||['general'],chapterCount:chapters.length,revision:doc.revision});
}
entries.sort((a,b)=>a.title.localeCompare(b.title));
const index={schemaVersion:1,stories:entries};
fs.writeFileSync(path.join(dir,'index.json'),JSON.stringify(index,null,2)+'\n');
console.log('Published catalog:',entries.length,'stories');
