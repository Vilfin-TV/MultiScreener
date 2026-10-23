/**
 * Free GitHub-backed VilfinTV Stories API on Cloudflare Workers.
 * Public published content only. No WordPress, paid server or credentials.
 * GET /api/stories and /api/stories/:slug
 * Content is maintained in the main branch at stories/v1/.
 */
const ORIGIN='https://raw.githubusercontent.com/Vilfin-TV/MultiScreener/main/stories/v1/';
const valid=/^[a-z0-9][a-z0-9-]{0,99}$/;
function response(value,status=200){return new Response(JSON.stringify(value),{status,headers:{
 'content-type':'application/json; charset=utf-8',
 'cache-control':status===200?'public, max-age=60, s-maxage=300':'no-store',
 'x-content-type-options':'nosniff',
 'access-control-allow-origin':'https://vilfintv.com'
}})}
export default {
 async fetch(request){
  const url=new URL(request.url);
  if(request.method!=='GET')return response({error:'Method not allowed'},405);
  const m=url.pathname.match(/^\/api\/stories(?:\/([a-z0-9-]+))?\/?$/);
  if(!m)return response({error:'Not found'},404);
  if(m[1]&&!valid.test(m[1]))return response({error:'Invalid slug'},400);
  const filename=m[1]?m[1]+'.json':'index.json';
  try{
   const upstream=await fetch(ORIGIN+filename,{headers:{accept:'application/json'},redirect:'error',cf:{cacheEverything:true,cacheTtl:300}});
   if(upstream.status===404)return response({error:'Story not found'},404);
   if(!upstream.ok)return response({error:'Content unavailable'},502);
   const raw=await upstream.text();
   if(raw.length>1500000)return response({error:'Content too large'},502);
   const data=JSON.parse(raw);
   if(data.schemaVersion!==1)return response({error:'Unsupported version'},502);
   if(m[1]&&(!Array.isArray(data.chapters)||!data.chapters.length))return response({error:'Invalid story'},502);
   if(!m[1]&&!Array.isArray(data.stories))return response({error:'Invalid catalog'},502);
   return response(data);
  }catch{return response({error:'Stories temporarily unavailable'},502)}
 }
};
