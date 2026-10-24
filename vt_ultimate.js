/* Shared, read-only John folio panels for the public and private statements. */
(function(){'use strict';
  function e(s){return String(s==null?'—':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function n(v,s){return typeof v==='number'&&isFinite(v)?v.toLocaleString('en-IN',{maximumFractionDigits:2})+(s||''):'Unavailable';}
  function table(headers,rows){return '<div style="overflow-x:auto;max-width:100%" tabindex="0"><table style="width:100%;min-width:'+(headers.length>8?'1100':'720')+'px;border-collapse:collapse;text-align:left"><thead><tr>'+headers.map(function(h){return '<th style="padding:10px;border-bottom:1px solid #cbd5e1;white-space:nowrap">'+e(h)+'</th>';}).join('')+'</tr></thead><tbody>'+rows.map(function(r){return '<tr>'+r.map(function(v){return '<td style="padding:10px;border-bottom:1px solid #e2e8f0;vertical-align:top">'+v+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table></div>';}
  function render(kind,u){
    if(!u||!u.plan)return '<p>Waiting for an audited strategy snapshot.</p>';
    var p=u.plan,selected=p.selected||[],h='<p><b>John · Manager · India resident · no other taxable income</b></p><p>₹20,000 per month in this folio, including modelled costs; separate ₹20,000 mutual fund and ₹20,000 ETF budgets. Start: <b>26 Oct 2026</b>. Seven-year goal; 16%+ annualised return is a target, not a forecast or guarantee.</p>';
    h+='<p>Market evidence as of <b>'+e(u.asOf)+'</b>. '+e(u.status)+'.</p>';
    if(kind==='strategy'){
      h+='<p><b>Plan '+e(p.mode)+'</b> · '+e(p.reason)+'</p><p>First and last trading weeks; October starts on 26 Oct with ₹20,000. Normally ₹10,000 funding in each window. Purchases meet whole monthly fund targets and minimum amounts. Up to five distinct funds per month; fewer when evidence fails. Failed sleeves stay in verified parking or cash. Cash allocation: <b>'+n(p.cashWeight,'%')+'</b>.</p>';
      h+=table(['Fund / ETF','Category','Monthly target','P/E','Look-through earnings growth','Eligibility'],selected.map(function(c){var cs=c.checks||[],pass=cs.filter(function(x){return x.state==='pass';}).length,na=cs.filter(function(x){return x.state==='na';}).length;return [e(c.name),e(c.category),'₹'+n(20000*c.weight/100)+' · '+n(c.weight,'%'),n(c.earnings&&c.earnings.pe),n(c.earnings&&c.earnings.earningsGrowth,'%'),pass+' passed'+(na?' · '+na+' N/A':'')+' / '+cs.length];}));
      h+='<p>Plan A: diversified eligible funds. Plan B: reduce equity when broad-market valuation reaches its 80th historical percentile. Plan C: verified parking or cash when evidence is missing. During the final two years, progressively reduce equity. No fallback is assumed to deliver 16%.</p><p>Ranking emphasises lower P/E and stronger comparable earnings. Earnings growth holds the current disclosed stock quantities constant; it is not a fund’s own EPS or a forecast. Tax-aware rotations require a verified cheaper replacement and costs below the policy limit. Tax harvesting uses John’s shared MF/ETF allowances and FIFO lots.</p>';
      selected.forEach(function(c){h+='<details style="margin:12px 0"><summary><b>'+e(c.name)+' — eligibility evidence</b></summary>'+table(['Check','Result','Observed value'],c.checks.map(function(x){return [e(x.label),e(x.state==='na'?'Not applicable':x.state),e(typeof x.value==='object'?JSON.stringify(x.value):x.value)];}))+'</details>';});
    }else if(kind==='metrics'){
      h+='<p>Actual daily NAV / adjusted-price histories. 1 year is absolute return; 3, 5 and 7 years are annualised CAGR. Fund costs are embedded in NAV. Investor taxes and entry/exit costs are excluded. Missing history remains unavailable.</p>';
      var rows=selected.map(function(c){return metricRow(c.name,c.history);});rows.push(metricRow('Current mix · hypothetical one-time buy and hold',p.history));
      h+=table(['Fund / current mix','1Y','3Y CAGR','5Y CAGR','7Y CAGR','Since inception*','Annualised volatility','Max drawdown','Risk / 10','Observed history'],rows);
      h+='<p>*Since-inception return is shown only when the observed start is within seven days of the recorded launch. The current mix uses its common observed history, with fixed units and cash; it is not John’s actual SIP performance. Risk /10 combines 60% volatility and 40% drawdown, capped at 10; maximum drawdown is peak-to-trough over the available history.</p>';
      if(u.historicalWarning)h+='<p>'+e(u.historicalWarning)+'</p>';
    }else{
      var b=u.backtest||{};h+='<p><b>Historical illustration — limited validation</b></p><p>'+e(b.basis||'Historical data not yet available')+'</p>';
      h+=table(['Period','From','Through','Contributions','Ending value','SIP XIRR','Max drawdown'],(b.cases||[]).map(function(c){return [c.years+' years',e(c.from),e(c.to),'₹'+n(c.contributed),'₹'+n(c.terminalValue),n(c.xirr,'%'),n(c.maximumDrawdown,'%')];}));
      h+='<p>₹20,000 monthly, historical selected mix, entry costs included. No exit costs or investor taxes; cash earns zero. Monthly funding differs from John’s live first/last-week execution. Today’s selection introduces hindsight and survivorship bias. A full point-in-time backtest of the adaptive 50-check strategy is unavailable because historical portfolio and earnings snapshots were not archived. Future decisions are archived prospectively.</p>';
    }
    return '<div style="min-width:0;overflow-wrap:anywhere;line-height:1.65">'+h+'</div>';
  }
  function metricRow(name,m){m=m||{};var r=m.returns||{};return [e(name),n(r['1'],'%'),n(r['3'],'%'),n(r['5'],'%'),n(r['7'],'%'),n(m.inceptionVerified?m.sinceInception:null,'%')+(m.inceptionVerified&&m.sinceAnnualised?' CAGR':''),n(m.volatility,'%'),n(m.maximumDrawdown,'%'),n(m.risk10),e(m.from)+' → '+e(m.asOf)];}
  window.VTUltimate={render:render};
})();
