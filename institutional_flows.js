/* Dated equity-cash flows; ownership has a separate quarterly denominator. */
(function () {
  'use strict';
  var data, busy = false, period = 'daily', shown = 30;
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); };
  var money = function(n){ return (n < 0 ? '−' : '') + Math.abs(n / 100).toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2}); };
  var dateText = function(s){return new Date(s+'T00:00:00Z').toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});};
  function validate(j) {
    if(j.v !== 1 || j.unit !== 'INR crore / 100' || !j.daily || !j.daily.length || !j.audit || j.audit.errors !== 0 || !j.audit.officialLatestMatch) throw Error('Unverified flow data');
    var prev = '';
    j.daily.forEach(function(r){
      if(!/^\d{4}-\d\d-\d\d$/.test(r.date) || r.date <= prev || r.date > j.asOf || r.values.length !== 6 || !r.values.every(Number.isSafeInteger)) throw Error('Invalid daily records');
      [0,3].forEach(function(i){if(r.values[i]<0 || r.values[i+1]<0 || r.values[i]-r.values[i+1]!==r.values[i+2])throw Error('Cash flow totals do not reconcile');});
      prev = r.date;
    });
    if(prev !== j.asOf) throw Error('Latest session missing');
    var o=j.ownership;
    if(!o || ![o.fii,o.dii].every(function(x){return typeof x==='number' && isFinite(x) && x>=0 && x<=100;}) || o.fii+o.dii>100 || !/^\d{4}-\d\d-\d\d$/.test(o.asOf) || o.asOf>j.asOf || !/^https:\/\/nsearchives\.nseindia\.com\//.test(o.source))throw Error('Invalid ownership snapshot');
  }
  // Recompute the displayed totals from daily records rather than trusting totals.
  function groups(p) {
    var by = {};
    data.daily.forEach(function(r){
      var dt = new Date(r.date+'T00:00:00Z'), key = r.date;
      if(p === 'weekly'){dt.setUTCDate(dt.getUTCDate()-(dt.getUTCDay()+6)%7);key=dt.toISOString().slice(0,10);}
      else if(p === 'monthly')key=key.slice(0,7);else if(p === 'yearly')key=key.slice(0,4);
      var g=by[key] || (by[key]={key:key,from:r.date,to:r.date,n:0,v:[0,0,0,0,0,0]});
      g.to=r.date;g.n++;g.v=g.v.map(function(x,i){return x+r.values[i];});
    });
    return Object.keys(by).sort().reverse().map(function(k){return by[k];});
  }
  function label(g){
    if(period==='daily')return dateText(g.from);
    if(period==='weekly')return 'Week of '+dateText(g.key);
    if(period==='monthly')return new Date(g.key+'-01T00:00:00Z').toLocaleDateString('en-IN',{month:'long',year:'numeric',timeZone:'UTC'});
    return g.key;
  }
  function render() {
    var root=document.getElementById('sipFlows');if(!root || !data)return;
    var latest=data.daily[data.daily.length-1], own=data.ownership, list=groups(period), age=(Date.now()-Date.parse(data.asOf+'T00:00:00+05:30'))/86400000;
    var h='<div class="if-heading"><div><div class="sec-title">FII &amp; DII activity</div><p class="sec-sub">Equity cash market · NSE, BSE &amp; MSEI combined · ₹ crore · provisional</p></div><span class="if-stamp">Latest session '+dateText(data.asOf)+'</span></div>';
    if(age>5)h+='<p class="if-warning" role="status">The flow snapshot is older than five days. Check its session date before using these figures.</p>';
    h+='<div class="if-summary">'+[['FII / FPI',0],['DII',3]].map(function(a){var i=a[1],v=latest.values;return '<div class="card pcard"><small>'+a[0]+' · latest session net</small><strong class="'+(v[i+2]<0?'if-sell':'if-buy')+'">'+(v[i+2]>0?'+':'')+money(v[i+2])+'</strong><div class="if-gross"><span>Buy <b>'+money(v[i])+'</b></span><span>Sell <b>'+money(v[i+1])+'</b></span></div></div>';}).join('')+'</div>';
    h+='<div class="card pcard if-ownership"><div class="sec-title">Ownership in Indian listed equities</div><p class="sec-sub">Latest verified quarter: '+dateText(own.asOf)+' · share of total market capitalisation of NSE-listed companies covered by the study</p><div class="if-own-grid">'+[['FII / FPI',own.fii],['DII',own.dii]].map(function(a){return '<div><span>'+a[0]+'</span><b>'+a[1].toFixed(1)+'%</b><div class="if-track"><i style="width:'+a[1]+'%"></i></div></div>';}).join('')+'</div><p class="note">Quarterly holdings, not a live percentage or a share of today’s buying. DII includes domestic mutual funds, banks, financial institutions, insurers and other institutional non-promoters. <a href="'+esc(own.source)+'" target="_blank" rel="noopener">NSE ownership report ↗</a></p></div>';
    h+='<div class="card pcard"><div class="if-periods" role="tablist" aria-label="Institutional flow periods">'+['daily','weekly','monthly','yearly'].map(function(p){return '<button type="button" role="tab" id="if-tab-'+p+'" aria-controls="if-results" aria-selected="'+(p===period)+'" tabindex="'+(p===period?'0':'-1')+'" data-if-period="'+p+'">'+p[0].toUpperCase()+p.slice(1)+'</button>';}).join('')+'</div><p class="note">Weeks run Monday–Sunday; months and years follow the calendar. The current period runs through '+dateText(data.asOf)+'. Net = buy − sell. History begins '+dateText(data.historyFrom)+'.</p><div id="if-results" role="tabpanel" aria-labelledby="if-tab-'+period+'"><div class="if-table-head"><span>Period / reported sessions</span><span>FII / FPI · buy / sell / net</span><span>DII · buy / sell / net</span></div>';
    h+=list.slice(0,shown).map(function(g){var current=period!=='daily'&&g.to===data.asOf;return '<div class="if-row"><div class="if-date"><b>'+esc(label(g))+'</b><small>'+g.n+' reported session'+(g.n===1?'':'s')+(current?' · to date':'')+'</small>'+(period!=='daily'?'<small>'+dateText(g.from)+' – '+dateText(g.to)+'</small>':'')+'</div>'+[['FII / FPI',0],['DII',3]].map(function(a){var i=a[1];return '<div class="if-participant"><b class="if-mobile-label">'+a[0]+'</b><div class="if-figures"><span><small>Buy</small>'+money(g.v[i])+'</span><span><small>Sell</small>'+money(g.v[i+1])+'</span><span class="'+(g.v[i+2]<0?'if-sell':'if-buy')+'"><small>Net</small><b>'+(g.v[i+2]>0?'+':'')+money(g.v[i+2])+'</b></span></div></div>';}).join('')+'</div>';}).join('')+'</div>';
    if(list.length>shown)h+='<button type="button" class="if-more" data-if-more>Show 30 more periods</button>';
    h+='<p class="note if-provenance">Daily history: <a href="https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/" target="_blank" rel="noopener">Moneycontrol cash-market archive</a>; each fetched month reconciled to its published total. Latest six figures match <a href="https://www.nseindia.com/reports/fii-dii" target="_blank" rel="noopener">NSE</a>; '+data.audit.independentSessions+' recent sessions also match <a href="https://groww.in/fii-dii-data" target="_blank" rel="noopener">Groww</a>. '+data.daily.length+' daily records · '+data.audit.monthsReconciled+' reconciled months. Figures may be revised. These are secondary-market cash flows; NSDL’s FPI series includes different transactions and must be read separately.</p></div>';
    root.innerHTML=h;
  }
  function load() {
    var root=document.getElementById('sipFlows');if(!root||busy)return;if(data){render();return;}
    busy=true;root.innerHTML='<div class="card pcard" role="status">Loading verified institutional activity…</div>';
    fetch('data/mf/institutional_flows.json').then(function(r){if(!r.ok)throw Error('Flow data unavailable');return r.json();}).then(function(j){validate(j);data=j;render();}).catch(function(){root.innerHTML='<div class="card pcard"><div class="sec-title">Institutional activity is unavailable</div><p>The last verified snapshot could not be loaded. Please retry.</p><button type="button" data-if-retry>Retry</button></div>';}).finally(function(){busy=false;});
  }
  function init(){
    var style=document.createElement('style');style.textContent='.if-heading{display:flex;justify-content:space-between;gap:14px;align-items:start;margin:22px 0 16px}.if-stamp{font-size:12px;white-space:nowrap;color:var(--text3)}.if-summary,.if-own-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.if-summary strong{display:block;font-size:27px;margin:8px 0}.if-gross{display:flex;justify-content:space-between;gap:10px;font-size:12px}.if-gross b{display:block}.if-own-grid{margin:18px 0}.if-own-grid b{float:right;font-size:22px}.if-track{height:7px;background:var(--border,#dce3ee);border-radius:7px;margin-top:12px;overflow:hidden}.if-track i{display:block;height:100%;background:#3377d8}.if-periods{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.if-periods button,.if-more{border:1px solid var(--border,#dce3ee);background:var(--surface,#fff);color:inherit;padding:9px 16px;border-radius:8px;font:inherit;cursor:pointer}.if-periods button[aria-selected=true]{background:#245fbd;color:white}.if-table-head,.if-row{display:grid;grid-template-columns:minmax(170px,1fr) minmax(0,1.5fr) minmax(0,1.5fr);gap:22px;padding:14px 0;border-bottom:1px solid var(--border,#dce3ee)}.if-table-head{font-size:11px;font-weight:700;color:var(--text3)}.if-date{font-size:13px}.if-date small{display:block;font-size:11px;margin-top:5px;color:var(--text3)}.if-figures{display:grid;grid-template-columns:1fr 1fr 1.1fr;gap:8px;text-align:right;font-size:12px;font-variant-numeric:tabular-nums}.if-figures small{display:block;font-size:10px;color:var(--text3);margin-bottom:4px}.if-buy{color:var(--pos,#078058)}.if-sell{color:var(--neg,#c33d49)}.if-mobile-label{display:none}.if-more{margin-top:16px}.if-provenance{margin-top:18px}.if-warning{background:#fff0d1;color:#71480b;padding:12px;border-radius:8px}#v-sip:not([data-st="market"]) #sipMarket,#v-sip:not([data-st="flows"]) #sipFlows{display:none}#v-sip[data-st="market"] .sp-plan,#v-sip[data-st="flows"] .sp-plan{display:none!important}@media(max-width:760px){.if-heading{display:block}.if-stamp{display:block;margin-top:8px}.if-summary,.if-own-grid{gap:10px}.if-summary .pcard{padding:13px}.if-summary strong{font-size:22px}.if-gross{display:block}.if-gross span{display:block;margin-top:7px}.if-gross b{display:inline}.if-table-head{display:none}.if-row{grid-template-columns:1fr;gap:12px;padding:18px 0}.if-mobile-label{display:block;font-size:11px;margin-bottom:8px}.if-date small{display:inline;margin-right:8px}.if-date b{display:block;margin-bottom:6px}.if-figures{font-size:12px}.if-own-grid b{font-size:20px}.if-periods button{padding:9px 13px}}';document.head.appendChild(style);
    document.addEventListener('click',function(e){var b=e.target.closest('[data-st="flows"],[data-if-retry],[data-if-period],[data-if-more]');if(!b)return;if(b.hasAttribute('data-if-period')){period=b.getAttribute('data-if-period');shown=30;render();document.getElementById('if-tab-'+period).focus();}else if(b.hasAttribute('data-if-more')){shown+=30;render();}else load();});
    document.addEventListener('keydown',function(e){if(!e.target.matches('[data-if-period]')||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();var ps=['daily','weekly','monthly','yearly'],i=ps.indexOf(period);period=ps[e.key==='Home'?0:e.key==='End'?3:(i+(e.key==='ArrowRight'?1:3))%4];shown=30;render();document.getElementById('if-tab-'+period).focus();});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
}());
