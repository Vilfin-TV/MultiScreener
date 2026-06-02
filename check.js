
  (function(){
    var t = localStorage.getItem('viltv_theme') || 'black';
    if (t === 'standard') { t = 'midnight'; }
    document.documentElement.setAttribute('data-theme', t);
  })();
