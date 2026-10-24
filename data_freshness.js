/* Shared, display-only market-data freshness warnings. No fetches or data mutation. */
(function (root) {
  'use strict';
  function parseDay(s) {
    if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
    var d = new Date(s + 'T00:00:00Z');
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s ? d : null;
  }
  function weekdaysSince(asOf, now) {
    var start = parseDay(asOf);
    if (!start) return null;
    var end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    if (start > end) return -1;
    var n = 0;
    for (var t = start.getTime() + 86400000; t <= end.getTime(); t += 86400000) {
      var day = new Date(t).getUTCDay();
      if (day !== 0 && day !== 6) n++;
      if (n > 366) return n;
    }
    return n;
  }
  function status(asOf, now) {
    var n = weekdaysSince(asOf, now || new Date());
    if (n === null) return {warn:true, text:'Data date unavailable. Check the last successful update.'};
    if (n < 0) return {warn:true, text:'Data date is ahead of today. Verify the source timestamp.'};
    // Conservative grace period for weekends, exchange holidays and late publication.
    if (n < 4) return {warn:false, text:''};
    return {warn:true, text:'Data may be delayed: last market data ' + asOf + ' (' + n + ' weekdays ago). Check the latest market session; exchange holidays can affect updates.'};
  }
  function render(targetId, asOf, market) {
    if (!root.document) return;
    var target = root.document.getElementById(targetId);
    if (!target) return;
    var id = 'vt-freshness-' + targetId;
    var el = root.document.getElementById(id);
    var s = status(asOf);
    if (!s.warn) { if (el) el.remove(); return; }
    if (!el) {
      el = root.document.createElement('div');
      el.id = id;
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      el.style.cssText = 'margin:10px 0;padding:10px 12px;border:1px solid #d6a44b;border-radius:8px;background:rgba(214,164,75,.10);color:inherit;font-size:13px;line-height:1.5;';
      target.insertAdjacentElement('afterend', el);
    }
    el.textContent = (market ? market + ': ' : '') + s.text;
  }
  root.VTDataFreshness = {status:status, weekdaysSince:weekdaysSince, render:render};
})(typeof window !== 'undefined' ? window : globalThis);
