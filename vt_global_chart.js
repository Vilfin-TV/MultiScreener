/* Short-range global ETF price charts. Daily observations; no invented ticks. */
(function(){
  'use strict';
  var promise;
  function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function load(){if(!promise)promise=fetch('data/global_etf_daily.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw Error('HTTP');return r.json();}).then(function(d){if(d.v!==1||!Array.isArray(d.dates)||!d.c||d.dates.length<2||d.dates.some(function(x,i){return !/^\d{4}-\d\d-\d\d$/.test(x)||(i&&x<=d.dates[i-1]);}))throw Error('Invalid daily history');return d;}).catch(function(e){promise=null;throw e;});return promise;}
  function points(d,ticker,range){
    var c=d.c[ticker];if(!Array.isArray(c)||c.length!==d.dates.length)throw Error('No daily history');
    var splits=(d.split&&d.split[ticker])||[], all=c.map(function(v,i){var px=v;if(!(typeof px==='number'&&isFinite(px)&&px>0))return null;splits.forEach(function(s){if(d.dates[i]<s[0]&&typeof s[1]==='number'&&s[1]>0)px/=s[1];});return [d.dates[i],px];}).filter(Boolean);
    var n={'1D':1,'1W':5,'1M':22,'3M':63,'6M':126,'1Y':252}[range]||22;
    // One preceding close is the return baseline, including for the1D range.
    var p=all.slice(-(n+1));if(p.length<2||p[p.length-1][0]!==d.asOf)throw Error('Latest close unavailable');return p;
  }
  function mount(root,ticker,asof){
    if(!root)return;var range='1M', data;
    var link='https://www.tradingview.com/chart/?symbol='+encodeURIComponent(ticker),other='https://finance.yahoo.com/quote/'+encodeURIComponent(ticker)+'/chart/';
    root.innerHTML='<div class="gtr-head"><div><h3>Trading Chart</h3><p data-gtr-note>Loading daily prices…</p></div><div class="gtr-ranges" role="group" aria-label="Trading chart range">'+['1D','1W','1M','3M','6M','1Y'].map(function(k){return '<button type="button" data-gtr="'+k+'" aria-pressed="'+(k===range)+'">'+k+'</button>';}).join('')+'</div></div><div class="gtr-plot"></div><p class="taxnote">Daily closing prices, adjusted for splits; cash dividends excluded. 1D compares the latest two closes; 1W covers five trading sessions. For an intraday timeline: <a href="'+link+'" target="_blank" rel="noopener noreferrer">TradingView chart ↗</a> · <a href="'+other+'" target="_blank" rel="noopener noreferrer">Yahoo Finance chart ↗</a>. External market data may be delayed depending on the exchange and provider.</p>';
    var box=root.querySelector('.gtr-plot'),note=root.querySelector('[data-gtr-note]');
    function unavailable(){box.innerHTML='<p>Daily prices are unavailable for this ETF. Use a chart link below.</p>';note.textContent='Daily chart unavailable';}
    function draw(){if(!data)return;try{if(data.asOf!==asof)throw Error('Snapshot date mismatch');var p=points(data,ticker,range),W=720,H=270,L=65,R=18,T=20,B=32,vs=p.map(function(x){return x[1];}),lo=Math.min.apply(null,vs),hi=Math.max.apply(null,vs),pad=(hi-lo)*.08||hi*.01;lo-=pad;hi+=pad;
      var X=function(i){return L+i/(p.length-1)*(W-L-R);},Y=function(v){return T+(hi-v)/(hi-lo)*(H-T-B);},ret=(vs[vs.length-1]/vs[0]-1)*100,col=ret>=0?'#087d52':'#c43343';
      var grid='';for(var j=0;j<5;j++){var v=lo+(hi-lo)*j/4,y=Y(v);grid+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="var(--line,#dce3ee)"/><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" fill="currentColor" font-size="11">$'+v.toFixed(2)+'</text>';}
      var path=p.map(function(x,i){return(i?'L':'M')+X(i).toFixed(2)+' '+Y(x[1]).toFixed(2);}).join(' ');
      var marks=p.map(function(x,i){return '<circle cx="'+X(i)+'" cy="'+Y(x[1])+'" r="'+(p.length<8?4:2)+'" fill="'+col+'"><title>'+esc(x[0])+' · $'+x[1].toFixed(4)+'</title></circle>';}).join('');
      box.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(ticker)+' '+range+' daily closing-price chart">'+grid+'<path d="'+path+'" fill="none" stroke="'+col+'" stroke-width="2.4"/>'+marks+'<text x="'+L+'" y="'+(H-8)+'" font-size="11" fill="currentColor">'+p[0][0]+'</text><text x="'+(W-R)+'" y="'+(H-8)+'" text-anchor="end" font-size="11" fill="currentColor">'+p[p.length-1][0]+'</text></svg>';
      note.textContent=range+' price change '+(ret>=0?'+':'')+ret.toFixed(2)+'% · latest close $'+vs[vs.length-1].toFixed(2)+' · '+p[p.length-1][0];
    }catch(e){unavailable();}}
    root.querySelector('.gtr-ranges').onclick=function(e){var b=e.target.closest('[data-gtr]');if(!b)return;range=b.dataset.gtr;root.querySelectorAll('[data-gtr]').forEach(function(x){x.setAttribute('aria-pressed',String(x===b));});draw();};
    load().then(function(d){data=d;draw();}).catch(unavailable);
  }
  window.VTGlobalChart={mount:mount,points:points};
}());
