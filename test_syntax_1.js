
  // Apply saved colour theme before first paint to avoid flash
  (function(){
    var t = localStorage.getItem('viltv_theme') || 'black';
    if (t === 'standard') { t = 'midnight'; localStorage.setItem('viltv_theme','midnight'); }
    document.documentElement.setAttribute('data-theme', t);
  })();
