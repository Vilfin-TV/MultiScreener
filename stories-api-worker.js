/**
 * VilfinTV Stories public API gateway (Cloudflare Worker).
 * Configure WORDPRESS_ORIGIN as a secret/var, e.g. https://cms.example.com
 * Routes: GET /api/stories, GET /api/stories/{slug}
 * No write endpoints, credentials, cookies or WP admin traffic.
 */
const allowedSlug = /^[a-z0-9][a-z0-9-]{0,99}$/;
const json = (value,status=200,ttl=60)=>new Response(JSON.stringify(value),{
 status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':status===200?'public, max-age=30, s-maxage='+ttl:'no-store','X-Content-Type-Options':'nosniff','Access-Control-Allow-Origin':'https://vilfintv.com','Vary':'Origin'}
});
export default {
 async fetch(request,env) {
  const u=new URL(request.url);
  if(request.method!=='GET')return json({error:'Method not allowed'},405);
  const match=u.pathname.match(/^\/api\/stories(?:\/([a-z0-9-]+))?\/?$/);
  if(!match)return json({error:'Not found'},404);
  if(match[1]&&!allowedSlug.test(match[1]))return json({error:'Invalid slug'},400);
  if(!env.WORDPRESS_ORIGIN)return json({error:'CMS not configured'},503);
  let origin;
  try{origin=new URL(env.WORDPRESS_ORIGIN);if(origin.protocol!=='https:'||origin.username||origin.password||origin.pathname!=='/'&&origin.pathname!=='')throw Error('Invalid origin')}catch{return json({error:'CMS configuration invalid'},503)}
  const endpoint=origin.origin+'/wp-json/viltv/v1/stories'+(match[1]?'/'+encodeURIComponent(match[1]):'');
  try{
   const upstream=await fetch(endpoint,{headers:{Accept:'application/json'},redirect:'error',signal:AbortSignal.timeout(8000),cf:{cacheTtl:60,cacheEverything:true}});
   if(upstream.status===404)return json({error:'Story not found'},404);
   if(!upstream.ok)return json({error:'CMS temporarily unavailable'},502);
   const type=upstream.headers.get('content-type')||'';
   if(!type.includes('application/json'))return json({error:'Invalid CMS response'},502);
   const body=await upstream.text();
   if(body.length>1500000)return json({error:'Story too large'},502);
   const data=JSON.parse(body);
   if(data.schemaVersion!==1)return json({error:'Unsupported content version'},502);
   if(match[1]&&(!Array.isArray(data.chapters)||!data.chapters.length))return json({error:'Invalid story'},502);
   if(!match[1]&&!Array.isArray(data.stories))return json({error:'Invalid catalog'},502);
   return json(data,200,60);
  }catch{return json({error:'Stories temporarily unavailable'},502)}
 }
};
